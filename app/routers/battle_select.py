from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.character import Character
from app.services.battle_service import fight_pvp

router = APIRouter(prefix="/battle", tags=["戰鬥"])


class PvPRequest(BaseModel):
    opponent_id: str = Field(min_length=1)


@router.get("/select")
def list_opponents(
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    characters = (
        db.query(Character)
        .filter(Character.id != current_user.id)
        .order_by(Character.level.desc())
        .limit(50)
        .all()
    )
    return [
        {"id": c.id, "name": c.name, "level": c.level, "job_class": c.job_class}
        for c in characters
    ]


@router.post("/select")
def battle_select(
    req: PvPRequest,
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    return fight_pvp(db, current_user, req.opponent_id)
