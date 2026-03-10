"""商店服務層。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import settings
from app.models.character import Character
from app.models.equipment import CharacterEquipment
from app.models.item_catalog import AccessoryCatalog, ArmorCatalog, WeaponCatalog


def buy_weapon(db: Session, char: Character, weapon_id: int) -> dict:
    weapon = db.query(WeaponCatalog).filter(WeaponCatalog.id == weapon_id).first()
    if not weapon:
        return {"error": "找不到武器"}
    if char.gold < weapon.price:
        return {"error": "金幣不足"}

    equip = char.equipment or CharacterEquipment(character_id=char.id)
    char.gold -= weapon.price
    equip.weapon_name = weapon.name
    equip.weapon_attack = weapon.attack
    equip.weapon_accuracy = weapon.accuracy_bonus
    if not char.equipment:
        db.add(equip)
    db.commit()
    return {"message": f"已購買{weapon.name}", "gold": int(char.gold)}


def buy_armor(db: Session, char: Character, armor_id: int) -> dict:
    armor = db.query(ArmorCatalog).filter(ArmorCatalog.id == armor_id).first()
    if not armor:
        return {"error": "找不到防具"}
    if char.gold < armor.price:
        return {"error": "金幣不足"}

    equip = char.equipment or CharacterEquipment(character_id=char.id)
    char.gold -= armor.price
    equip.armor_name = armor.name
    equip.armor_defense = armor.defense
    equip.armor_evasion = armor.evasion_bonus
    if not char.equipment:
        db.add(equip)
    db.commit()
    return {"message": f"已購買{armor.name}", "gold": int(char.gold)}


def buy_accessory(db: Session, char: Character, acs_id: int) -> dict:
    acs = db.query(AccessoryCatalog).filter(AccessoryCatalog.id == acs_id).first()
    if not acs:
        return {"error": "找不到飾品"}
    if char.gold < acs.price:
        return {"error": "金幣不足"}

    equip = char.equipment or CharacterEquipment(character_id=char.id)
    char.gold -= acs.price
    equip.accessory_name = acs.name
    equip.accessory_skill_id = acs.skill_id
    equip.acs_str = acs.str_bonus
    equip.acs_mag = acs.mag_bonus
    equip.acs_fai = acs.fai_bonus
    equip.acs_vit = acs.vit_bonus
    equip.acs_dex = acs.dex_bonus
    equip.acs_spd = acs.spd_bonus
    equip.acs_cha = acs.cha_bonus
    equip.acs_karma = acs.karma_bonus
    equip.acs_accuracy = acs.accuracy_bonus
    equip.acs_evasion = acs.evasion_bonus
    equip.acs_critical = acs.critical_bonus
    if not char.equipment:
        db.add(equip)
    db.commit()
    return {"message": f"已購買{acs.name}", "gold": int(char.gold)}


def sell_weapon(db: Session, char: Character) -> dict:
    equip = char.equipment
    if not equip or equip.weapon_name == "徒手":
        return {"error": "沒有可賣的武器"}
    refund = equip.weapon_attack * 5
    char.gold = min(char.gold + refund, settings.gold_max)
    equip.weapon_name = "徒手"
    equip.weapon_attack = 0
    equip.weapon_accuracy = 0
    db.commit()
    return {"message": f"已賣出武器（{refund}G）", "gold": int(char.gold)}


def sell_armor(db: Session, char: Character) -> dict:
    equip = char.equipment
    if not equip or equip.armor_name == "布衣":
        return {"error": "沒有可賣的防具"}
    refund = equip.armor_defense * 5
    char.gold = min(char.gold + refund, settings.gold_max)
    equip.armor_name = "布衣"
    equip.armor_defense = 0
    equip.armor_evasion = 0
    db.commit()
    return {"message": f"已賣出防具（{refund}G）", "gold": int(char.gold)}


def sell_accessory(db: Session, char: Character) -> dict:
    equip = char.equipment
    if not equip or equip.accessory_name == "無":
        return {"error": "沒有可賣的飾品"}
    refund = equip.acs_str + equip.acs_mag + equip.acs_fai + equip.acs_vit
    refund = max(refund * 10, 100)
    char.gold = min(char.gold + refund, settings.gold_max)
    equip.accessory_name = "無"
    equip.accessory_skill_id = 0
    equip.acs_str = equip.acs_mag = equip.acs_fai = equip.acs_vit = 0
    equip.acs_dex = equip.acs_spd = equip.acs_cha = equip.acs_karma = 0
    equip.acs_accuracy = equip.acs_evasion = equip.acs_critical = 0
    db.commit()
    return {"message": f"已賣出飾品（{refund}G）", "gold": int(char.gold)}
