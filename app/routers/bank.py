from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_current_user, get_db
from app.models.character import Character

router = APIRouter(prefix="/bank", tags=["銀行"])


class BankRequest(BaseModel):
    amount: int = Field(gt=0, description="金額（千G單位）")


@router.get("")
def bank_status(
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    return {
        "gold": int(current_user.gold),
        "bank_savings": int(current_user.bank_savings),
        "bank_max": settings.bank_max,
    }


@router.post("/deposit")
def deposit(
    req: BankRequest,
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    amount = req.amount * 1000
    if current_user.gold < amount:
        raise HTTPException(status_code=400, detail="金幣不足")
    if current_user.bank_savings + amount > settings.bank_max:
        raise HTTPException(status_code=400, detail="超過銀行存款上限")

    current_user.gold -= amount
    current_user.bank_savings += amount
    db.commit()
    return {
        "message": f"已存入{amount}G",
        "gold": int(current_user.gold),
        "bank_savings": int(current_user.bank_savings),
    }


@router.post("/withdraw")
def withdraw(
    req: BankRequest,
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    amount = req.amount * 1000
    if current_user.bank_savings < amount:
        raise HTTPException(status_code=400, detail="存款不足")
    if current_user.gold + amount > settings.gold_max:
        raise HTTPException(status_code=400, detail="超過持有金幣上限")

    current_user.bank_savings -= amount
    current_user.gold += amount
    db.commit()
    return {
        "message": f"已提領{amount}G",
        "gold": int(current_user.gold),
        "bank_savings": int(current_user.bank_savings),
    }
