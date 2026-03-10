from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.services.ranking_service import RANKING_CATEGORIES, get_ranking

router = APIRouter(prefix="/ranking", tags=["排行榜"])


@router.get("")
def ranking(
    category: str = Query(default="level", description="level/hp/str/mag/fai/vit/dex/spd/cha/karma/gold/wins"),
    db: Session = Depends(get_db),
):
    return {
        "category": category,
        "available_categories": list(RANKING_CATEGORIES.keys()),
        "rankings": get_ranking(db, category),
    }
