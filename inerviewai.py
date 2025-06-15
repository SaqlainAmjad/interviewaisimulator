import asyncio
import io
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from google import genai
from google.genai import types
import wave

app = FastAPI()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")  # Set on Render as an environment secret
MODEL = "gemini-2.5-flash-preview-native-audio-dialog"

@app.websocket("/interview")
async def interview_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        # 1. Wait for "start" (could send config/user context/questions etc.)
        start_msg = await websocket.receive_json()
        print(f"Session starting, client says: {start_msg}")

        # 2. Connect to Gemini Live session
        client = genai.Client(api_key=GOOGLE_API_KEY)
        config = {
            "response_modalities": ["AUDIO"],
            "system_instruction": "You are conducting a professional job interview, asking one question at a time in a friendly, professional manner. Listen to audio answers and provide brief encouraging feedback."
        }
        session = await client.aio.live.connect(model=MODEL, config=config).__aenter__()
        print("Connected to Gemini audio session.")

        async def google_to_client():
            try:
                async for response in session.receive():
                    if response.data:
                        # Forward audio to frontend
                        await websocket.send_bytes(response.data)
            except Exception as e:
                print("Error in google_to_client:", e)

        g2c_task = asyncio.create_task(google_to_client())

        # 3. Loop: recv mic audio from client, send to Gemini
        while True:
            in_msg = await websocket.receive_bytes()
            # Forward as Gemini audio blob
            await session.send_realtime_input(
                audio=types.Blob(data=in_msg, mime_type="audio/pcm;rate=16000")
            )

    except WebSocketDisconnect:
        print("Client disconnected.")
    except Exception as e:
        print("Server exception:", e)
    finally:
        await session.__aexit__(None, None, None)

@app.get("/")
def get_root():
    return {"msg": "AI interview relay up!"}
