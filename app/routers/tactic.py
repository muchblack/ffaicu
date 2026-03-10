import json
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.character import Character
from app.services.character_service import change_tactic

router = APIRouter(prefix="/tactic", tags=["戰術"])


class TacticChangeRequest(BaseModel):
    tactic_id: int


@router.get("")
def list_tactics(current_user: Character = Depends(get_current_user)):
    path = Path(__file__).parent.parent.parent / "data" / "tactics.json"
    with open(path, encoding="utf-8") as f:
        tactics = json.load(f)

    job = current_user.job_class
    return {
        "current_tactic": current_user.tactic_id,
        "tactics": [
            {"id": int(k), "name": v["name"], "description": v["description"]}
            for k, v in tactics.items()
            if int(k) == 0 or job in v.get("job_classes", [])
        ],
    }


@router.post("")
def do_change_tactic(
    req: TacticChangeRequest,
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    return change_tactic(db, current_user, req.tactic_id)
