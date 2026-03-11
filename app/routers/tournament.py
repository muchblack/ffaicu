"""天下第一武道會 — 玩家逐場挑戰制（對齊 Perl tenka.cgi）。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.character import Character
from app.services.tournament_service import (
    fight_tournament,
    get_conquest_history,
    get_tournament_state,
)

router = APIRouter(prefix="/tournament", tags=["天下第一武道會"])


@router.get("")
def api_tournament_state(
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    return get_tournament_state(db, current_user)


@router.post("/fight")
def api_tournament_fight(
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    return fight_tournament(db, current_user)


@router.get("/history")
def api_tournament_history(
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    return get_conquest_history(db)
