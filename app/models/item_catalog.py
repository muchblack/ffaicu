from sqlalchemy import BigInteger, Column, Integer, String

from app.database import Base


class WeaponCatalog(Base):
    __tablename__ = "weapon_catalog"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False)
    attack = Column(Integer, default=0)
    price = Column(BigInteger, default=0)
    accuracy_bonus = Column(Integer, default=0)
    shop_tier = Column(Integer, default=0)


class ArmorCatalog(Base):
    __tablename__ = "armor_catalog"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False)
    defense = Column(Integer, default=0)
    price = Column(BigInteger, default=0)
    evasion_bonus = Column(Integer, default=0)
    shop_tier = Column(Integer, default=0)


class AccessoryCatalog(Base):
    __tablename__ = "accessory_catalog"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False)
    price = Column(BigInteger, default=0)
    skill_id = Column(Integer, default=0)
    str_bonus = Column(Integer, default=0)
    mag_bonus = Column(Integer, default=0)
    fai_bonus = Column(Integer, default=0)
    vit_bonus = Column(Integer, default=0)
    dex_bonus = Column(Integer, default=0)
    spd_bonus = Column(Integer, default=0)
    cha_bonus = Column(Integer, default=0)
    karma_bonus = Column(Integer, default=0)
    accuracy_bonus = Column(Integer, default=0)
    evasion_bonus = Column(Integer, default=0)
    critical_bonus = Column(Integer, default=0)
    description = Column(String(256), default="")
    shop_tier = Column(Integer, default=0)
