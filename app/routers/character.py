from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.character import Character
from app.services.character_service import allocate_stat

router = APIRouter(prefix="/character", tags=["角色"])


class AllocateStatRequest(BaseModel):
    stat: str = Field(pattern=r"^(str|mag|fai|vit|dex|spd|cha)$")


@router.get("/stats")
def get_stats(current_user: Character = Depends(get_current_user)):
    return {
        "str": current_user.str_,
        "mag": current_user.mag,
        "fai": current_user.fai,
        "vit": current_user.vit,
        "dex": current_user.dex,
        "spd": current_user.spd,
        "cha": current_user.cha,
        "karma": current_user.karma,
        "available_points": current_user.karma,
    }


@router.post("/stats")
def allocate(
    req: AllocateStatRequest,
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    return allocate_stat(db, current_user, req.stat)
