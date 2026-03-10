from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class JobMastery(Base):
    __tablename__ = "job_mastery"

    character_id = Column(String(32), ForeignKey("characters.id", ondelete="CASCADE"), primary_key=True)
    job_class = Column(Integer, primary_key=True)  # 0-30
    mastery_level = Column(Integer, default=0)      # 0-60

    character = relationship("Character", back_populates="job_masteries")
