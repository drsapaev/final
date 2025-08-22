from sqlalchemy.orm import Session
from app.models.user import User


# Получение пользователя по ID
def get_user_by_id(db: Session, user_id: int) -> User | None:
	return db.query(User).filter(User.id == user_id).first()


# Получение пользователя по username
def get_user_by_username(db: Session, username: str) -> User | None:
	return db.query(User).filter(User.username == username).first()