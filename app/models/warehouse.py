from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class WarehouseItem(Base):
    """統一倉庫表，用 item_type 區分武器/防具/飾品。"""
    __tablename__ = "warehouse_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    character_id = Column(String(32), ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    item_type = Column(String(16), nullable=False)  # "weapon" | "armor" | "accessory"
    catalog_id = Column(Integer, nullable=False)     # 對應 weapon/armor/accessory_catalog.id
    slot_index = Column(Integer, default=0)          # 0-7

    character = relationship("Character", back_populates="warehouse_items")
