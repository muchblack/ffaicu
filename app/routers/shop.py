from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.character import Character
from app.models.item_catalog import AccessoryCatalog, ArmorCatalog, WeaponCatalog
from app.services.shop_service import (
    buy_accessory,
    buy_armor,
    buy_weapon,
    sell_accessory,
    sell_armor,
    sell_weapon,
)

router = APIRouter(prefix="/shop", tags=["商店"])


class BuyRequest(BaseModel):
    item_id: int


# --- 武器商店 ---
@router.get("/weapon")
def list_weapons(db: Session = Depends(get_db), current_user: Character = Depends(get_current_user)):
    items = db.query(WeaponCatalog).order_by(WeaponCatalog.price).all()
    return [{"id": w.id, "name": w.name, "attack": w.attack, "price": w.price} for w in items]


@router.post("/weapon/buy")
def weapon_buy(req: BuyRequest, db: Session = Depends(get_db), current_user: Character = Depends(get_current_user)):
    return buy_weapon(db, current_user, req.item_id)


@router.post("/weapon/sell")
def weapon_sell(db: Session = Depends(get_db), current_user: Character = Depends(get_current_user)):
    return sell_weapon(db, current_user)


# --- 防具商店 ---
@router.get("/armor")
def list_armors(db: Session = Depends(get_db), current_user: Character = Depends(get_current_user)):
    items = db.query(ArmorCatalog).order_by(ArmorCatalog.price).all()
    return [{"id": a.id, "name": a.name, "defense": a.defense, "price": a.price} for a in items]


@router.post("/armor/buy")
def armor_buy(req: BuyRequest, db: Session = Depends(get_db), current_user: Character = Depends(get_current_user)):
    return buy_armor(db, current_user, req.item_id)


@router.post("/armor/sell")
def armor_sell(db: Session = Depends(get_db), current_user: Character = Depends(get_current_user)):
    return sell_armor(db, current_user)


# --- 飾品商店 ---
@router.get("/accessory")
def list_accessories(db: Session = Depends(get_db), current_user: Character = Depends(get_current_user)):
    items = db.query(AccessoryCatalog).order_by(AccessoryCatalog.price).all()
    return [
        {"id": a.id, "name": a.name, "price": a.price, "description": a.description}
        for a in items
    ]


@router.post("/accessory/buy")
def accessory_buy(req: BuyRequest, db: Session = Depends(get_db), current_user: Character = Depends(get_current_user)):
    return buy_accessory(db, current_user, req.item_id)


@router.post("/accessory/sell")
def accessory_sell(db: Session = Depends(get_db), current_user: Character = Depends(get_current_user)):
    return sell_accessory(db, current_user)
