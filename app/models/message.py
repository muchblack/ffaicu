from sqlalchemy import BigInteger, Column, Integer, String, Text

from app.database import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sender_id = Column(String(32), nullable=False, index=True)
    sender_name = Column(String(64), default="")
    recipient_id = Column(String(32), nullable=False, index=True)
    content = Column(Text, default="")
    sender_host = Column(String(128), default="")
    created_at = Column(BigInteger, default=0)


class BroadcastMessage(Base):
    __tablename__ = "broadcast_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sender_id = Column(String(32), nullable=False)
    sender_name = Column(String(64), default="")
    content = Column(Text, default="")
    sender_host = Column(String(128), default="")
    created_at = Column(BigInteger, default=0)
