from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class BattleMode(Enum):
    CHAMPION = "champion"
    PVP_SELECT = "pvp_select"
    MONSTER = "monster"
    BOSS = "boss"
    ISEKAI = "isekai"
    GENEI = "genei"


@dataclass
class Stats:
    str_: int = 0
    mag: int = 0
    fai: int = 0
    vit: int = 0
    dex: int = 0
    spd: int = 0
    cha: int = 0
    karma: int = 0

    def get(self, name: str) -> int:
        mapping = {
            "str": self.str_, "mag": self.mag, "fai": self.fai,
            "vit": self.vit, "dex": self.dex, "spd": self.spd,
            "cha": self.cha, "karma": self.karma,
        }
        return mapping.get(name, 0)

    def total(self) -> int:
        return self.str_ + self.mag + self.fai + self.vit + self.dex + self.spd + self.cha + self.karma


@dataclass
class AccessoryBonuses:
    skill_id: int = 0
    str_: int = 0
    mag: int = 0
    fai: int = 0
    vit: int = 0
    dex: int = 0
    spd: int = 0
    cha: int = 0
    karma: int = 0
    accuracy: int = 0
    evasion: int = 0
    critical: int = 0


@dataclass
class Combatant:
    name: str
    level: int
    max_hp: int
    current_hp: int
    stats: Stats
    job_class: int
    job_level: int
    weapon_attack: int
    weapon_accuracy: int
    armor_defense: int
    armor_evasion: int
    accessory: AccessoryBonuses
    skill_id: int
    battle_cry: str = ""
    image_id: int = 0
    gold: int = 0  # 暴擊率計算用
    is_monster: bool = False
    damage_range: int = 0  # 怪物用：傷害隨機幅度


@dataclass
class RoundState:
    round_num: int = 0
    attacker_dmg: int = 0
    defender_dmg: int = 0
    attacker_evaded: bool = False
    defender_evaded: bool = False
    attacker_crit: bool = False
    defender_crit: bool = False
    attacker_hp_heal: int = 0
    defender_hp_heal: int = 0
    attacker_weapon_attack: int = 0  # 可被 buff 修改
    defender_weapon_attack: int = 0
    attacker_armor_defense: int = 0
    defender_armor_defense: int = 0
    sealed: bool = False
    log_lines: list[str] = field(default_factory=list)


@dataclass
class BattleResult:
    outcome: Literal["win", "lose", "draw", "timeout"]
    rounds: list[RoundState]
    attacker_final_hp: int = 0
    defender_final_hp: int = 0
    exp_gained: int = 0
    gold_gained: int = 0
    level_ups: int = 0
