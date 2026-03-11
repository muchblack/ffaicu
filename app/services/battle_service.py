"""戰鬥服務層 — 編排戰鬥引擎與資料庫操作。"""

from __future__ import annotations

import json
import random
import time

from sqlalchemy.orm import Session

from app.config import settings
from app.engine.battle_core import BattleEngine
from app.engine.battle_state import (
    AccessoryBonuses,
    BattleMode,
    BattleResult,
    Combatant,
    Stats,
)
from app.engine.level_up import check_level_up
from app.models.champion import Champion
from app.models.character import Character
from app.models.equipment import CharacterEquipment
from app.models.monster import Monster


def _char_to_combatant(char: Character, equip: CharacterEquipment | None) -> Combatant:
    eq = equip or CharacterEquipment()
    # 飾品加成合算到能力值（比照原版 battle.pl L335-342）
    return Combatant(
        name=char.name,
        level=char.level,
        max_hp=char.max_hp,
        current_hp=char.current_hp,
        stats=Stats(
            str_=char.str_ + eq.acs_str, mag=char.mag + eq.acs_mag,
            fai=char.fai + eq.acs_fai, vit=char.vit + eq.acs_vit,
            dex=char.dex + eq.acs_dex, spd=char.spd + eq.acs_spd,
            cha=char.cha + eq.acs_cha, karma=char.karma + eq.acs_karma,
        ),
        job_class=char.job_class,
        job_level=char.job_level,
        weapon_attack=eq.weapon_attack,
        weapon_accuracy=eq.weapon_accuracy,
        armor_defense=eq.armor_defense,
        armor_evasion=eq.armor_evasion,
        accessory=AccessoryBonuses(
            skill_id=eq.accessory_skill_id,
            str_=eq.acs_str, mag=eq.acs_mag, fai=eq.acs_fai, vit=eq.acs_vit,
            dex=eq.acs_dex, spd=eq.acs_spd, cha=eq.acs_cha, karma=eq.acs_karma,
            accuracy=eq.acs_accuracy, evasion=eq.acs_evasion, critical=eq.acs_critical,
        ),
        skill_id=char.skill_id,
        battle_cry=char.battle_cry,
        image_id=char.image_id,
        gold=int(char.gold),
    )


def _champion_to_combatant(champ: Champion) -> Combatant:
    snap = json.loads(champ.snapshot_json) if champ.snapshot_json else {}
    return Combatant(
        name=snap.get("name", champ.character_name),
        level=snap.get("level", 1),
        max_hp=snap.get("max_hp", 100),
        current_hp=snap.get("max_hp", 100),
        stats=Stats(
            str_=snap.get("str", 10), mag=snap.get("mag", 10), fai=snap.get("fai", 10),
            vit=snap.get("vit", 10), dex=snap.get("dex", 10), spd=snap.get("spd", 10),
            cha=snap.get("cha", 10), karma=snap.get("karma", 0),
        ),
        job_class=snap.get("job_class", 0),
        job_level=snap.get("job_level", 0),
        weapon_attack=snap.get("weapon_attack", 0),
        weapon_accuracy=snap.get("weapon_accuracy", 0),
        armor_defense=snap.get("armor_defense", 0),
        armor_evasion=snap.get("armor_evasion", 0),
        accessory=AccessoryBonuses(
            skill_id=snap.get("acs_skill_id", 0),
            critical=snap.get("acs_critical", 0),
            evasion=snap.get("acs_evasion", 0),
        ),
        skill_id=snap.get("skill_id", 0),
        battle_cry=snap.get("battle_cry", ""),
        gold=snap.get("gold", 0),
    )


def _monster_to_combatant(mon: Monster) -> Combatant:
    # Perl: $mhp = int(rand($mrand)) + $msp
    hp = random.randint(0, mon.damage_range - 1) + mon.speed if mon.damage_range > 0 else mon.speed
    hp = max(1, hp)
    return Combatant(
        name=mon.name,
        level=1,
        max_hp=hp,
        current_hp=hp,
        stats=Stats(str_=mon.base_damage, spd=mon.speed, dex=mon.evasion),
        job_class=0,
        job_level=0,
        weapon_attack=mon.base_damage,
        weapon_accuracy=0,
        armor_defense=0,
        armor_evasion=mon.evasion,
        accessory=AccessoryBonuses(critical=mon.critical_rate),
        skill_id=0,
        gold=0,
        is_monster=True,
        damage_range=mon.damage_range,
    )


