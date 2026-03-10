from app.engine.battle_core import BattleEngine
from app.engine.battle_state import (
    AccessoryBonuses,
    BattleMode,
    Combatant,
    Stats,
)


def _make_combatant(
    name: str = "測試",
    level: int = 10,
    hp: int = 1000,
    job_class: int = 0,
    weapon_attack: int = 50,
    armor_defense: int = 20,
    **kwargs,
) -> Combatant:
    return Combatant(
        name=name,
        level=level,
        max_hp=hp,
        current_hp=hp,
        stats=Stats(str_=100, mag=50, fai=50, vit=50, dex=50, spd=50, cha=50, karma=10),
        job_class=job_class,
        job_level=30,
        weapon_attack=weapon_attack,
        weapon_accuracy=10,
        armor_defense=armor_defense,
        armor_evasion=0,
        accessory=AccessoryBonuses(),
        skill_id=0,
        gold=10000,
        **kwargs,
    )


def test_battle_produces_result():
    attacker = _make_combatant("勇者", hp=5000, weapon_attack=200)
    defender = _make_combatant("魔物", hp=500, weapon_attack=10, armor_defense=5)
    engine = BattleEngine(max_rounds=50)
    result = engine.execute(attacker, defender, BattleMode.MONSTER)
    assert result.outcome in ("win", "lose", "draw", "timeout")
    assert len(result.rounds) > 0


def test_strong_attacker_usually_wins():
    wins = 0
    for _ in range(20):
        attacker = _make_combatant("強者", hp=10000, weapon_attack=500, armor_defense=100)
        defender = _make_combatant("弱者", hp=100, weapon_attack=5, armor_defense=0)
        result = BattleEngine(max_rounds=50).execute(attacker, defender, BattleMode.PVP_SELECT)
        if result.outcome == "win":
            wins += 1
    assert wins >= 15, f"強者應大多獲勝，但只贏了 {wins}/20"


def test_timeout_when_both_tanky():
    attacker = _make_combatant("壁A", hp=99999, weapon_attack=1, armor_defense=9999)
    defender = _make_combatant("壁B", hp=99999, weapon_attack=1, armor_defense=9999)
    result = BattleEngine(max_rounds=10).execute(attacker, defender, BattleMode.PVP_SELECT)
    assert result.outcome == "timeout"
    assert len(result.rounds) == 10
