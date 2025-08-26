# ensure_admin_flexible.py
# Универсальный сид для создания/сброса admin/admin
# Запуск: .venv\Scripts\python.exe ensure_admin_flexible.py
# Поддерживает как async, так и sync фабрики сессий.

import asyncio
import os
import sys
import traceback

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")

print("ensure_admin_flexible: username=%s" % ADMIN_USERNAME)

# try passlib
try:
    from passlib.context import CryptContext
    pwdctx = CryptContext(schemes=["bcrypt", "sha256_crypt", "pbkdf2_sha256"], deprecated="auto")
except Exception:
    pwdctx = None
    print("Warning: passlib not available. Install with: pip install 'passlib[bcrypt]'.")

candidates_session = [
    "app.db.session.get_async_session",
    "app.db.session.async_session_maker",
    "app.db.session.AsyncSessionLocal",
    "app.db.session.async_session",
    "app.db.session.get_db",
    "app.db.session.sessionmaker",
    "app.db.session.SessionLocal",
    "app.db.session.async_session_factory",
]

candidates_user = [
    "app.models.user.User",
    "app.models.users.User",
    "app.models.models.user.User",
    "app.models.models.User",
    "app.models.User",
    "app.db.models.user.User",
]

def try_import(path):
    try:
        module_path, attr = path.rsplit(".", 1)
        m = __import__(module_path, fromlist=[attr])
        return getattr(m, attr)
    except Exception:
        return None

def make_hash(pwd):
    if pwdctx:
        return pwdctx.hash(pwd)
    else:
        import hashlib
        return "plain$" + hashlib.sha256(pwd.encode("utf8")).hexdigest()

# SYNC helper
def create_or_update_sync(session, UserModel):
    try:
        from sqlalchemy import select
        q = select(UserModel).where(getattr(UserModel, "username", UserModel.email) == ADMIN_USERNAME)
        result = session.execute(q)
        user = result.scalar_one_or_none()
    except Exception:
        # try fallback using typical attribute 'username'
        try:
            from sqlalchemy import select
            q = select(UserModel).where(getattr(UserModel, "username") == ADMIN_USERNAME)
            result = session.execute(q)
            user = result.scalar_one_or_none()
        except Exception:
            user = None

    hashed = make_hash(ADMIN_PASSWORD)

    if user:
        print("Found existing user (sync). Updating password/flags...")
        if hasattr(user, "hashed_password"):
            user.hashed_password = hashed
        elif hasattr(user, "password"):
            user.password = hashed
        if hasattr(user, "is_active"):
            user.is_active = True
        if hasattr(user, "is_superuser"):
            user.is_superuser = True
        if hasattr(user, "email"):
            user.email = ADMIN_EMAIL
        session.add(user)
        session.commit()
        print("Updated existing admin user (sync).")
    else:
        print("No user found (sync). Creating...")
        kwargs = {}
        # try sensible fields
        if "username" in UserModel.__dict__:
            kwargs["username"] = ADMIN_USERNAME
        if "email" in UserModel.__dict__:
            kwargs["email"] = ADMIN_EMAIL
        if "hashed_password" in UserModel.__dict__:
            kwargs["hashed_password"] = hashed
        elif "password" in UserModel.__dict__:
            kwargs["password"] = hashed
        if "is_active" in UserModel.__dict__:
            kwargs["is_active"] = True
        if "is_superuser" in UserModel.__dict__:
            kwargs["is_superuser"] = True
        try:
            newu = UserModel(**kwargs)
            session.add(newu)
            session.commit()
            print("Created admin user (sync).")
        except Exception:
            traceback.print_exc()
            print("Failed to create user (sync).")

