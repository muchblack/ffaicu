"""排行榜服務層。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.character import Character


RANKING_CATEGORIES = {
    "level": Character.level,
    "hp": Character.max_hp,
    "str": Character.str_,
    "mag": Character.mag,
    "fai": Character.fai,
    "vit": Character.vit,
    "dex": Character.dex,
    "spd": Character.spd,
    "cha": Character.cha,
    "karma": Character.karma,
    "gold": Character.gold,
    "wins": Character.win_count,
}


def get_ranking(db: Session, category: str = "level", limit: int = 50) -> list[dict]:
    col = RANKING_CATEGORIES.get(category)
    if col is None:
        col = Character.level
        category = "level"

    rows = (
        db.query(Character)
        .order_by(col.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "rank": i + 1,
            "id": c.id,
            "name": c.name,
            "level": c.level,
            "job_class": c.job_class,
            "value": getattr(c, "str_" if category == "str" else category, 0),
        }
        for i, c in enumerate(rows)
    ]
