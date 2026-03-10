from sqlalchemy import BigInteger, Column, Integer, String

from app.database import Base


class LoginLog(Base):
    __tablename__ = "login_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    character_id = Column(String(32), nullable=False, index=True)
    password_attempt = Column(String(128), default="")
    host = Column(String(128), default="")
    timestamp = Column(BigInteger, default=0)
    success = Column(Integer, default=0)  # 0=失敗 1=成功
