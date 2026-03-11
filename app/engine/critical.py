"""暴擊判定與 Limit Break。

PvP 和魔物戰使用不同的暴擊系統：
- PvP：暴擊率 = gold/15 + 10 + job_level（wbattle.pl）
- 魔物戰：暴擊率 = 100 - HP%（mbattle.pl）
"""

from __future__ import annotations

import random

from app.engine.battle_state import BattleMode, Combatant, RoundState

_MONSTER_MODES = (BattleMode.MONSTER, BattleMode.BOSS, BattleMode.ISEKAI, BattleMode.GENEI)


def calculate_crit_rate(combatant: Combatant, mode: BattleMode | None = None) -> int:
    """PvP 暴擊率：waza_ritu = int(gold/15) + 10 + job_level, cap 95。"""
    rate = combatant.gold // 15 + 10 + combatant.job_level
    rate = min(rate, 75)
    rate += combatant.accessory.critical
    rate = min(rate, 95)
    # ISEKAI 暴擊率 /3，BOSS/GENEI 暴擊率 /2
    if mode == BattleMode.ISEKAI:
        rate = rate // 3
    elif mode in (BattleMode.BOSS, BattleMode.GENEI):
        rate = rate // 2
    return rate


def check_limit_break(combatant: Combatant, current_hp: int, round_num: int) -> bool:
    """Limit Break：HP < 10% 且回合 > 15 時觸發。"""
    if round_num <= 15:
        return False
    threshold = combatant.max_hp // 10
    return current_hp > 0 and current_hp < threshold


def apply_critical(state: RoundState, combatant: Combatant, current_hp: int,
                   round_num: int, is_attacker: bool, mode: BattleMode | None = None) -> None:
    """PvP 暴擊判定（dmg × 2，Limit Break × 10）。"""
    rate = calculate_crit_rate(combatant, mode)

    # Limit Break：50% 觸發（Perl: int(rand(4)) > 1）
    if check_limit_break(combatant, current_hp, round_num) and random.randint(0, 3) > 1:
        rate = 999

    if rate > random.randint(0, 99):
        log = state.attacker_log_lines if is_attacker else state.defender_log_lines
        if is_attacker:
            state.attacker_crit = True
            state.attacker_dmg *= 2
        else:
            state.defender_crit = True
            state.defender_dmg *= 2
        log.append(f"★{combatant.name}的暴擊命中！！！")

        # Limit Break 10x
        if rate >= 999:
            if is_attacker:
                state.attacker_dmg *= 5  # 已經 2x，再 5x = 10x
            else:
                state.defender_dmg *= 5
            log.append(f"☆{combatant.name}的極限技發動！！！！！")


def apply_monster_critical(state: RoundState, attacker: Combatant, defender: Combatant,
                           attacker_hp: int, defender_hp: int) -> None:
    """魔物戰暴擊判定。暴擊率 = 100 - 當前HP%。

    Perl (mbattle.pl):
      玩家暴擊率 = 100 - int(HP / maxHP * 100)，vs rand(100)，效果 dmg × 3
      魔物暴擊率 = 100 - int(HP / maxHP * 100)，vs rand(200)，效果 dmg += 對方防禦力
    """
    # 玩家暴擊（攻擊方）
    if attacker.max_hp > 0:
        player_rate = 100 - (attacker_hp * 100 // attacker.max_hp)
        if player_rate > random.randint(0, 99):
            state.attacker_crit = True
            state.attacker_dmg *= 3
            state.attacker_log_lines.append(f"暴擊！！「{attacker.battle_cry}」" if attacker.battle_cry
                                            else f"★{attacker.name}的暴擊命中！！！")

    # 魔物暴擊（防守方）
    if defender.max_hp > 0:
        monster_rate = 100 - (defender_hp * 100 // defender.max_hp)
        if monster_rate > random.randint(0, 199):
            state.defender_crit = True
            # Perl: $dmg2 = $dmg2 + $item[4]（穿透：加上對方防禦力）
            state.defender_dmg += state.attacker_armor_defense
            state.defender_log_lines.append(f"★{defender.name}的暴擊命中！！")
