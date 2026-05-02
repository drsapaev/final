# ws_diag.py
import asyncio
import logging
import threading

import uvicorn
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

PORT = 8050
WS_PATH = "/ws/diag"

logging.basicConfig(level=logging.INFO)

app = FastAPI()


@app.websocket(WS_PATH)
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({"type": "server", "msg": "WebSocket connected"})
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"echo: {data}")
    except WebSocketDisconnect:
        logging.info("Disconnected")


def start_server():
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    server.run()


async def run_client():
    await asyncio.sleep(2)  # подождать, пока сервер стартует
    uri = f"ws://localhost:{PORT}{WS_PATH}"
    try:
        async with websockets.connect(uri) as websocket:
            print(f"[CLIENT] ✅ Connected to {uri}")
            await websocket.send("Hello from client")
            resp = await websocket.recv()
            print(f"[CLIENT] 👂 Got response: {resp}")
    except Exception as e:
        print(f"[CLIENT] ❌ Failed to connect: {e}")


if __name__ == "__main__":
    thread = threading.Thread(target=start_server, daemon=True)
    thread.start()

    asyncio.run(run_client())
