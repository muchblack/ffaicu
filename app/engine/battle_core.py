"""統一戰鬥迴圈。

整合原始 battle.pl、wbattle.pl、mbattle.pl 三個檔案的邏輯。
差異透過 BattleMode 注入。
"""

from __future__ import annotations

from app.engine.battle_state import BattleMode, BattleResult, Combatant, RoundState
from app.engine.critical import apply_critical, apply_monster_critical
from app.engine.damage import apply_defense, calculate_base_damage, calculate_job_bonus
from app.engine.evasion import check_evasion
from app.engine.skill_executor import (
    execute_accessory_skill,
    execute_character_skill,
    execute_monster_skill,
)

_MONSTER_MODES = (BattleMode.MONSTER, BattleMode.BOSS, BattleMode.ISEKAI, BattleMode.GENEI)


class BattleEngine:
    def __init__(self, max_rounds: int = 150):
        self.max_rounds = max_rounds

    def execute(
        self,
        attacker: Combatant,
        defender: Combatant,
        mode: BattleMode,
        monster_skill_id: int = 0,
    ) -> BattleResult:
        rounds: list[RoundState] = []
        a_hp = attacker.current_hp
        d_hp = defender.max_hp if mode != BattleMode.PVP_SELECT else defender.current_hp
        is_monster = mode in _MONSTER_MODES

        for i in range(1, self.max_rounds + 1):
            state = RoundState(
                round_num=i,
                attacker_weapon_attack=attacker.weapon_attack,
                defender_weapon_attack=defender.weapon_attack,
                attacker_armor_defense=attacker.armor_defense,
                defender_armor_defense=defender.armor_defense,
            )

            # 1. 基礎傷害
            state.attacker_dmg = calculate_base_damage(attacker, mode)
            state.defender_dmg = calculate_base_damage(defender, mode)

            # 2. 職業公式加算（怪物不使用職業加算）
            state.attacker_dmg += calculate_job_bonus(attacker)
            if not is_monster:
                state.defender_dmg += calculate_job_bonus(defender)

            # 3. 暴擊判定（魔物戰用 HP 比例制）
            if is_monster:
                apply_monster_critical(state, attacker, defender, a_hp, d_hp)
            else:
                apply_critical(state, attacker, a_hp, i, is_attacker=True, mode=mode)
                apply_critical(state, defender, d_hp, i, is_attacker=False, mode=mode)

            # 4. 角色技能 (hissatu)
            execute_character_skill(state, attacker, "hissatu", is_attacker=True)
            if mode in (BattleMode.CHAMPION, BattleMode.PVP_SELECT):
                execute_character_skill(state, defender, "hissatu", is_attacker=False)
            elif monster_skill_id > 0:
                execute_monster_skill(state, monster_skill_id, defender, is_attacker=False)

            # 5. 飾品效果
            is_champion_battle = mode == BattleMode.CHAMPION
            execute_accessory_skill(state, attacker, is_attacker=True)
            if mode in (BattleMode.CHAMPION, BattleMode.PVP_SELECT):
                execute_accessory_skill(state, defender, is_attacker=False, is_champion=is_champion_battle)

            # 6. 角色技能 (atowaza)
            execute_character_skill(state, attacker, "atowaza", is_attacker=True)
            if mode in (BattleMode.CHAMPION, BattleMode.PVP_SELECT):
                execute_character_skill(state, defender, "atowaza", is_attacker=False)

            # 7. 防禦減算（魔物戰只對怪物傷害做防禦減算，玩家打怪物無防禦減算）
            if is_monster:
                # Perl: 只有 $dmg2（怪物→玩家）做防禦減算
                state.defender_dmg = apply_defense(
                    state.defender_dmg, state.attacker_armor_defense, attacker.job_class
                )
            else:
                state.attacker_dmg = apply_defense(
                    state.attacker_dmg, state.defender_armor_defense, defender.job_class
                )
                state.defender_dmg = apply_defense(
                    state.defender_dmg, state.attacker_armor_defense, attacker.job_class
                )

            # 8. 迴避判定
            check_evasion(state, attacker, defender, mode=mode)

            # 9. HP 結算
            state.attacker_dmg = max(0, state.attacker_dmg)
            state.defender_dmg = max(0, state.defender_dmg)

            # 回合標題（顯示結算前的 HP）
            round_header = (
                f"第{i}回合 [{attacker.name} HP:{max(0,a_hp)}/{attacker.max_hp}]"
                f" vs [{defender.name} HP:{max(0,d_hp)}/{defender.max_hp}]"
            )

            d_hp -= state.attacker_dmg
            a_hp -= state.defender_dmg
            a_hp += state.attacker_hp_heal
            d_hp += state.defender_hp_heal
            a_hp = min(a_hp, attacker.max_hp)
            d_hp = min(d_hp, defender.max_hp)

            # 10. 戰鬥紀錄（回合標題 → 攻方技能/暴擊 → 攻方傷害 → 守方技能/暴擊 → 守方傷害）
            state.log_lines = [round_header]
            state.log_lines.extend(state.attacker_log_lines)
            state.log_lines.append(f"對{defender.name}造成了 {state.attacker_dmg} 點傷害。")
            state.log_lines.extend(state.defender_log_lines)
            state.log_lines.append(f"{defender.name}對{attacker.name}造成了 {state.defender_dmg} 點傷害。")
            if state.attacker_hp_heal > 0:
                state.log_lines.append(f"{attacker.name}回復了 {state.attacker_hp_heal} HP。")
            if state.defender_hp_heal > 0:
                state.log_lines.append(f"{defender.name}回復了 {state.defender_hp_heal} HP。")

            rounds.append(state)

            # 10. 勝負判定
            if state.battle_escaped:
                break
            if d_hp <= 0 or a_hp <= 0:
                break

        # 判定結果
        last = rounds[-1] if rounds else None
        if last and last.battle_escaped:
            outcome = "draw"
        elif d_hp <= 0 and a_hp <= 0:
            outcome = "draw"
        elif d_hp <= 0:
            outcome = "win"
        elif a_hp <= 0:
            outcome = "lose"
        else:
            outcome = "timeout"

        return BattleResult(
            outcome=outcome,
            rounds=rounds,
            attacker_final_hp=max(0, a_hp),
            defender_final_hp=max(0, d_hp),
        )
