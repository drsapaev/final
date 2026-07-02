# Chat System & WebSocket Fix Report

## Overview
This report documents the critical fixes applied to the Chat System and WebSocket infrastructure to resolve connection issues, 500 Internal Server Errors, and real-time synchronization problems.

## 1. Critical Database Connection Leak (Fixed)
**Symptoms:** 
- The Registrar Panel (and other parts of the app) were throwing `500 Internal Server Error` with `sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached`.
- Chat was unstable.

**Root Cause:**
The WebSocket handler in `chat_ws.py` and `main.py` was using `db: Session = Depends(get_db)`. In FastAPI, dependencies for WebSockets are resolved during the handshake and **kept alive** until the connection closes. Since WebSocket connections are persistent, each connected user was permanently holding a database connection from the pool (limit 5). 6 users = System Crash.

**Fix:**
- Removed `Depends(get_db)` from `chat_websocket_handler` and `chat_ws`.
- Implemented a short-lived session strategy:
  ```python
  # chat_ws.py
  db = SessionLocal()
  try:
      user = await authenticate_websocket(websocket, token, db)
  finally:
      db.close()
  ```
- This ensures the DB connection is only used for milliseconds during authentication and then released, leaving the WebSocket connection open without a DB lock.

## 2. Real-Time Message Delivery (Fixed)
**Symptoms:**
- Messages were not appearing instantly. Users had to refresh the page.
- "failed to send WebSocket notification" logs.

**Root Cause:**
Python's standard `json.dumps` (used by `active_connections[user_id].send_json`) cannot serialize `datetime` objects. The Pydantic models used for messages contain `created_at` fields. This caused a silent exception inside the WebSocket send loop.

**Fix:**
- Integrated `jsonable_encoder` from FastAPI to handle serialization of complex types before sending:
  ```python
  from fastapi.encoders import jsonable_encoder
  await self.active_connections[user_id].send_json(jsonable_encoder(data))
  ```

## 3. Cross-Tab Synchronization (Implemented)
**Symptoms:**
- Sending a message in Tab A did not show updating in Tab B (same user).

**Fix:**
- **Backend (`messages.py`):** Added logic to send WebSocket notifications to the **sender** as well as the recipient.
- **Frontend (`useChat.js`):** Updated `handleNewMessage` to accept "self-sent" messages if they belong to the active conversation, preventing duplicates via ID check.

## 4. Frontend Resilience (`useChat.js`)
**Fixes:**
- **Type Mismatch:** Implemented `String(id)` casting for all ID comparisons to handle discrepancies between API (int) and URL parameters (string).
- **Stale Closures:** Refactored the hook to use `useRef` for `activeConversation`, ensuring WebSocket callbacks always have access to the current state.
- **Infinite Reconnect:** Added logic to stop reconnection attempts if the server returns `4001 Unauthorized`.

## 5. Active Users List (`ChatWindow.jsx`)
**Fix:**
- Updated `useEffect` dependencies to reload the user list every time the chat window is opened (if no conversations exist), instead of only on mount.

## Conclusion
The chat system is now stable, scalable (does not block DB), and fully synchronized in real-time across multiple tabs and devices.
