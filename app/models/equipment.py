from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class CharacterEquipment(Base):
    __tablename__ = "character_equipment"

    character_id = Column(String(32), ForeignKey("characters.id", ondelete="CASCADE"), primary_key=True)

    # 武器
    weapon_name = Column(String(64), default="徒手")
    weapon_attack = Column(Integer, default=0)
    weapon_accuracy = Column(Integer, default=0)

    # 防具
    armor_name = Column(String(64), default="布衣")
    armor_defense = Column(Integer, default=0)
    armor_evasion = Column(Integer, default=0)

    # 飾品
    accessory_name = Column(String(64), default="無")
    accessory_skill_id = Column(Integer, default=0)
    acs_str = Column(Integer, default=0)
    acs_mag = Column(Integer, default=0)
    acs_fai = Column(Integer, default=0)
    acs_vit = Column(Integer, default=0)
    acs_dex = Column(Integer, default=0)
    acs_spd = Column(Integer, default=0)
    acs_cha = Column(Integer, default=0)
    acs_karma = Column(Integer, default=0)
    acs_accuracy = Column(Integer, default=0)
    acs_evasion = Column(Integer, default=0)
    acs_critical = Column(Integer, default=0)

    character = relationship("Character", back_populates="equipment")
