from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.infrastructure.db.models.user import User
from src.infrastructure.security.jwt_tokens import create_access_token
from src.infrastructure.security.password import hash_password, verify_password


class AuthError(Exception):
    pass


def register_user(db: Session, *, email: str, password: str) -> User:
    normalized = email.strip().lower()
    user = User(email=normalized, hashed_password=hash_password(password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AuthError("Email already registered") from None
    db.refresh(user)
    return user


def authenticate_user(db: Session, *, email: str, password: str) -> User | None:
    normalized = email.strip().lower()
    user = db.scalars(select(User).where(User.email == normalized)).first()
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def issue_access_token(user: User) -> str:
    return create_access_token(subject_user_id=user.id)


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)
