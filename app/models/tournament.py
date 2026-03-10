from sqlalchemy import BigInteger, Column, Integer, String, Text

from app.database import Base


class Tournament(Base):
    __tablename__ = "tournaments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(BigInteger, default=0)
    result_html = Column(Text, default="")
    winner_name = Column(String(64), default="")


class TournamentEntry(Base):
    __tablename__ = "tournament_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tournament_id = Column(Integer, nullable=False, index=True)
    character_id = Column(String(32), nullable=False)
    character_name = Column(String(64), default="")
    level = Column(Integer, default=0)
    round_reached = Column(Integer, default=0)
