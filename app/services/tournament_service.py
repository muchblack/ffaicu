"""武道會服務層 — 對齊 Perl 原版 tenka.cgi 玩家逐場挑戰制。"""

from __future__ import annotations

import random
import time
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.engine.battle_core import BattleEngine
from app.engine.battle_state import BattleMode
from app.engine.level_up import check_level_up
from app.models.character import Character
from app.models.tournament import Tournament
from app.services.battle_service import _char_to_combatant, check_cooldown


def _get_participants(db: Session, exclude_id: str) -> list[Character]:
    """取得武道會參賽者（等級最高的 tenka_su 名，排除挑戰者自己）。"""
    return (
        db.query(Character)
        .filter(Character.id != exclude_id)
        .order_by(Character.level.desc())
        .limit(settings.tenka_su)
        .all()
    )


def get_tournament_state(db: Session, char: Character) -> dict:
    """回傳武道會當前狀態，供頁面顯示用。"""
    participants = _get_participants(db, char.id)
    cooldown = check_cooldown(char, settings.b_time)

    # 制覇紀錄
    history = (
        db.query(Tournament)
        .order_by(Tournament.id.desc())
        .limit(10)
        .all()
    )

    # 資格判定
    tc = char.tenka_counter
    if tc == 0 or tc > settings.boss:
        status = "not_eligible"
    elif tc == settings.boss - settings.tenka_su:
        status = "conquered"
    elif settings.boss - settings.tenka_su < tc <= settings.boss:
        status = "in_progress"
    else:
        status = "not_eligible"

    # 當前對手索引（Perl: $aite = $tenka_su + $chara[28] - $boss - 1）
    current_opponent = None
    opponent_index = -1
    fight_number = 0
    if status == "in_progress":
        opponent_index = settings.tenka_su + tc - settings.boss - 1
        fight_number = settings.boss - tc + 1  # 第幾戰（1-based）
        if 0 <= opponent_index < len(participants):
            current_opponent = participants[opponent_index]

    return {
        "status": status,
        "participants": [
            {
                "id": p.id,
                "name": p.name,
                "level": p.level,
                "rank": i + 1,
                "is_current": i == opponent_index,
                # 對手從 index 大(弱)到小(強) 挑戰，index i 對應的戰鬥編號 = tenka_su - i
                "fight_status": (
                    "current" if i == opponent_index else
                    "defeated" if status == "in_progress" and i > opponent_index else
                    "waiting"
                ),
            }
            for i, p in enumerate(participants)
        ],
        "current_opponent": {
            "id": current_opponent.id,
            "name": current_opponent.name,
            "level": current_opponent.level,
        } if current_opponent else None,
        "fight_number": fight_number,
        "total_fights": settings.tenka_su,
        "cooldown": cooldown,
        "history": [
            {
                "id": t.id,
                "winner_name": t.winner_name,
                "created_at": t.created_at,
                "created_at_fmt": datetime.fromtimestamp(t.created_at).strftime("%Y-%m-%d %H:%M") if t.created_at else "",
            }
            for t in history
        ],
    }


def fight_tournament(db: Session, char: Character) -> dict:
    """執行一場武道會戰鬥。"""
    tc = char.tenka_counter

    # 資格檢查
    if tc == 0 or tc > settings.boss:
        return {"error": "請先挑戰冠軍取得參賽資格"}
    if tc <= settings.boss - settings.tenka_su:
        return {"error": "已制覇武道會，請重新挑戰冠軍"}

    # 冷卻檢查
    remaining = check_cooldown(char, settings.b_time)
    if remaining > 0:
        return {"error": f"請再等{remaining}秒"}

    # 取得參賽者與對手
    participants = _get_participants(db, char.id)
    opponent_index = settings.tenka_su + tc - settings.boss - 1
    if opponent_index < 0 or opponent_index >= len(participants):
        return {"error": "對手不足，無法進行武道會"}

    opponent = participants[opponent_index]
    fight_number = settings.boss - tc + 1

    # 執行戰鬥
    attacker = _char_to_combatant(char, char.equipment)
    defender = _char_to_combatant(opponent, opponent.equipment)
    engine = BattleEngine(max_rounds=settings.turn)
    result = engine.execute(attacker, defender, BattleMode.PVP_SELECT)

    # 更新戰鬥統計
    char.battle_count += 1
    char.last_battle_time = int(time.time())

    # Perl: 平手（雙方倒下）視為勝利
    is_win = result.outcome == "win" or result.outcome == "draw"

    if is_win:
        char.win_count += 1
        # Perl tenka.cgi: EXP = 對手等級 × kiso_exp
        exp_gained = opponent.level * settings.kiso_exp
        # Perl tenka.cgi: 金幣 = rand(syoukin)+1 × 對手等級
        gold_gained = (random.randint(0, settings.syoukin) + 1) * opponent.level
        char.exp += exp_gained
        char.gold = min(char.gold + gold_gained, settings.gold_max)
        # Perl tenka.cgi L390: $chara[28]--
        char.tenka_counter -= 1
    else:
        # 敗北
        # Perl wbattle.pl: EXP = 對手等級（無乘數）
        exp_gained = opponent.level
        gold_before = int(char.gold)
        char.exp += exp_gained
        # Perl wbattle.pl L592-594: 金幣減半 + 進度歸零
        char.gold = int(char.gold // 2)
        gold_gained = -(gold_before - int(char.gold))
        # Perl: $chara[28] = $boss — 重置進度
        char.tenka_counter = settings.boss

    # HP 結算（Perl tenka.cgi L397-402）
    final_hp = result.attacker_final_hp
    if final_hp <= 0:
        final_hp = 1
    vit_recovery = random.randint(0, max(1, char.vit) - 1) if char.vit > 0 else 0
    char.current_hp = min(final_hp + vit_recovery, char.max_hp)
    # Perl: if($chara[15] == 1) { $chara[15] = $chara[16]; }
    if char.current_hp == 1:
        char.current_hp = char.max_hp

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

    # 制覇判定（Perl tenka.cgi L413: $next_winner = $chara[28] + $tenka_su - $boss）
    conquered = False
    if is_win:
        next_winner = char.tenka_counter + settings.tenka_su - settings.boss
        if next_winner == 0:
            conquered = True
            # 寫入制覇紀錄
            tournament = Tournament(
                created_at=int(time.time()),
                winner_name=char.name,
            )
            db.add(tournament)

    db.commit()

    resp = {
        "outcome": "win" if is_win else "lose",
        "opponent_name": opponent.name,
        "opponent_level": opponent.level,
        "fight_number": fight_number,
        "total_fights": settings.tenka_su,
        "exp_gained": exp_gained,
        "gold_gained": gold_gained,
        "level_ups": level_ups,
        "attacker_hp": char.current_hp,
        "defender_hp": result.defender_final_hp,
        "conquered": conquered,
        "battle_log": [line for r in result.rounds for line in r.log_lines],
    }
    return resp


def get_conquest_history(db: Session, limit: int = 10) -> list[dict]:
    """取得制覇紀錄。"""
    records = (
        db.query(Tournament)
        .order_by(Tournament.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": t.id,
            "winner_name": t.winner_name,
            "created_at": t.created_at,
        }
        for t in records
    ]
