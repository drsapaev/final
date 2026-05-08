import os


def require_ws_test_confirmation():
    if os.getenv("CONFIRM_FRONTEND_WS_TEST") != "1":
        raise RuntimeError(
            "Refusing to open a websocket connection. "
            "Set CONFIRM_FRONTEND_WS_TEST=1 only for an explicit local websocket smoke."
        )


def websocket_url():
    return os.getenv("FRONTEND_WS_TEST_URL", "").strip() or (
        "ws://localhost:18000/ws/queue?department=ENT&date=2025-08-18"
    )


def websocket_origin():
    return os.getenv("FRONTEND_WS_TEST_ORIGIN", "").strip() or "http://localhost:5173"


def on_open(ws):
    print("open")


def on_message(ws, message):
    print("msg:", message)


def on_close(ws, *args):
    print("closed")


def main():
    require_ws_test_confirmation()
    import websocket

    ws = websocket.WebSocketApp(
        websocket_url(),
        header=[f"Origin: {websocket_origin()}"],
        on_open=on_open,
        on_message=on_message,
        on_close=on_close,
    )
    ws.run_forever()


if __name__ == "__main__":
    main()
