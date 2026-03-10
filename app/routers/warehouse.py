from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_current_user, get_db
from app.models.character import Character
from app.models.warehouse import WarehouseItem

router = APIRouter(prefix="/warehouse", tags=["倉庫"])


class StoreRequest(BaseModel):
    item_type: str = Field(pattern=r"^(weapon|armor|accessory)$")
    catalog_id: int


class RetrieveRequest(BaseModel):
    warehouse_item_id: int


@router.get("")
def list_warehouse(
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    items = (
        db.query(WarehouseItem)
        .filter(WarehouseItem.character_id == current_user.id)
        .order_by(WarehouseItem.item_type, WarehouseItem.slot_index)
        .all()
    )
    return [
        {"id": w.id, "item_type": w.item_type, "catalog_id": w.catalog_id, "slot": w.slot_index}
        for w in items
    ]


@router.post("/store")
def store_item(
    req: StoreRequest,
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    count = (
        db.query(WarehouseItem)
        .filter(WarehouseItem.character_id == current_user.id, WarehouseItem.item_type == req.item_type)
        .count()
    )
    max_slots = settings.item_max
    if count >= max_slots:
        raise HTTPException(status_code=400, detail=f"倉庫已滿（最多{max_slots}個）")

    item = WarehouseItem(
        character_id=current_user.id,
        item_type=req.item_type,
        catalog_id=req.catalog_id,
        slot_index=count,
    )
    db.add(item)
    db.commit()
    return {"message": "已存入倉庫", "id": item.id}


@router.post("/retrieve")
def retrieve_item(
    req: RetrieveRequest,
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    item = (
        db.query(WarehouseItem)
        .filter(WarehouseItem.id == req.warehouse_item_id, WarehouseItem.character_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="找不到物品")

    db.delete(item)
    db.commit()
    return {"message": "已從倉庫取出", "item_type": item.item_type, "catalog_id": item.catalog_id}
