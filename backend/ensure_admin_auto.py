# ensure_admin_auto.py
# Универсальный сид/сброс пароля admin/admin для FastAPI + SQLAlchemy.
# Поддерживает sync и async пути. Игнорирует неподготовленный app.db.session.sessionmaker.
# Запуск:
#   .venv\Scripts\python.exe ensure_admin_auto.py
import asyncio
import os
import sys
import traceback
import types

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")

print(f"[ensure_admin_auto] target user: {ADMIN_USERNAME}")

# --- парольный хэш ---
try:
    from passlib.context import CryptContext

    pwdctx = CryptContext(
        schemes=["bcrypt", "sha256_crypt", "pbkdf2_sha256"], deprecated="auto"
    )

    def make_hash(p):
        return pwdctx.hash(p)

    print("[ensure_admin_auto] using passlib for password hashing")
except Exception:
    import hashlib

    def make_hash(p):
        return "plain$" + hashlib.sha256(p.encode("utf-8")).hexdigest()

    print(
        "[ensure_admin_auto] passlib not available; falling back to sha256 (may be incompatible)"
    )

# --- попробовать импортировать User модель ---
UserModel = None
user_candidates = [
    "app.models.user.User",
    "app.models.users.User",
    "app.models.User",
    "app.db.models.user.User",
]


def try_import(path):
    try:
        mod, attr = path.rsplit(".", 1)
        m = __import__(mod, fromlist=[attr])
        return getattr(m, attr)
    except Exception:
        return None


for p in user_candidates:
    obj = try_import(p)
    if obj:
        UserModel = obj
        print("[ensure_admin_auto] found User model:", p)
        break
if not UserModel:
    print("[ensure_admin_auto][FATAL] cannot find User model. Tried:", user_candidates)
    sys.exit(2)

# --- найти фабрику/способ получить сессию в app.db.session ---
dbs = None
try:
    import app.db.session as dbs

    print("[ensure_admin_auto] imported app.db.session")
except Exception as e:
    print("[ensure_admin_auto][FATAL] cannot import app.db.session:", e)
    sys.exit(3)


# helpers to detect async
def is_async_callable(obj):
    import inspect

    return inspect.iscoroutinefunction(obj) or inspect.isasyncgenfunction(obj)


def has_attr(o, name):
    return getattr(o, name, None) is not None


# приоритет: get_db (sync generator) -> SessionLocal (sync sessionmaker) -> engine+sessionmaker (sync)
#            -> get_async_session (async gen) -> AsyncSessionLocal/async_session_maker (async)
sync_strategy = None
async_strategy = None

# 1) get_db (часто sync-генератор)
get_db = getattr(dbs, "get_db", None)
if get_db and isinstance(get_db, types.FunctionType) and not is_async_callable(get_db):
    sync_strategy = "get_db"
    print("[ensure_admin_auto] will use sync get_db()")

# 2) SessionLocal (часто sessionmaker(bind=engine))
SessionLocal = getattr(dbs, "SessionLocal", None)
if not sync_strategy and SessionLocal:
    # важно: игнорировать 'sessionmaker' если это импортированный класс/функция SQLA, а не инстанс
    if (
        SessionLocal.__class__.__name__ == "sessionmaker"
        or "sessionmaker" in str(type(SessionLocal)).lower()
    ):
        sync_strategy = "SessionLocal"
        print("[ensure_admin_auto] will use sync SessionLocal()")
    else:
        # если это не sessionmaker, но что-то callable — всё равно попробуем как фабрику
        if callable(SessionLocal):
            sync_strategy = "SessionLocal"
            print("[ensure_admin_auto] will use callable SessionLocal()")

# 3) engine + sessionmaker (когда SessionLocal отсутствует)
if not sync_strategy:
    engine = getattr(dbs, "engine", None)
    try:
        from sqlalchemy.orm import sessionmaker as sa_sessionmaker
    except Exception:
        sa_sessionmaker = None
    if engine and sa_sessionmaker:
        try:
            SessionLocal2 = sa_sessionmaker(
                bind=engine, autoflush=False, autocommit=False
            )
            sync_strategy = "engine_sessionmaker"
            SessionLocal = SessionLocal2
            print("[ensure_admin_auto] built SessionLocal from engine/sessionmaker")
        except Exception:
            pass

# --- async варианты ---
get_async_session = getattr(dbs, "get_async_session", None)
if get_async_session and is_async_callable(get_async_session):
    async_strategy = "get_async_session"
    print("[ensure_admin_auto] async path available: get_async_session()")

