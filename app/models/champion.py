from sqlalchemy import BigInteger, Column, Integer, String, Text

from app.database import Base


class Champion(Base):
    """冠軍資料（永遠只有一列）。snapshot_json 存完整角色+裝備快照。"""
    __tablename__ = "champion"

    id = Column(Integer, primary_key=True, default=1)
    character_id = Column(String(32), nullable=True)
    character_name = Column(String(64), default="")
    win_streak = Column(Integer, default=0)
    bounty = Column(BigInteger, default=0)
    snapshot_json = Column(Text, default="{}")
