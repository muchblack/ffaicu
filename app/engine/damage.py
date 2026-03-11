"""傷害計算模組。

職業攻擊公式從 jobs.json 查表，消滅原始 31 個 sub syoku* 函數。
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from app.engine.battle_state import BattleMode, Combatant

_jobs_data: dict | None = None


def _load_jobs() -> dict:
    global _jobs_data
    if _jobs_data is None:
        path = Path(__file__).parent.parent.parent / "data" / "jobs.json"
        with open(path, encoding="utf-8") as f:
            _jobs_data = json.load(f)
    return _jobs_data


def calculate_base_damage(combatant: Combatant, mode: BattleMode) -> int:
    """基礎傷害計算。魔物戰與 PvP 公式不同。"""
    is_monster_battle = mode in (BattleMode.MONSTER, BattleMode.BOSS, BattleMode.ISEKAI, BattleMode.GENEI)
    if is_monster_battle and combatant.is_monster:
        # Perl: $dmg2 = $mdmg + int(rand($mrand))
        dr = combatant.damage_range
        return combatant.weapon_attack + (random.randint(0, dr - 1) if dr > 0 else 0)
    elif is_monster_battle:
        # Perl: $dmg1 = $chara[18] * (int(rand(5)) + 1)  → level × rand(1~5)
        return combatant.level * random.randint(1, 5)
    else:
        # PvP: Perl wbattle.pl L5-6: $dmg = $chara[18] * (int(rand(3)) + 1) → level × rand(1~3)
        return combatant.level * random.randint(1, 3)


def calculate_job_bonus(combatant: Combatant) -> int:
    """依職業公式加算傷害。"""
    jobs = _load_jobs()
    job_key = str(combatant.job_class)
    job_def = jobs.get(job_key)
    if not job_def:
        return 0

    total = 0
    for op, stat_name in job_def.get("attack_stats", []):
        stat_val = combatant.stats.get(stat_name)
        if op == "rand":
            total += random.randint(0, stat_val - 1) if stat_val > 0 else 0
        elif op == "flat":
            total += stat_val

    multiplier = job_def.get("multiplier", 1)
    return total * multiplier + combatant.weapon_attack


def apply_defense(damage: int, armor_defense: int, attacker_job_class: int) -> int:
    """防禦減算 + 職業防禦加成。至少造成 1 點傷害。"""
    if damage < armor_defense:
        return 1
    damage = damage - armor_defense
    if attacker_job_class >= 18:
        damage = damage // 4
    elif attacker_job_class >= 8:
        damage = damage // 2
    return max(1, damage)
