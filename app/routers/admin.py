"""管理後台。"""

import time

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_db
from app.models.character import Character
from app.models.item_catalog import AccessoryCatalog, ArmorCatalog, WeaponCatalog

router = APIRouter(prefix="/admin", tags=["管理"])

ADMIN_PASSWORD = "1111"  # TODO: 移至環境變數


def _check_admin(password: str):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="管理密碼錯誤")


class AdminAuth(BaseModel):
    admin_password: str


class DeleteInactiveRequest(AdminAuth):
    pass


class SearchRequest(AdminAuth):
    query: str


class ProtectRequest(AdminAuth):
    character_id: str


class AddWeaponRequest(AdminAuth):
    id: int
    name: str
    attack: int
    price: int
    accuracy_bonus: int = 0
    shop_tier: int = 0


class AddArmorRequest(AdminAuth):
    id: int
    name: str
    defense: int
    price: int
    evasion_bonus: int = 0
    shop_tier: int = 0


class AddAccessoryRequest(AdminAuth):
    id: int
    name: str
    price: int
    skill_id: int = 0
    str_bonus: int = 0
    mag_bonus: int = 0
    fai_bonus: int = 0
    vit_bonus: int = 0
    dex_bonus: int = 0
    spd_bonus: int = 0
    cha_bonus: int = 0
    karma_bonus: int = 0
    description: str = ""
    shop_tier: int = 0


@router.post("/list-characters")
def list_all(req: AdminAuth, db: Session = Depends(get_db)):
    _check_admin(req.admin_password)
    chars = db.query(Character).order_by(Character.level.desc()).all()
    return [
        {"id": c.id, "name": c.name, "level": c.level, "job_class": c.job_class, "protected": c.protected}
        for c in chars
    ]


@router.post("/search")
def search_character(req: SearchRequest, db: Session = Depends(get_db)):
    _check_admin(req.admin_password)
    char = (
        db.query(Character)
        .filter((Character.id == req.query) | (Character.name == req.query))
        .first()
    )
    if not char:
        raise HTTPException(status_code=404, detail="找不到角色")
    return {
        "id": char.id, "name": char.name, "level": char.level,
        "gold": int(char.gold), "bank": int(char.bank_savings),
        "job_class": char.job_class, "protected": char.protected,
    }


@router.post("/delete-inactive")
def delete_inactive(req: DeleteInactiveRequest, db: Session = Depends(get_db)):
    _check_admin(req.admin_password)
    cutoff = int(time.time()) - settings.limit_days * 86400
    deleted = (
        db.query(Character)
        .filter(Character.last_battle_time < cutoff, Character.protected == 0)
        .delete()
    )
    db.commit()
    return {"message": f"已刪除{deleted}個不活躍角色"}


@router.post("/protect")
def protect_character(req: ProtectRequest, db: Session = Depends(get_db)):
    _check_admin(req.admin_password)
    char = db.query(Character).filter(Character.id == req.character_id).first()
    if not char:
        raise HTTPException(status_code=404, detail="找不到角色")
    char.protected = 1
    db.commit()
    return {"message": f"已保護{char.name}"}


@router.post("/add-weapon")
def add_weapon(req: AddWeaponRequest, db: Session = Depends(get_db)):
    _check_admin(req.admin_password)
    weapon = WeaponCatalog(
        id=req.id, name=req.name, attack=req.attack,
        price=req.price, accuracy_bonus=req.accuracy_bonus, shop_tier=req.shop_tier,
    )
    db.merge(weapon)
    db.commit()
    return {"message": f"已新增/更新武器 {req.name}"}


@router.post("/add-armor")
def add_armor(req: AddArmorRequest, db: Session = Depends(get_db)):
    _check_admin(req.admin_password)
    armor = ArmorCatalog(
        id=req.id, name=req.name, defense=req.defense,
        price=req.price, evasion_bonus=req.evasion_bonus, shop_tier=req.shop_tier,
    )
    db.merge(armor)
    db.commit()
    return {"message": f"已新增/更新防具 {req.name}"}


@router.post("/add-accessory")
def add_accessory(req: AddAccessoryRequest, db: Session = Depends(get_db)):
    _check_admin(req.admin_password)
    acs = AccessoryCatalog(
        id=req.id, name=req.name, price=req.price, skill_id=req.skill_id,
        str_bonus=req.str_bonus, mag_bonus=req.mag_bonus, fai_bonus=req.fai_bonus,
        vit_bonus=req.vit_bonus, dex_bonus=req.dex_bonus, spd_bonus=req.spd_bonus,
        cha_bonus=req.cha_bonus, karma_bonus=req.karma_bonus,
        description=req.description, shop_tier=req.shop_tier,
    )
    db.merge(acs)
    db.commit()
    return {"message": f"已新增/更新飾品 {req.name}"}
