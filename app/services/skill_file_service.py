"""技能 JSON 檔案 CRUD 服務。"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from app.engine.formula_parser import FormulaError, _tokenize, _Parser

_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "skills"

SKILL_FILES: dict[str, str] = {
    "character": "character_skills.json",
    "accessory": "accessory_skills.json",
    "monster": "monster_skills.json",
    "champion": "champion_accessory_skills.json",
}

CATEGORY_LABELS: dict[str, str] = {
    "character": "角色技能",
    "accessory": "飾品技能",
    "monster": "魔物技能",
    "champion": "冠軍飾品技能",
}

# character 是雙階段格式 (hissatu/atowaza)，其餘是扁平格式
DUAL_PHASE_CATEGORIES = {"character"}

VALID_TRIGGER_TYPES = {"always", "skill_rate_check", "monster_skill_rate", "random"}

VALID_EFFECT_TYPES = {
    "add_damage", "set_damage", "multiply_damage", "heal_attacker",
    "reduce_attacker_damage", "bypass_evasion", "buff_attack", "buff_defense",
    "multi_hit", "instakill", "conditional", "evasion_boost",
    "nullify_enemy_damage", "damage_reflect", "self_damage", "ignore_defense",
    "full_heal", "battle_escape", "steal_gold", "tarot_draw", "copy_enemy",
    "heal_enemy", "damage_to_enemy_self",
}

# 公式驗證用的假變數（只需能通過 parser 即可）
_DUMMY_VARS = {
    "str": 10, "mag": 10, "fai": 10, "vit": 10, "dex": 10, "spd": 10,
    "cha": 10, "karma": 10, "job_level": 10, "level": 10, "max_hp": 100,
    "current_hp": 50, "weapon_attack": 10, "armor_defense": 10,
    "all_stats": 90, "seven_stats": 70, "damage_range": 10,
}


def load_skill_file(category: str) -> dict[str, Any]:
    """讀取指定分類的技能 JSON 檔案。"""
    filename = SKILL_FILES.get(category)
    if not filename:
        raise ValueError(f"Unknown category: {category}")
    path = _DATA_DIR / filename
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_skill_file(category: str, data: dict[str, Any]) -> None:
    """原子寫入技能 JSON 檔案。"""
    filename = SKILL_FILES.get(category)
    if not filename:
        raise ValueError(f"Unknown category: {category}")
    path = _DATA_DIR / filename
    fd, tmp_path = tempfile.mkstemp(dir=str(_DATA_DIR), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_path, str(path))
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def get_skill(category: str, skill_id: str) -> Any:
    """取得單筆技能定義。"""
    data = load_skill_file(category)
    return data.get(skill_id)


def save_skill(category: str, skill_id: str, skill_data: Any) -> None:
    """更新單筆技能。"""
    data = load_skill_file(category)
    data[skill_id] = skill_data
    save_skill_file(category, data)


def delete_skill(category: str, skill_id: str) -> bool:
    """刪除單筆技能。回傳是否成功。"""
    data = load_skill_file(category)
    if skill_id not in data:
        return False
    del data[skill_id]
    save_skill_file(category, data)
    return True


def _validate_formula(formula: str) -> list[str]:
    """驗證公式語法，回傳錯誤列表。"""
    errors = []
    try:
        tokens = _tokenize(formula)
        if tokens:
            parser = _Parser(tokens, _DUMMY_VARS, lambda n: 1)
            parser.parse_expr()
            if parser.pos < len(parser.tokens):
                errors.append(f"公式 '{formula}' 有多餘字元: {parser.peek()}")
    except FormulaError as e:
        errors.append(f"公式 '{formula}' 語法錯誤: {e}")
    return errors


def _validate_effects(effects: list[dict], path_prefix: str = "") -> list[str]:
    """遞迴驗證 effects 陣列。"""
    errors = []
    for i, effect in enumerate(effects):
        prefix = f"{path_prefix}effects[{i}]"
        etype = effect.get("type", "")
        if etype not in VALID_EFFECT_TYPES:
            errors.append(f"{prefix}: 未知效果類型 '{etype}'")

        # 驗證 formula 欄位
        for key in ("formula", "hits_formula"):
            if key in effect:
                errors.extend(_validate_formula(effect[key]))

        # 遞迴驗證 conditional 的 success/failure
        if etype == "conditional":
            for sub_key in ("success", "failure"):
                sub = effect.get(sub_key)
                if isinstance(sub, dict) and sub:
                    errors.extend(_validate_effects([sub], f"{prefix}.{sub_key}."))

        # 遞迴驗證 tarot_draw 的 cards
        if etype == "tarot_draw":
            for ci, card in enumerate(effect.get("cards", [])):
                card_effects = card.get("effects", [])
                errors.extend(_validate_effects(card_effects, f"{prefix}.cards[{ci}]."))
    return errors


def _validate_phase(phase_data: dict | None, phase_name: str) -> list[str]:
    """驗證單一 phase (hissatu 或 atowaza)。"""
    if phase_data is None:
        return []
    errors = []
    trigger = phase_data.get("trigger")
    if trigger:
        ttype = trigger.get("type", "")
        if ttype not in VALID_TRIGGER_TYPES:
            errors.append(f"{phase_name}.trigger: 未知觸發類型 '{ttype}'")
    effects = phase_data.get("effects", [])
    errors.extend(_validate_effects(effects, f"{phase_name}."))
    return errors


def validate_skill(category: str, skill_data: Any) -> list[str]:
    """驗證技能定義，回傳錯誤訊息列表（空=通過）。"""
    if skill_data is None:
        return []

    errors = []

    if category in DUAL_PHASE_CATEGORIES:
        # 雙階段：hissatu / atowaza
        if not isinstance(skill_data, dict):
            return ["角色技能應為物件（含 hissatu/atowaza）"]
        errors.extend(_validate_phase(skill_data.get("hissatu"), "hissatu"))
        errors.extend(_validate_phase(skill_data.get("atowaza"), "atowaza"))
    else:
        # 扁平格式：trigger + effects
        if not isinstance(skill_data, dict):
            return ["技能應為物件（含 trigger + effects）"]
        trigger = skill_data.get("trigger")
        if trigger:
            ttype = trigger.get("type", "")
            if ttype not in VALID_TRIGGER_TYPES:
                errors.append(f"trigger: 未知觸發類型 '{ttype}'")
        effects = skill_data.get("effects", [])
        errors.extend(_validate_effects(effects))

    return errors
