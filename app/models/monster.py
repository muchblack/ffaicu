from sqlalchemy import BigInteger, Column, Integer, String

from app.database import Base


class Monster(Base):
    __tablename__ = "monsters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    zone = Column(String(32), nullable=False, index=True)  # low/normal/high/special/isekai/boss0-3
    name = Column(String(64), nullable=False)
    exp_reward = Column(Integer, default=0)
    damage_range = Column(Integer, default=0)
    speed = Column(Integer, default=0)
    base_damage = Column(Integer, default=0)
    evasion = Column(Integer, default=0)
    skill_id = Column(Integer, default=0)      # mons/*.pl ID
    critical_rate = Column(Integer, default=0)
    gold_drop = Column(BigInteger, default=0)
