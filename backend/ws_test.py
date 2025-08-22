import websocket

URL = "ws://localhost:8000/ws/queue?department=ENT&date=2025-08-18"

def on_open(ws): print("open")
def on_message(ws, m): print("msg:", m)
def on_close(ws, *a): print("closed")

ws = websocket.WebSocketApp(
    URL,
    header=["Origin: http://localhost:5173"],  # важно для WS
    on_open=on_open,
    on_message=on_message,
    on_close=on_close,
)
ws.run_forever()
