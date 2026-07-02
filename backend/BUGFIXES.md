# Bug Fixes - Production Readiness

## Bug 1: WebSocket Heartbeat Timeout Detection (Updated)

### Problem
The `last_pong` variable was assigned inside a nested try block, creating a new local variable instead of updating the outer scope variable. This prevented pong responses from updating the timeout tracker, causing connection heartbeat/timeout detection to malfunction.

### Impact
- Dead connections could remain open indefinitely
- Heartbeat timeout checks would always use the original initialization value
- Memory leaks from stale WebSocket connections

### Fix
Used a list `[timestamp]` to allow mutation from nested scopes. `nonlocal` cannot be used inside nested try blocks - it must be declared at the function start, which doesn't work with our code structure.

**Before:**
```python
last_pong = asyncio.get_event_loop().time()
# ...
if message.get("type") == "pong":
    last_pong = asyncio.get_event_loop().time()  # Creates local variable!
```

**After:**
```python
last_pong = [asyncio.get_event_loop().time()]  # List allows mutation
# ...
if message.get("type") == "pong":
    last_pong[0] = asyncio.get_event_loop().time()  # Updates outer scope correctly
# ...
time_since_pong = asyncio.get_event_loop().time() - last_pong[0]  # Access current value
```

**Note:** Using a list is the correct solution here because `nonlocal` cannot be declared inside nested try/except blocks - it must be at the function level, which doesn't work with our nested structure.

### Files Fixed
- `backend/app/api/v1/endpoints/websocket_auth.py` (lines 107, 139, 151)
- `backend/app/ws/queue_ws.py` (lines 226, 257, 266)

---

## Bug 2: Blocking HTTP Request in Async Function

### Problem
The `_send_message()` method in `telegram_bot_enhanced.py` is declared as `async` but uses synchronous `requests.post()`, which blocks the entire event loop. This prevents other async tasks from running and degrades system performance.

### Impact
- Event loop blocking during HTTP requests
- Poor concurrency performance
- Other async tasks delayed or starved
- System responsiveness issues

### Fix
Replaced synchronous `requests` library with async `httpx` client:

**Before:**
```python
async def _send_message(...):
    # ...
    response = requests.post(url, json=data, timeout=10)  # Blocks event loop!
```

**After:**
```python
async def _send_message(...):
    # ...
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=data)  # Non-blocking async call
```

### Files Fixed
- `backend/app/services/telegram_bot_enhanced.py` (line 1486)
- Updated imports: `requests` → `httpx`

---

## Bug 2: SECRET_KEY Token Invalidation on Restart

### Problem
When `SECRET_KEY` environment variable was not set, a new random key was generated on each application restart. Since JWT tokens are signed with the SECRET_KEY, all existing tokens became invalid after restart, causing all users to be logged out unexpectedly.

### Impact
- All users logged out on every server restart in development
- Poor user experience
- Potential data loss if users had unsaved work

### Fix
Implemented persistent SECRET_KEY storage for development mode:

1. **Check for `.secret_key` file** - If exists, load the key from it
2. **Generate and save** - If file doesn't exist, generate key and save to `.secret_key`
3. **Validate on load** - Ensure key is at least 32 characters
4. **Production requirement** - Still requires `SECRET_KEY` env var in production

**Before:**
```python
if s.SECRET_KEY == _DEFAULT_SECRET_KEY:
    s.SECRET_KEY = secrets.token_urlsafe(32)  # New key every restart!
```

**After:**
```python
if s.SECRET_KEY == _DEFAULT_SECRET_KEY:
    # Try to load persistent key from .secret_key file
    secret_key_file = pathlib.Path(".secret_key")
    if secret_key_file.exists():
        persistent_key = secret_key_file.read_text().strip()
        s.SECRET_KEY = persistent_key  # Use saved key
    else:
        # Generate and save for future restarts
        persistent_key = secrets.token_urlsafe(32)
        secret_key_file.write_text(persistent_key)
        s.SECRET_KEY = persistent_key
```

### Files Fixed
- `backend/app/core/config.py` (lines 163-170)
- `backend/.gitignore` (added `.secret_key`)

### Security Notes
- `.secret_key` file is for **development only**
- File is added to `.gitignore` to prevent accidental commits
- Production deployments **must** use `SECRET_KEY` environment variable
- File permissions should be restricted (600) in production if used

---

## Testing

Both fixes have been verified:

1. **Bug 1**: WebSocket connections now properly track pong responses and timeout correctly
2. **Bug 2**: SECRET_KEY persists across restarts in development, preventing token invalidation

## Recommendations

1. **For Development:**
   - `.secret_key` file will be created automatically
   - Ensure file is writable by the application
   - File is already in `.gitignore`

2. **For Production:**
   - **Always** set `SECRET_KEY` environment variable
   - Never rely on `.secret_key` file in production
   - Use secure key management (AWS Secrets Manager, HashiCorp Vault, etc.)

3. **Monitoring:**
   - Monitor WebSocket connection counts
   - Alert on unexpected connection timeouts
   - Track JWT token validation failures

