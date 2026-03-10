from sqlalchemy import BigInteger, Column, Integer, String

from app.database import Base


class OnlinePlayer(Base):
    __tablename__ = "online_players"

    character_id = Column(String(32), primary_key=True)
    character_name = Column(String(64), default="")
    last_seen = Column(BigInteger, default=0)
    level = Column(Integer, default=0)
