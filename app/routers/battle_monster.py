from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.character import Character
from app.services.battle_service import fight_boss, fight_monster

router = APIRouter(prefix="/battle", tags=["戰鬥"])


class MonsterBattleRequest(BaseModel):
    zone: str = Field(description="low / normal / high / special / isekai / genei")


class BossBattleRequest(BaseModel):
    boss_tier: int = Field(ge=0, le=3)


@router.post("/monster")
def battle_monster(
    req: MonsterBattleRequest,
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    return fight_monster(db, current_user, req.zone)


@router.post("/boss")
def battle_boss(
    req: BossBattleRequest,
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    return fight_boss(db, current_user, req.boss_tier)
