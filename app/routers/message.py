import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.ban_list import BanEntry
from app.models.character import Character
from app.models.message import BroadcastMessage, Message

router = APIRouter(prefix="/message", tags=["訊息"])


class SendMessageRequest(BaseModel):
    recipient_id: str = Field(min_length=1)
    content: str = Field(min_length=1, max_length=500)


class BroadcastRequest(BaseModel):
    content: str = Field(min_length=1, max_length=500)


class BanRequest(BaseModel):
    target_id: str = Field(min_length=1)
    status: int = Field(ge=1, le=2, description="1=封鎖 2=好友")


@router.get("")
def get_messages(
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    inbox = (
        db.query(Message)
        .filter(Message.recipient_id == current_user.id)
        .order_by(Message.created_at.desc())
        .limit(30)
        .all()
    )
    broadcasts = (
        db.query(BroadcastMessage)
        .order_by(BroadcastMessage.created_at.desc())
        .limit(10)
        .all()
    )
    return {
        "inbox": [
            {"sender_name": m.sender_name, "content": m.content, "time": m.created_at}
            for m in inbox
        ],
        "broadcasts": [
            {"sender_name": b.sender_name, "content": b.content, "time": b.created_at}
            for b in broadcasts
        ],
    }


@router.post("/send")
def send_message(
    req: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    recipient = db.query(Character).filter(Character.id == req.recipient_id).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="找不到對方")

    # 封鎖名單確認
    ban = (
        db.query(BanEntry)
        .filter(
            BanEntry.character_id == req.recipient_id,
            BanEntry.target_id.in_([current_user.id, "all"]),
            BanEntry.status == 1,
        )
        .first()
    )
    if ban:
        raise HTTPException(status_code=403, detail="無法傳送訊息給對方")

    msg = Message(
        sender_id=current_user.id,
        sender_name=current_user.name,
        recipient_id=req.recipient_id,
        content=req.content,
        created_at=int(time.time()),
    )
    db.add(msg)
    db.commit()
    return {"message": "訊息已送出"}


@router.post("/broadcast")
def broadcast(
    req: BroadcastRequest,
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    msg = BroadcastMessage(
        sender_id=current_user.id,
        sender_name=current_user.name,
        content=req.content,
        created_at=int(time.time()),
    )
    db.add(msg)
    db.commit()
    return {"message": "廣播訊息已送出"}


@router.post("/ban")
def set_ban(
    req: BanRequest,
    db: Session = Depends(get_db),
    current_user: Character = Depends(get_current_user),
):
    existing = (
        db.query(BanEntry)
        .filter(BanEntry.character_id == current_user.id, BanEntry.target_id == req.target_id)
        .first()
    )
    if existing:
        existing.status = req.status
    else:
        entry = BanEntry(character_id=current_user.id, target_id=req.target_id, status=req.status)
        db.add(entry)
    db.commit()
    action = "封鎖" if req.status == 1 else "加為好友"
    return {"message": f"已將{req.target_id}{action}"}
