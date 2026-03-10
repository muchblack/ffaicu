#!/usr/bin/env python3
"""從原始 Perl 資料檔案匯入怪物、武器、防具、飾品到 SQLAlchemy DB。"""

from __future__ import annotations

import sys
from pathlib import Path

# 確保 app 可以 import
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
from app.models.champion import Champion
from app.models.item_catalog import AccessoryCatalog, ArmorCatalog, WeaponCatalog
from app.models.monster import Monster

# 原始資料根目錄
PERL_DATA = Path(__file__).parent.parent / "data" / "importData"

# 怪物 zone 對應的 .ini 檔
MONSTER_FILES = {
    "low": "lowmons.ini",
    "normal": "normalmons.ini",
    "high": "highmons.ini",
    "special": "spmons.ini",
    "isekai": "isekaimons.ini",
    "boss0": "bossmons0.ini",
    "boss1": "bossmons1.ini",
    "boss2": "bossmons2.ini",
    "boss3": "bossmons3.ini",
}

# Perl 原始欄位：($mname,$mex,$mrand,$msp,$mdmg,$mkahi,$monstac,$mons_ritu,$mgold)


def _int(s: str, default: int = 0) -> int:
    s = s.strip()
    return int(s) if s else default


def parse_monsters(db: Session) -> int:
    count = 0
    for zone, filename in MONSTER_FILES.items():
        path = PERL_DATA / filename
        if not path.exists():
            print(f"  [跳過] {filename} 不存在")
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            fields = line.split("<>")
            if len(fields) < 9:
                continue
            name = fields[0]
            exp_reward = _int(fields[1])
            damage_range = _int(fields[2])
            speed = _int(fields[3])
            base_damage = _int(fields[4])
            evasion = _int(fields[5])
            skill_id = _int(fields[6])
            critical_rate = _int(fields[7])
            gold_drop = _int(fields[8])
            db.add(Monster(
                zone=zone, name=name, exp_reward=exp_reward,
                damage_range=damage_range, speed=speed, base_damage=base_damage,
                evasion=evasion, skill_id=skill_id, critical_rate=critical_rate,
                gold_drop=gold_drop,
            ))
            count += 1
    db.commit()
    return count


def parse_weapons(db: Session) -> int:
    """item{N}.ini → WeaponCatalog，shop_tier = N（同 ID 取最低 tier）"""
    count = 0
    seen_ids: set[int] = set()
    item_dir = PERL_DATA / "item"
    if not item_dir.exists():
        print("  [跳過] item/ 目錄不存在")
        return 0
    for ini_file in sorted(item_dir.glob("item*.ini")):
        stem = ini_file.stem
        if stem == "item":
            continue
        tier = int(stem.replace("item", ""))
        for line in ini_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            fields = line.split("<>")
            if len(fields) < 5:
                continue
            item_code = _int(fields[0])
            if item_code in seen_ids:
                continue
            seen_ids.add(item_code)
            name = fields[1].strip()
            attack = _int(fields[2])
            price = _int(fields[3])
            accuracy_bonus = _int(fields[4])
            db.add(WeaponCatalog(
                id=item_code, name=name, attack=attack,
                price=price, accuracy_bonus=accuracy_bonus, shop_tier=tier,
            ))
            count += 1
    db.commit()
    return count


def parse_armor(db: Session) -> int:
    """def{N}.ini → ArmorCatalog，shop_tier = N（同 ID 取最低 tier）"""
    count = 0
    seen_ids: set[int] = set()
    def_dir = PERL_DATA / "def"
    if not def_dir.exists():
        print("  [跳過] def/ 目錄不存在")
        return 0
    for ini_file in sorted(def_dir.glob("def*.ini")):
        stem = ini_file.stem
        if stem == "def":
            continue
        tier = int(stem.replace("def", ""))
        for line in ini_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            fields = line.split("<>")
            if len(fields) < 5:
                continue
            item_code = _int(fields[0])
            if item_code in seen_ids:
                continue
            seen_ids.add(item_code)
            name = fields[1].strip()
            defense = _int(fields[2])
            price = _int(fields[3])
            evasion_bonus = _int(fields[4])
            db.add(ArmorCatalog(
                id=item_code, name=name, defense=defense,
                price=price, evasion_bonus=evasion_bonus, shop_tier=tier,
            ))
            count += 1
    db.commit()
    return count


def parse_accessories(db: Session) -> int:
    """acs{N}.ini → AccessoryCatalog，shop_tier = N
    格式: code<>name<>price<>skill_id<>str<>mag<>fai<>vit<>dex<>spd<>cha<>karma<>accuracy<>evasion<>critical<>description
    """
    count = 0
    seen_ids: set[int] = set()
    acs_dir = PERL_DATA / "acs"
    if not acs_dir.exists():
        print("  [跳過] acs/ 目錄不存在")
        return 0
    for ini_file in sorted(acs_dir.glob("acs*.ini")):
        stem = ini_file.stem
        if stem == "acs":
            continue
        tier = int(stem.replace("acs", ""))
        for line in ini_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            fields = line.split("<>")
            if len(fields) < 16:
                continue
            item_code = _int(fields[0])
            if item_code in seen_ids:
                continue  # 同一飾品出現在多個商店，只保留第一次
            seen_ids.add(item_code)
            name = fields[1].strip()
            price = _int(fields[2])
            skill_id = _int(fields[3])
            str_bonus = _int(fields[4])
            mag_bonus = _int(fields[5])
            fai_bonus = _int(fields[6])
            vit_bonus = _int(fields[7])
            dex_bonus = _int(fields[8])
            spd_bonus = _int(fields[9])
            cha_bonus = _int(fields[10])
            karma_bonus = _int(fields[11])
            accuracy_bonus = _int(fields[12])
            evasion_bonus = _int(fields[13])
            critical_bonus = _int(fields[14])
            description = fields[15] if len(fields) > 15 else ""
            db.add(AccessoryCatalog(
                id=item_code, name=name, price=price, skill_id=skill_id,
                str_bonus=str_bonus, mag_bonus=mag_bonus, fai_bonus=fai_bonus,
                vit_bonus=vit_bonus, dex_bonus=dex_bonus, spd_bonus=spd_bonus,
                cha_bonus=cha_bonus, karma_bonus=karma_bonus,
                accuracy_bonus=accuracy_bonus, evasion_bonus=evasion_bonus,
                critical_bonus=critical_bonus, description=description,
                shop_tier=tier,
            ))
            count += 1
    db.commit()
    return count


def seed_champion(db: Session):
    """建立初始冠軍（空位）"""
    existing = db.query(Champion).first()
    if existing:
        print("  冠軍資料已存在，跳過")
        return
    db.add(Champion(id=1, character_id=None, character_name="(空位)", win_streak=0, bounty=1000))
    db.commit()
    print("  初始冠軍位建立完成")


def main():
    print("=== FF Adventure 資料初始化 ===")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 先清除舊資料
        db.query(Monster).delete()
        db.query(WeaponCatalog).delete()
        db.query(ArmorCatalog).delete()
        db.query(AccessoryCatalog).delete()
        db.commit()

        n = parse_monsters(db)
        print(f"怪物匯入: {n} 筆")

        n = parse_weapons(db)
        print(f"武器匯入: {n} 筆")

        n = parse_armor(db)
        print(f"防具匯入: {n} 筆")

        n = parse_accessories(db)
        print(f"飾品匯入: {n} 筆")

        seed_champion(db)
        print("=== 完成 ===")
    finally:
        db.close()


if __name__ == "__main__":
    main()
