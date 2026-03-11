"""NPC 模擬角色產生服務。"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.engine.level_up import check_level_up
from app.models.champion import Champion
from app.models.character import Character
from app.models.equipment import CharacterEquipment
from app.models.item_catalog import AccessoryCatalog, ArmorCatalog, WeaponCatalog
from app.models.job_mastery import JobMastery

_NPC_NAMES = [
    "影武者", "蒼穹騎士", "月光巫女", "紅蓮導士", "鉄壁衛士",
    "風來盜賊", "星詠賢者", "暁の勇者", "黒翼天使", "白銀聖騎",
    "翠風弓手", "紫電忍者", "金剛武僧", "碧海召喚", "朱雀使者",
    "玄武守護", "青龍劍士", "白虎鬥士", "天狼戰士", "地龍騎兵",
    "冰霜魔女", "烈焰鬥神", "雷鳴劍聖", "幻影刺客", "大地守人",
    "深淵魔導", "光明導師", "闇夜獵手", "蒼天武神", "銀翼詩人",
    "黃金騎士", "鑽石賢者", "翡翠巫師", "紅寶鬥士", "藍寶射手",
    "鋼鉄戰車", "疾風斥候", "烈日武士", "月影暗殺", "星塵魔人",
    "雲海仙人", "森林精靈", "沙漠遊俠", "海原水手", "火山鍛冶",
    "極光術士", "暴風騎兵", "大地巨人", "深海龍王", "天空城主",
]

_jobs_cache: dict | None = None


def _load_jobs() -> dict:
    global _jobs_cache
    if _jobs_cache is None:
        path = Path(__file__).parent.parent.parent / "data" / "jobs.json"
        with open(path, encoding="utf-8") as f:
            _jobs_cache = json.load(f)
    return _jobs_cache


def _next_npc_number(db: Session) -> int:
    """查詢 DB 中 npc_ 前綴角色的最大編號。"""
    last = (
        db.query(Character.id)
        .filter(Character.id.like("npc_%"))
        .order_by(Character.id.desc())
        .first()
    )
    if not last:
        return 1
    try:
        return int(last[0].replace("npc_", "")) + 1
    except ValueError:
        return 1


def _pick_name(db: Session, used: set[str]) -> str:
    """從名稱池中選一個不重複的名稱。"""
    existing = {n for n, in db.query(Character.name).all()}
    taken = existing | used
    available = [n for n in _NPC_NAMES if n not in taken]
    if available:
        return random.choice(available)
    # 名稱池用完，加數字後綴
    for i in range(1, 9999):
        candidate = f"{random.choice(_NPC_NAMES)}・{i}"
        if candidate not in taken:
            return candidate
    return f"NPC_{random.randint(10000, 99999)}"


def _level_to_tier(level: int) -> int:
    if level < 20:
        return 1
    if level < 50:
        return 2
    if level < 100:
        return 3
    if level < 200:
        return 4
    return 5


def _equip_npc(db: Session, char_id: str, level: int, mode: str) -> CharacterEquipment:
    """依等級和模式從 catalog 中選配裝備。"""
    eq = CharacterEquipment(character_id=char_id)
    if mode == "none":
        return eq

    tier = _level_to_tier(level)

    # 武器
    weapons = db.query(WeaponCatalog).filter(WeaponCatalog.shop_tier <= tier).all()
    if weapons:
        w = max(weapons, key=lambda x: x.attack) if mode == "best" else random.choice(weapons)
        eq.weapon_name = w.name
        eq.weapon_attack = w.attack
        eq.weapon_accuracy = w.accuracy_bonus

    # 防具
    armors = db.query(ArmorCatalog).filter(ArmorCatalog.shop_tier <= tier).all()
    if armors:
        a = max(armors, key=lambda x: x.defense) if mode == "best" else random.choice(armors)
        eq.armor_name = a.name
        eq.armor_defense = a.defense
        eq.armor_evasion = a.evasion_bonus

    # 飾品
    accessories = db.query(AccessoryCatalog).filter(AccessoryCatalog.shop_tier <= tier).all()
    if accessories:
        ac = random.choice(accessories)
        eq.accessory_name = ac.name
        eq.accessory_skill_id = ac.skill_id
        eq.acs_str = ac.str_bonus
        eq.acs_mag = ac.mag_bonus
        eq.acs_fai = ac.fai_bonus
        eq.acs_vit = ac.vit_bonus
        eq.acs_dex = ac.dex_bonus
        eq.acs_spd = ac.spd_bonus
        eq.acs_cha = ac.cha_bonus
        eq.acs_karma = ac.karma_bonus
        eq.acs_accuracy = ac.accuracy_bonus
        eq.acs_evasion = ac.evasion_bonus
        eq.acs_critical = ac.critical_bonus

    return eq


def generate_npcs(
    db: Session,
    count: int,
    target_level: int,
    job_classes: list[int] | None = None,
    equip_tier: str = "auto",
    set_as_champion: bool = False,
) -> list[dict]:
    """產生模擬 NPC 角色。回傳已建立的角色摘要列表。"""
    jobs = _load_jobs()
    count = max(1, min(count, 32))
    target_level = max(1, min(target_level, settings.chara_max_lv))

    if not job_classes:
        job_classes = list(range(14))  # 基礎職業 0-13

    # 計算升到目標等級所需的總 exp
    total_exp = sum(lv * settings.lv_up for lv in range(1, target_level))

    start_num = _next_npc_number(db)
    used_names: set[str] = set()
    results = []

    for i in range(count):
        npc_id = f"npc_{start_num + i:03d}"
        npc_name = _pick_name(db, used_names)
        used_names.add(npc_name)
        job_class = random.choice(job_classes)

        # 模擬成長
        base_stats = {"str": 10, "mag": 10, "fai": 10, "vit": 10,
                      "dex": 10, "spd": 10, "cha": 10, "karma": 0}
        new_lv, new_exp, new_stats, new_hp = check_level_up(
            level=1, exp=total_exp, job_class=job_class,
            stats=base_stats, max_hp=100,
        )

        job_name = jobs.get(str(job_class), {}).get("name", "不明")
        job_level = min(target_level, 60)

        char = Character(
            id=npc_id,
            password_hash="$NPC$",
            name=npc_name,
            sex=random.randint(0, 1),
            image_id=random.randint(0, 9),
            str_=new_stats["str"],
            mag=new_stats["mag"],
            fai=new_stats["fai"],
            vit=new_stats["vit"],
            dex=new_stats["dex"],
            spd=new_stats["spd"],
            cha=new_stats["cha"],
            karma=new_stats["karma"],
            job_class=job_class,
            current_hp=new_hp,
            max_hp=new_hp,
            exp=new_exp,
            level=new_lv,
            gold=random.randint(1000, 100000),
            battle_count=random.randint(10, 500),
            win_count=random.randint(5, 250),
            available_battles=settings.sentou_limit,
            last_battle_time=int(time.time()),
            tactic_id=0,
            job_level=job_level,
            protected=1,
            password_recovery="npc",
        )
        db.add(char)
        db.flush()  # 確保 FK 可用

        eq = _equip_npc(db, npc_id, target_level, equip_tier)
        db.add(eq)

        mastery = JobMastery(
            character_id=npc_id,
            job_class=job_class,
            mastery_level=job_level,
        )
        db.add(mastery)

        results.append({
            "id": npc_id,
            "name": npc_name,
            "level": new_lv,
            "job": job_name,
            "hp": new_hp,
            "weapon": eq.weapon_name,
            "atk": eq.weapon_attack,
            "armor": eq.armor_name,
            "def": eq.armor_defense,
        })

    # 設為冠軍
    if set_as_champion and results:
        first_id = results[0]["id"]
        first_char = db.query(Character).get(first_id)
        first_eq = db.query(CharacterEquipment).get(first_id)
        _set_as_champion(db, first_char, first_eq)

    db.commit()
    return results


def _set_as_champion(db: Session, char: Character, eq: CharacterEquipment | None) -> None:
    """將指定角色設為冠軍。"""
    from app.services.battle_service import _make_champion_snapshot

    champ = db.query(Champion).first()
    if not champ:
        champ = Champion(id=1)
        db.add(champ)
    champ.character_id = char.id
    champ.character_name = char.name
    champ.win_streak = 0
    champ.bounty = 1000
    champ.snapshot_json = _make_champion_snapshot(char, eq)


def delete_all_npcs(db: Session) -> int:
    """刪除所有 NPC 角色，回傳刪除數量。"""
    count = db.query(Character).filter(Character.id.like("npc_%")).count()
    db.query(Character).filter(Character.id.like("npc_%")).delete(synchronize_session="fetch")
    db.commit()
    return count
