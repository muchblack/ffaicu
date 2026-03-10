from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.character import Character
from app.services.battle_service import fight_champion

router = APIRouter(prefix="/battle", tags=["戰鬥"])


@router.post("/champion")
def battle_champion(
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    return fight_champion(db, current_user)
