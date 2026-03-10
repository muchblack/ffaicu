"""技能效果執行器 — 讀取 JSON 技能定義，在戰鬥中執行效果。"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from app.engine.battle_state import Combatant, RoundState
from app.engine.formula_parser import evaluate

_skills_cache: dict[str, dict] = {}


def _load_skill_file(filename: str) -> dict:
    if filename not in _skills_cache:
        path = Path(__file__).parent.parent.parent / "data" / "skills" / filename
        if path.exists():
            with open(path, encoding="utf-8") as f:
                _skills_cache[filename] = json.load(f)
        else:
            _skills_cache[filename] = {}
    return _skills_cache[filename]


def _build_variables(combatant: Combatant, state: RoundState, is_attacker: bool) -> dict[str, int]:
    """建立公式可用的變數映射。"""
    return {
        "str": combatant.stats.str_,
        "mag": combatant.stats.mag,
        "fai": combatant.stats.fai,
        "vit": combatant.stats.vit,
        "dex": combatant.stats.dex,
        "spd": combatant.stats.spd,
        "cha": combatant.stats.cha,
        "karma": combatant.stats.karma,
        "job_level": combatant.job_level,
        "level": combatant.level,
        "weapon_attack": combatant.weapon_attack,
        "armor_defense": combatant.armor_defense,
        "damage_range": state.attacker_dmg if is_attacker else state.defender_dmg,
    }


def _check_trigger(trigger: dict, combatant: Combatant, state: RoundState) -> bool:
    """判定技能是否觸發。"""
    trigger_type = trigger.get("type", "never")

    if trigger_type == "always":
        return True

    if trigger_type == "skill_rate_check":
        threshold = trigger.get("threshold", 100)
        rate = combatant.gold // 15 + 10 + combatant.job_level
        rate = min(rate, 95)
        return rate > random.randint(0, threshold - 1)

    if trigger_type == "monster_skill_rate":
        return random.randint(0, 99) < 50  # 簡化版魔物技能觸發率

    if trigger_type == "random":
        chance = trigger.get("chance", 0.5)
        return random.random() < chance

    return False


def _apply_effect(effect: dict, state: RoundState, combatant: Combatant, is_attacker: bool) -> None:
    """套用單一效果。"""
    variables = _build_variables(combatant, state, is_attacker)
    effect_type = effect.get("type", "none")
    message = effect.get("message", "")

    if effect_type == "add_damage":
        amount = evaluate(effect["formula"], variables)
        if is_attacker:
            state.attacker_dmg += amount
        else:
            state.defender_dmg += amount

    elif effect_type == "set_damage":
        amount = evaluate(effect["formula"], variables)
        if is_attacker:
            state.attacker_dmg = amount
        else:
            state.defender_dmg = amount

    elif effect_type == "multiply_damage":
        multiplier = effect.get("multiplier", 1)
        if is_attacker:
            state.attacker_dmg = int(state.attacker_dmg * multiplier)
        else:
            state.defender_dmg = int(state.defender_dmg * multiplier)

    elif effect_type == "heal_attacker":
        amount = evaluate(effect["formula"], variables)
        if is_attacker:
            state.attacker_hp_heal += amount
        else:
            state.defender_hp_heal += amount

    elif effect_type == "reduce_attacker_damage":
        multiplier = effect.get("multiplier", 0.5)
        if is_attacker:
            state.defender_dmg = int(state.defender_dmg * multiplier)
        else:
            state.attacker_dmg = int(state.attacker_dmg * multiplier)

    elif effect_type == "bypass_evasion":
        if is_attacker:
            state.defender_evaded = False
        else:
            state.attacker_evaded = False

    elif effect_type == "buff_attack":
        multiplier = effect.get("multiplier", 2)
        if is_attacker:
            state.attacker_weapon_attack = int(state.attacker_weapon_attack * multiplier)
        else:
            state.defender_weapon_attack = int(state.defender_weapon_attack * multiplier)

    elif effect_type == "buff_defense":
        multiplier = effect.get("multiplier", 2)
        if is_attacker:
            state.attacker_armor_defense = int(state.attacker_armor_defense * multiplier)
        else:
            state.defender_armor_defense = int(state.defender_armor_defense * multiplier)

    elif effect_type == "multi_hit":
        hits = evaluate(effect.get("hits_formula", "1"), variables)
        base = evaluate(effect.get("formula", "0"), variables)
        total = base * max(1, hits)
        if is_attacker:
            state.attacker_dmg = total
        else:
            state.defender_dmg = total
        message = message.replace("{hits}", str(hits))

    elif effect_type == "instakill":
        inner_chance = effect.get("inner_chance", 1.0)
        if random.random() < inner_chance:
            if is_attacker:
                state.attacker_dmg = 99999999
            else:
                state.defender_dmg = 99999999
        else:
            fail_msg = effect.get("fail_message", "")
            if fail_msg:
                state.log_lines.append(fail_msg.format(name=combatant.name))
            return

    elif effect_type == "conditional":
        inner_chance = effect.get("inner_chance", 0.5)
        if random.random() < inner_chance:
            success = effect.get("success", {})
            if success:
                _apply_effect(success, state, combatant, is_attacker)
        else:
            failure = effect.get("failure", {})
            if failure:
                _apply_effect(failure, state, combatant, is_attacker)
        return

    if message:
        formatted = message.format(
            name=combatant.name,
            accessory_name="",
            amount=state.attacker_hp_heal if is_attacker else state.defender_hp_heal,
        )
        state.log_lines.append(formatted)


def execute_character_skill(
    state: RoundState,
    combatant: Combatant,
    phase: str,  # "hissatu" or "atowaza"
    is_attacker: bool,
) -> None:
    """執行角色技能。"""
    skills = _load_skill_file("character_skills.json")
    skill_def = skills.get(str(combatant.skill_id))
    if not skill_def:
        return
    phase_def = skill_def.get(phase)
    if not phase_def:
        return
    trigger = phase_def.get("trigger")
    if trigger and _check_trigger(trigger, combatant, state):
        for effect in phase_def.get("effects", []):
            _apply_effect(effect, state, combatant, is_attacker)


def execute_accessory_skill(
    state: RoundState,
    combatant: Combatant,
    is_attacker: bool,
    is_champion: bool = False,
) -> None:
    """執行飾品技能。"""
    filename = "champion_accessory_skills.json" if is_champion else "accessory_skills.json"
    skills = _load_skill_file(filename)
    skill_def = skills.get(str(combatant.accessory.skill_id))
    if not skill_def:
        return
    trigger = skill_def.get("trigger")
    if trigger and _check_trigger(trigger, combatant, state):
        for effect in skill_def.get("effects", []):
            _apply_effect(effect, state, combatant, is_attacker)


def execute_monster_skill(
    state: RoundState,
    monster_skill_id: int,
    combatant: Combatant,
    is_attacker: bool,
) -> None:
    """執行魔物技能。"""
    skills = _load_skill_file("monster_skills.json")
    skill_def = skills.get(str(monster_skill_id))
    if not skill_def:
        return
    trigger = skill_def.get("trigger")
    if trigger and _check_trigger(trigger, combatant, state):
        for effect in skill_def.get("effects", []):
            _apply_effect(effect, state, combatant, is_attacker)
