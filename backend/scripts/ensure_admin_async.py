from __future__ import annotations

import asyncio
from sqlalchemy import select

# Универсальные импорты сессии
try:
    from app.db.session import async_session as SessionMaker  # type: ignore
except Exception:
    from app.db.session import SessionLocal as SessionMaker  # type: ignore

from app.models.user import User
from app.core.security import get_password_hash

USERNAME = "admin"
PASSWORD = "admin"
EMAIL = "admin@example.com"

async def main():
    async with SessionMaker() as session:  # type: ignore
        res = await session.execute(select(User).where(User.username == USERNAME))
        user = res.scalars().first()
        if user:
            print("✅ Admin already exists.")
            return
        user = User(
            username=USERNAME,
            email=EMAIL,
            full_name="Administrator",
            is_active=True,
            is_superuser=True,
            hashed_password=get_password_hash(PASSWORD),
        )
        session.add(user)
        await session.commit()
        print("✅ Admin user created:", USERNAME, "/", PASSWORD)

if __name__ == "__main__":
    asyncio.run(main())
