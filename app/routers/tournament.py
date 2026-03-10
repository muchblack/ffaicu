"""天下第一武道会。"""

import time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.engine.battle_core import BattleEngine
from app.engine.battle_state import BattleMode
from app.models.character import Character
from app.models.tournament import Tournament, TournamentEntry
from app.services.battle_service import _char_to_combatant

router = APIRouter(prefix="/tournament", tags=["天下第一武道會"])

_TOURNAMENT_INTERVAL = 86400  # 24 時間


@router.get("")
def get_tournament(
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    latest = db.query(Tournament).order_by(Tournament.id.desc()).first()
    now = int(time.time())

    if latest and (now - latest.created_at) < _TOURNAMENT_INTERVAL:
        entries = (
            db.query(TournamentEntry)
            .filter(TournamentEntry.tournament_id == latest.id)
            .order_by(TournamentEntry.round_reached.desc())
            .all()
        )
        return {
            "status": "completed",
            "winner": latest.winner_name,
            "created_at": latest.created_at,
            "entries": [
                {"name": e.character_name, "level": e.level, "round_reached": e.round_reached}
                for e in entries
            ],
        }

    return {"status": "ready", "message": "可以開催武道會"}


@router.post("")
def run_tournament(
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    latest = db.query(Tournament).order_by(Tournament.id.desc()).first()
    now = int(time.time())
    if latest and (now - latest.created_at) < _TOURNAMENT_INTERVAL:
        return {"error": "武道會每日僅限一次"}

    # 全角色參加
    characters = db.query(Character).order_by(Character.level.desc()).limit(32).all()
    if len(characters) < 2:
        return {"error": "參加者不足"}

    # 建立錦標賽
    tournament = Tournament(created_at=now)
    db.add(tournament)
    db.flush()

    # 執行錦標賽（單淘汰制）
    engine = BattleEngine(max_rounds=50)
    participants = list(characters)
    round_num = 1
    results_log: list[str] = []

    while len(participants) > 1:
        next_round = []
        for i in range(0, len(participants) - 1, 2):
            a = participants[i]
            b = participants[i + 1]
            ca = _char_to_combatant(a, a.equipment)
            cb = _char_to_combatant(b, b.equipment)
            result = engine.execute(ca, cb, BattleMode.PVP_SELECT)
            winner = a if result.outcome == "win" else b
            loser = b if result.outcome == "win" else a

            entry = TournamentEntry(
                tournament_id=tournament.id,
                character_id=loser.id,
                character_name=loser.name,
                level=loser.level,
                round_reached=round_num,
            )
            db.add(entry)
            next_round.append(winner)
            results_log.append(f"R{round_num}: {a.name} vs {b.name} → {winner.name}")

        # 奇數時，最後一人輪空
        if len(participants) % 2 == 1:
            next_round.append(participants[-1])

        participants = next_round
        round_num += 1

    # 優勝者
    champion = participants[0]
    entry = TournamentEntry(
        tournament_id=tournament.id,
        character_id=champion.id,
        character_name=champion.name,
        level=champion.level,
        round_reached=round_num,
    )
    db.add(entry)
    tournament.winner_name = champion.name
    db.commit()

    return {
        "status": "completed",
        "winner": champion.name,
        "results": results_log,
    }
