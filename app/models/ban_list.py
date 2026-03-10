from sqlalchemy import Column, Integer, String

from app.database import Base


class BanEntry(Base):
    __tablename__ = "ban_list"

    id = Column(Integer, primary_key=True, autoincrement=True)
    character_id = Column(String(32), nullable=False, index=True)
    target_id = Column(String(32), nullable=False)  # "all" 表示拒絕所有
    status = Column(Integer, default=1)              # 1=拒絕 2=好友
