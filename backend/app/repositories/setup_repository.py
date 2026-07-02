from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.clinic import Branch, ClinicSettings
from app.models.user import User


class SetupRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_setting(self, key: str) -> ClinicSettings | None:
        return (
            self.db.execute(select(ClinicSettings).where(ClinicSettings.key == key))
            .scalars()
            .first()
        )

    def count_branches(self) -> int:
        return int(self.db.execute(select(func.count(Branch.id))).scalar() or 0)

    def count_active_admins(self) -> int:
        return int(
            self.db.execute(
                select(func.count(User.id)).where(
                    User.role == "Admin",
                    User.is_active == True,
                )
            ).scalar()
            or 0
        )

    def get_existing_branch_codes(self) -> set[str]:
        rows = self.db.execute(select(Branch.code)).scalars().all()
        return {str(code).lower() for code in rows if code}

    def find_user_by_username(self, username: str) -> User | None:
        return (
            self.db.execute(select(User).where(User.username == username))
            .scalars()
            .first()
        )

    def find_user_by_email(self, email: str) -> User | None:
        return (
            self.db.execute(select(User).where(User.email == email))
            .scalars()
            .first()
        )
