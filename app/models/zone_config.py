from sqlalchemy import Boolean, Column, String

from app.database import Base


class ZoneConfig(Base):
    __tablename__ = "zone_config"

    zone = Column(String(32), primary_key=True)
    open = Column(Boolean, nullable=False, default=True)