# ASYNC helper
async def create_or_update_async(session, UserModel):
    try:
        from sqlalchemy import select
        result = await session.execute(select(UserModel).where(getattr(UserModel, "username", UserModel.email) == ADMIN_USERNAME))
        user = result.scalar_one_or_none()
    except Exception:
        try:
            from sqlalchemy import select
            result = await session.execute(select(UserModel).where(getattr(UserModel, "username") == ADMIN_USERNAME))
            user = result.scalar_one_or_none()
        except Exception:
            user = None

    hashed = make_hash(ADMIN_PASSWORD)

    if user:
        print("Found existing user (async). Updating password/flags...")
        if hasattr(user, "hashed_password"):
            user.hashed_password = hashed
        elif hasattr(user, "password"):
            user.password = hashed
        if hasattr(user, "is_active"):
            user.is_active = True
        if hasattr(user, "is_superuser"):
            user.is_superuser = True
        if hasattr(user, "email"):
            user.email = ADMIN_EMAIL
        session.add(user)
        await session.commit()
        print("Updated existing admin user (async).")
    else:
        print("No user found (async). Creating...")
        kwargs = {}
        if "username" in UserModel.__dict__:
            kwargs["username"] = ADMIN_USERNAME
        if "email" in UserModel.__dict__:
            kwargs["email"] = ADMIN_EMAIL
        if "hashed_password" in UserModel.__dict__:
            kwargs["hashed_password"] = hashed
        elif "password" in UserModel.__dict__:
            kwargs["password"] = hashed
        if "is_active" in UserModel.__dict__:
            kwargs["is_active"] = True
        if "is_superuser" in UserModel.__dict__:
            kwargs["is_superuser"] = True
        try:
            newu = UserModel(**kwargs)
            session.add(newu)
            await session.commit()
            print("Created admin user (async).")
        except Exception:
            traceback.print_exc()
            print("Failed to create user (async).")

async def run():
    session_factory = None
    get_async_session = None
    UserModel = None

    for p in candidates_session:
        obj = try_import(p)
        if obj:
            print("Found session candidate:", p)
            # prefer get_async_session if present
            if p.endswith("get_async_session"):
                get_async_session = obj
                break
            session_factory = obj
            break

    for p in candidates_user:
        obj = try_import(p)
        if obj:
            UserModel = obj
            print("Found User model:", p)
            break

    if not UserModel:
        print("ERROR: Could not find User model. Tried:", candidates_user)
        return 2

    # If explicit async generator exists
    if get_async_session:
        try:
            print("Using get_async_session()")
            async for session in get_async_session():
                await create_or_update_async(session, UserModel)
            return 0
        except Exception:
            traceback.print_exc()
            print("get_async_session failed; will try other options...")

    # If session_factory exists:
    if session_factory:
        # try to call and see if it returns an async context manager or sync session object
        try:
            maybe = session_factory()
            # async session maker may return an object that supports __aenter__
            if hasattr(maybe, "__aenter__") and hasattr(maybe, "__aexit__"):
                # it's an async context manager returned directly (rare)
                try:
                    async with maybe as session:
                        await create_or_update_async(session, UserModel)
                    return 0
                except Exception:
                    traceback.print_exc()
            # if it's a class like sessionmaker, calling produced a Session object (sync)
            if hasattr(maybe, "__enter__") and hasattr(maybe, "__exit__"):
                # sync session
                try:
                    maybe.close()  # close preview instance
                except Exception:
                    pass
                try:
                    print("Detected sync sessionmaker: using sync path")
                    # run sync code in threadpool to avoid blocking event loop
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, sync_wrapper, session_factory, UserModel)
                    return 0
                except Exception:
                    traceback.print_exc()
            # else maybe is coroutine or async factory - try await
            try:
                # if calling returned coroutine/future, await it
                obj = await maybe
                if hasattr(obj, "__aenter__") and hasattr(obj, "__aexit__"):
                    async with obj as session:
                        await create_or_update_async(session, UserModel)
                    return 0
            except Exception:
                pass
        except TypeError:
            # session_factory not callable - try to use it directly as sessionmaker instance
            try:
                print("session_factory is not callable; attempting to use as sessionmaker object")
                # try sync path
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, sync_wrapper, session_factory, UserModel)
                return 0
            except Exception:
                traceback.print_exc()
        except Exception:
            traceback.print_exc()

    print("All attempts failed; please inspect session/model locations.")
    return 4

def sync_wrapper(session_factory, UserModel):
    """Run sync create/update using sync sessionmaker"""
    try:
        # If session_factory is a sessionmaker, calling it returns a Session
        with session_factory() as session:
            create_or_update_sync(session, UserModel)
    except Exception:
        traceback.print_exc()
        raise

if __name__ == "__main__":
    try:
        res = asyncio.run(run())
        sys.exit(res)
    except Exception:
        traceback.print_exc()
        sys.exit(10)