def _make_champion_snapshot(char: Character, equip: CharacterEquipment | None) -> str:
    eq = equip or CharacterEquipment()
    return json.dumps({
        "name": char.name, "level": char.level, "max_hp": char.max_hp,
        "str": char.str_, "mag": char.mag, "fai": char.fai, "vit": char.vit,
        "dex": char.dex, "spd": char.spd, "cha": char.cha, "karma": char.karma,
        "job_class": char.job_class, "job_level": char.job_level,
        "weapon_attack": eq.weapon_attack, "weapon_accuracy": eq.weapon_accuracy,
        "armor_defense": eq.armor_defense, "armor_evasion": eq.armor_evasion,
        "acs_skill_id": eq.accessory_skill_id, "acs_critical": eq.acs_critical,
        "acs_evasion": eq.acs_evasion, "skill_id": char.skill_id,
        "battle_cry": char.battle_cry, "gold": int(char.gold),
    }, ensure_ascii=False)


def _apply_battle_rewards(
    db: Session, char: Character, result: BattleResult,
    exp_gained: int, gold_gained: int,
    is_monster_battle: bool = False,
) -> dict:
    char.battle_count += 1
    char.last_battle_time = int(time.time())

    actual_exp = exp_gained
    actual_gold = gold_gained

    if result.outcome == "win":
        char.win_count += 1
        # Perl: $gold = $mgold + int(rand($mgold)+1)
        if is_monster_battle:
            actual_gold = gold_gained + random.randint(1, max(1, gold_gained))
        char.exp += actual_exp
        char.gold = min(char.gold + actual_gold, settings.gold_max)
        if char.gold < 0:
            char.gold = 0

        # 升級判定
        new_lv, new_exp, new_stats, new_hp = check_level_up(
            char.level, int(char.exp), char.job_class,
            {"str": char.str_, "mag": char.mag, "fai": char.fai, "vit": char.vit,
             "dex": char.dex, "spd": char.spd, "cha": char.cha, "karma": char.karma},
            char.max_hp,
        )
        level_ups = new_lv - char.level
        char.level = new_lv
        char.exp = new_exp
        char.max_hp = new_hp
        char.str_ = new_stats["str"]
        char.mag = new_stats["mag"]
        char.fai = new_stats["fai"]
        char.vit = new_stats["vit"]
        char.dex = new_stats["dex"]
        char.spd = new_stats["spd"]
        char.cha = new_stats["cha"]
        char.karma = new_stats["karma"]

        # 職業經驗
        char.job_level = min(char.job_level + 1, 60)
    elif result.outcome == "lose" and is_monster_battle:
        # Perl: 敗北 → 經驗 1，金幣變百分之一
        actual_exp = 1
        gold_before = int(char.gold)
        char.exp += actual_exp
        char.gold = int(char.gold // 100)
        gold_lost = gold_before - int(char.gold)
        level_ups = 0
    elif result.outcome == "timeout" and is_monster_battle:
        # Perl: 逃跑 → 經驗減半
        actual_exp = exp_gained // 2
        char.exp += actual_exp
        level_ups = 0
    else:
        level_ups = 0

    # HP 結算
    if is_monster_battle:
        # Perl: $chara[15] = $khp_flg + int(rand($chara[10]))
        # 戰後 HP = 殘餘 HP + rand(VIT)，不超過 max_hp，死亡則回滿
        final_hp = result.attacker_final_hp
        if final_hp <= 0:
            char.current_hp = char.max_hp
        else:
            vit_recovery = random.randint(0, max(1, char.vit) - 1) if char.vit > 0 else 0
            char.current_hp = min(final_hp + vit_recovery, char.max_hp)
    else:
        char.current_hp = max(1, result.attacker_final_hp)

    db.commit()

    resp = {
        "outcome": result.outcome,
        "rounds": len(result.rounds),
        "exp_gained": actual_exp,
        "gold_gained": actual_gold if result.outcome == "win" else 0,
        "level_ups": level_ups,
        "attacker_hp": char.current_hp,
        "defender_hp": result.defender_final_hp,
        "battle_log": [line for r in result.rounds for line in r.log_lines],
    }
    if result.outcome == "lose" and is_monster_battle:
        resp["gold_lost"] = gold_lost
    return resp


def check_cooldown(char: Character, cooldown: int) -> int:
    """回傳剩餘冷卻秒數，0 表示可戰鬥。"""
    return max(0, cooldown - (int(time.time()) - int(char.last_battle_time)))


def _reset_daily_battles(char: Character) -> None:
    """若跨日則重置剩餘戰鬥次數。"""
    from datetime import date
    today = date.today().isoformat()
    if char.last_battle_reset != today:
        char.available_battles = settings.sentou_limit
        char.last_battle_reset = today


def fight_champion(db: Session, char: Character) -> dict:
    remaining = check_cooldown(char, settings.b_time)
    if remaining > 0:
        return {"error": f"請再等{remaining}秒"}

    champ = db.query(Champion).first()
    if not champ or not champ.character_id:
        return {"error": "目前沒有冠軍"}
    if champ.character_id == char.id:
        return {"error": "無法與自己戰鬥"}

    attacker = _char_to_combatant(char, char.equipment)
    defender = _champion_to_combatant(champ)

    engine = BattleEngine(max_rounds=settings.turn)
    result = engine.execute(attacker, defender, BattleMode.CHAMPION)

    bounty = int(champ.bounty)
    exp_gained = defender.level * 50

    resp = _apply_battle_rewards(db, char, result, exp_gained, bounty)

    if result.outcome == "win":
        champ.character_id = char.id
        champ.character_name = char.name
        champ.win_streak = 1
        champ.bounty = 0
        champ.snapshot_json = _make_champion_snapshot(char, char.equipment)
        db.commit()
        resp["became_champion"] = True
    else:
        champ.bounty += char.level * 100
        champ.win_streak += 1
        db.commit()
        resp["became_champion"] = False

    resp["champion_name"] = champ.character_name
    return resp


def fight_monster(db: Session, char: Character, zone: str) -> dict:
    _reset_daily_battles(char)

    remaining = check_cooldown(char, settings.m_time)
    if remaining > 0:
        return {"error": f"請再等{remaining}秒"}

    if char.available_battles <= 0:
        return {"error": "今日的戰鬥次數已用完"}

    monsters = db.query(Monster).filter(Monster.zone == zone).all()
    if not monsters:
        return {"error": f"區域 '{zone}' 沒有魔物"}

    mon = random.choice(monsters)
    attacker = _char_to_combatant(char, char.equipment)
    defender = _monster_to_combatant(mon)

    engine = BattleEngine(max_rounds=settings.turn)
    result = engine.execute(attacker, defender, BattleMode.MONSTER, monster_skill_id=mon.skill_id)

    char.available_battles -= 1

    resp = _apply_battle_rewards(db, char, result, mon.exp_reward, int(mon.gold_drop), is_monster_battle=True)
    resp["monster_name"] = mon.name
    return resp


def fight_boss(db: Session, char: Character, boss_tier: int) -> dict:
    remaining = check_cooldown(char, settings.m_time)
    if remaining > 0:
        return {"error": f"請再等{remaining}秒"}

    if boss_tier < 0 or boss_tier > 3:
        return {"error": "無效的Boss難度"}
    if char.title_rank < boss_tier:
        return {"error": "稱號等級不足"}

    zone = f"boss{boss_tier}"
    monsters = db.query(Monster).filter(Monster.zone == zone).all()
    if not monsters:
        return {"error": "尚未設定Boss"}

    mon = random.choice(monsters)
    attacker = _char_to_combatant(char, char.equipment)
    defender = _monster_to_combatant(mon)

    engine = BattleEngine(max_rounds=settings.turn)
    result = engine.execute(attacker, defender, BattleMode.BOSS, monster_skill_id=mon.skill_id)

    resp = _apply_battle_rewards(db, char, result, mon.exp_reward * 3, int(mon.gold_drop) * 2, is_monster_battle=True)

    if result.outcome == "win":
        char.boss_counter += 1
        if char.boss_counter >= 10 and char.title_rank <= boss_tier:
            char.title_rank = boss_tier + 1
            resp["title_rank_up"] = True
        db.commit()

    resp["monster_name"] = mon.name
    return resp


def fight_pvp(db: Session, char: Character, opponent_id: str) -> dict:
    remaining = check_cooldown(char, settings.b_time)
    if remaining > 0:
        return {"error": f"請再等{remaining}秒"}

    if opponent_id == char.id:
        return {"error": "無法與自己戰鬥"}

    opponent = db.query(Character).filter(Character.id == opponent_id).first()
    if not opponent:
        return {"error": "找不到對戰對手"}

    attacker = _char_to_combatant(char, char.equipment)
    defender = _char_to_combatant(opponent, opponent.equipment)

    engine = BattleEngine(max_rounds=settings.turn)
    result = engine.execute(attacker, defender, BattleMode.PVP_SELECT)

    # PvP 無報酬（原始設計）
    char.battle_count += 1
    char.last_battle_time = int(time.time())
    if result.outcome == "win":
        char.win_count += 1
    char.current_hp = max(1, result.attacker_final_hp)
    db.commit()

    return {
        "outcome": result.outcome,
        "rounds": len(result.rounds),
        "opponent_name": opponent.name,
        "attacker_hp": result.attacker_final_hp,
        "defender_hp": result.defender_final_hp,
        "battle_log": [line for r in result.rounds for line in r.log_lines],
    }
