import json
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.character import Character
from app.models.job_mastery import JobMastery
from app.services.character_service import change_job

router = APIRouter(prefix="/job", tags=["轉職"])


class JobChangeRequest(BaseModel):
    job_class: int = Field(ge=0, le=30)


@router.get("/change")
def list_jobs(
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    path = Path(__file__).parent.parent.parent / "data" / "jobs.json"
    with open(path, encoding="utf-8") as f:
        jobs = json.load(f)

    masteries = {
        m.job_class: m.mastery_level
        for m in db.query(JobMastery).filter(JobMastery.character_id == current_user.id).all()
    }

    return {
        "current_job": current_user.job_class,
        "current_job_level": current_user.job_level,
        "jobs": [
            {
                "id": int(k),
                "name": v["name"],
                "mastery": masteries.get(int(k), 0),
                "mastered": masteries.get(int(k), 0) >= 60,
            }
            for k, v in jobs.items()
        ],
    }


@router.post("/change")
def do_change_job(
    req: JobChangeRequest,
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    return change_job(db, current_user, req.job_class)
