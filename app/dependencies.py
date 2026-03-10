from typing import Generator

from fastapi import Cookie, Depends, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.character import Character


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Cookie(default=None, alias="ffa_token"),
) -> Character:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登入")
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        character_id: str = payload.get("sub")
        if character_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="無效的 token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="無效的 token")

    character = db.query(Character).filter(Character.id == character_id).first()
    if character is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="角色不存在")
    return character


def get_optional_user(
    db: Session = Depends(get_db),
    token: str = Cookie(default=None, alias="ffa_token"),
) -> Character | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        character_id = payload.get("sub")
        if character_id:
            return db.query(Character).filter(Character.id == character_id).first()
    except JWTError:
        pass
    return None
