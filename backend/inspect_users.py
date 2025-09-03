# inspect_users.py
import asyncio
import traceback

candidates_session = [
    "app.db.session.get_async_session",
    "app.db.session.async_session_maker",
    "app.db.session.AsyncSessionLocal",
    "app.db.session.async_session",
    "app.db.session.get_db",
    "app.db.session.sessionmaker",
    "app.db.session.SessionLocal",
]
candidates_user = [
    "app.models.user.User",
    "app.models.users.User",
    "app.models.User",
]


def try_import(path):
    try:
        module_path, attr = path.rsplit(".", 1)
        m = __import__(module_path, fromlist=[attr])
        return getattr(m, attr)
    except Exception:
        return None


async def run_async():
    SessionCandidate = None
    get_async_session = None
    for p in candidates_session:
        obj = try_import(p)
        if obj:
            print("Found session candidate:", p)
            if p.endswith("get_async_session"):
                get_async_session = obj
            else:
                SessionCandidate = obj
            break

    UserModel = None
    for p in candidates_user:
        u = try_import(p)
        if u:
            UserModel = u
            print("Found User model:", p)
            break

    if not UserModel:
        print("No User model auto-detected; check app/models/ or share path.")
        return

    if get_async_session:
        try:
            async for session in get_async_session():
                q = await session.execute(UserModel.__table__.select().limit(50))
                rows = q.fetchall()
                print("Users (async, up to 50):")
                for r in rows:
                    print(dict(r))
                return
        except Exception:
            traceback.print_exc()

    # try sync sessionmaker path in thread
    import concurrent.futures
    import inspect

    def sync_job():
        try:
            # if SessionCandidate is sessionmaker class
            S = SessionCandidate
            sess = S()
            try:
                q = sess.execute(UserModel.__table__.select().limit(50))
                rows = q.fetchall()
                print("Users (sync, up to 50):")
                for r in rows:
                    print(dict(r))
            finally:
                try:
                    sess.close()
                except:
                    pass
        except Exception:
            traceback.print_exc()

    with concurrent.futures.ThreadPoolExecutor() as ex:
        await asyncio.get_running_loop().run_in_executor(ex, sync_job)


if __name__ == "__main__":
    asyncio.run(run_async())