AsyncSessionLocal = getattr(dbs, "AsyncSessionLocal", None)
if not async_strategy and AsyncSessionLocal and callable(AsyncSessionLocal):
    async_strategy = "AsyncSessionLocal"
    print("[ensure_admin_auto] async path available: AsyncSessionLocal()")

async_session_maker = getattr(dbs, "async_session_maker", None) or getattr(
    dbs, "async_session", None
)
if not async_strategy and async_session_maker and callable(async_session_maker):
    async_strategy = "async_session_maker"
    print("[ensure_admin_auto] async path available: async_session_maker()")

from sqlalchemy import select


def upsert_sync(session):
    # догадаемся о поле логина
    uname_field = (
        "username"
        if hasattr(UserModel, "username")
        else ("login" if hasattr(UserModel, "login") else None)
    )
    if not uname_field:
        uname_field = "username"
    print("[ensure_admin_auto] sync upsert using field:", uname_field)
    try:
        res = session.execute(
            select(UserModel).where(getattr(UserModel, uname_field) == ADMIN_USERNAME)
        )
        user = res.scalar_one_or_none()
    except Exception:
        traceback.print_exc()
        user = None

    hashed = make_hash(ADMIN_PASSWORD)
    if user:
        print("[ensure_admin_auto] updating existing admin (sync)")
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
        print("[ensure_admin_auto] updated (sync)")
    else:
        print("[ensure_admin_auto] creating new admin (sync)")
        kwargs = {}
        if "username" in UserModel.__dict__:
            kwargs["username"] = ADMIN_USERNAME
        if "login" in UserModel.__dict__ and "username" not in kwargs:
            kwargs["login"] = ADMIN_USERNAME
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
        u = UserModel(**kwargs)
        session.add(u)
        session.commit()
        print("[ensure_admin_auto] created (sync)")


async def upsert_async(session):
    uname_field = (
        "username"
        if hasattr(UserModel, "username")
        else ("login" if hasattr(UserModel, "login") else None)
    )
    if not uname_field:
        uname_field = "username"
    print("[ensure_admin_auto] async upsert using field:", uname_field)
    try:
        res = await session.execute(
            select(UserModel).where(getattr(UserModel, uname_field) == ADMIN_USERNAME)
        )
        user = res.scalar_one_or_none()
    except Exception:
        traceback.print_exc()
        user = None

    hashed = make_hash(ADMIN_PASSWORD)
    if user:
        print("[ensure_admin_auto] updating existing admin (async)")
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
        print("[ensure_admin_auto] updated (async)")
    else:
        print("[ensure_admin_auto] creating new admin (async)")
        kwargs = {}
        if "username" in UserModel.__dict__:
            kwargs["username"] = ADMIN_USERNAME
        if "login" in UserModel.__dict__ and "username" not in kwargs:
            kwargs["login"] = ADMIN_USERNAME
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
        u = UserModel(**kwargs)
        session.add(u)
        await session.commit()
        print("[ensure_admin_auto] created (async)")


async def main():
    # Сначала пробуем SYNC стратегии
    if sync_strategy == "get_db":
        print("[ensure_admin_auto] using sync get_db()")
        gen = get_db()
        session = next(gen)  # взять первую выдачу из генератора
        try:
            upsert_sync(session)
        finally:
            try:
                next(gen)  # корректно закрыть генератор
            except StopIteration:
                pass
        return 0

    if sync_strategy in ("SessionLocal", "engine_sessionmaker"):
        try:
            sess = SessionLocal()
            try:
                upsert_sync(sess)
            finally:
                try:
                    sess.close()
                except:
                    pass
            return 0
        except Exception:
            traceback.print_exc()

    # Если sync не получилось — пробуем ASYNC
    if async_strategy == "get_async_session":
        print("[ensure_admin_auto] using async get_async_session()")
        async for s in get_async_session():
            await upsert_async(s)
        return 0

    if async_strategy in ("AsyncSessionLocal", "async_session_maker"):
        try:
            async with (
                AsyncSessionLocal()
                if async_strategy == "AsyncSessionLocal"
                else async_session_maker()
            ) as s:
                await upsert_async(s)
            return 0
        except Exception:
            traceback.print_exc()

    print(
        "[ensure_admin_auto][FATAL] no suitable session strategy found. Check app.db.session contents."
    )
    return 4


if __name__ == "__main__":
    try:
        code = asyncio.run(main())
        sys.exit(code)
    except Exception:
        traceback.print_exc()
        sys.exit(10)
