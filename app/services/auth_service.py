import time
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.models.character import Character
from app.models.equipment import CharacterEquipment
from app.models.job_mastery import JobMastery
from app.models.login_log import LoginLog


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(character_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": character_id, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def authenticate(db: Session, character_id: str, password: str, host: str) -> Character | None:
    character = db.query(Character).filter(Character.id == character_id).first()
    success = False
    if character and verify_password(password, character.password_hash):
        success = True

    log = LoginLog(
        character_id=character_id,
        password_attempt="***",
        host=host,
        timestamp=int(time.time()),
        success=1 if success else 0,
    )
    db.add(log)
    db.commit()

    return character if success else None


def register_character(
    db: Session,
    character_id: str,
    password: str,
    password_recovery: str,
    name: str,
    site_name: str,
    url: str,
    sex: int,
    image_id: int,
    job_class: int,
    host: str,
) -> Character:
    character = Character(
        id=character_id,
        password_hash=hash_password(password),
        password_recovery=password_recovery,
        name=name,
        site_name=site_name,
        url=url,
        sex=sex,
        image_id=image_id,
        job_class=job_class,
        level=1,
        current_hp=100,
        max_hp=100,
        str_=10,
        mag=10,
        fai=10,
        vit=10,
        dex=10,
        spd=10,
        cha=10,
        host=host,
        available_battles=settings.sentou_limit,
    )
    db.add(character)

    equipment = CharacterEquipment(character_id=character_id)
    db.add(equipment)

    mastery = JobMastery(character_id=character_id, job_class=job_class, mastery_level=0)
    db.add(mastery)

    db.commit()
    db.refresh(character)
    return character
