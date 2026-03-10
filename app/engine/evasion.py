"""迴避判定。

PvP 和魔物戰使用不同的迴避系統：
- PvP：armor_evasion + acs_evasion vs rand(999)
- 魔物戰（Perl mbattle.pl mons_kaihi）：
  - 玩家迴避 = spd/20 + armor_evasion + acs_evasion vs rand(300)
  - 魔物迴避 = mon.evasion - (dex/10 + 51 + weapon_accuracy + acs_accuracy) vs rand(100)
"""

from __future__ import annotations

import random

from app.engine.battle_state import BattleMode, Combatant, RoundState

_MONSTER_MODES = (BattleMode.MONSTER, BattleMode.BOSS, BattleMode.ISEKAI, BattleMode.GENEI)


def check_evasion(state: RoundState, attacker: Combatant, defender: Combatant,
                  mode: BattleMode | None = None) -> None:
    """迴避判定。依 mode 分派 PvP 或魔物戰邏輯。"""
    if mode in _MONSTER_MODES:
        _check_monster_evasion(state, attacker, defender)
    else:
        _check_pvp_evasion(state, attacker, defender)


def _check_pvp_evasion(state: RoundState, attacker: Combatant, defender: Combatant) -> None:
    """PvP 迴避：armor_evasion + acs_evasion vs rand(999)。迴避成功傷害歸 0。"""
    # 防守方迴避攻擊方的傷害
    defender_evade = defender.armor_evasion + defender.accessory.evasion
    if defender_evade > 0 and random.randint(0, 999) < defender_evade:
        state.attacker_dmg = 0
        state.defender_evaded = True
        state.log_lines.append(f"{defender.name}閃避了攻擊！")

    # 攻擊方迴避防守方的傷害
    attacker_evade = attacker.armor_evasion + attacker.accessory.evasion
    if attacker_evade > 0 and random.randint(0, 999) < attacker_evade:
        state.defender_dmg = 0
        state.attacker_evaded = True
        state.log_lines.append(f"{attacker.name}閃避了攻擊！")


def _check_monster_evasion(state: RoundState, attacker: Combatant, defender: Combatant) -> None:
    """魔物戰迴避。attacker=玩家，defender=魔物。

    Perl:
      玩家迴避率 = spd/20 + armor_evasion + acs_evasion，vs rand(300)
      魔物迴避率 = mon.evasion - hit_rate，vs rand(100)
        where hit_rate = dex/10 + 51 + weapon_accuracy + acs_accuracy
    """
    # 防禦減算（Perl 在 mons_kaihi 中處理）已由 apply_defense 處理，此處只做迴避

    # 玩家迴避魔物攻擊：spd/20 + armor_evasion + acs_evasion vs rand(300)
    player_evade = attacker.stats.get("spd") // 20 + attacker.armor_evasion + attacker.accessory.evasion
    if player_evade > random.randint(0, 299):
        state.defender_dmg = 0
        state.attacker_evaded = True
        state.log_lines.append(f"{attacker.name}閃開了攻擊！")

    # 魔物迴避玩家攻擊：mon.evasion - hit_rate vs rand(100)
    hit_rate = attacker.stats.get("dex") // 10 + 51 + attacker.weapon_accuracy + attacker.accessory.accuracy
    monster_evade = defender.armor_evasion - hit_rate
    if monster_evade > random.randint(0, 99):
        state.attacker_dmg = 0
        state.defender_evaded = True
        state.log_lines.append(f"{defender.name}閃開了攻擊！")
