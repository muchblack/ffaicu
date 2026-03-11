from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.character import Character

router = APIRouter(prefix="/character", tags=["角色"])


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
    }
