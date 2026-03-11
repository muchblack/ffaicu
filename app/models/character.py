from sqlalchemy import BigInteger, Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from app.database import Base


class Character(Base):
    __tablename__ = "characters"

    # 基本資訊
    id = Column(String(32), primary_key=True)                    # [0] 登入 ID
    password_hash = Column(String(128), nullable=False)          # [1] bcrypt hash
    name = Column(String(64), nullable=False, unique=True, index=True)  # [4] 角色名
    site_name = Column(String(128), default="")                  # [2] 網站名
    url = Column(String(256), default="")                        # [3] 個人網站
    sex = Column(Integer, default=1)                             # [5] 0=女 1=男
    image_id = Column(Integer, default=0)                        # [6] 角色圖片

    # 七維能力值
    str_ = Column("str", Integer, default=10)                    # [7]
    mag = Column(Integer, default=10)                            # [8]
    fai = Column(Integer, default=10)                            # [9]
    vit = Column(Integer, default=10)                            # [10]
    dex = Column(Integer, default=10)                            # [11]
    spd = Column(Integer, default=10)                            # [12]
    cha = Column(Integer, default=10)                            # [13]

    # 職業與狀態
    job_class = Column(Integer, default=0)                       # [14] 職業 0-30
    current_hp = Column(Integer, default=100)                    # [15]
    max_hp = Column(Integer, default=100)                        # [16]
    exp = Column(BigInteger, default=0)                          # [17]
    level = Column(Integer, default=1)                           # [18]
    gold = Column(BigInteger, default=0)                         # [19]
    karma = Column(Integer, default=0)                           # [20]

    # 戰鬥統計
    battle_count = Column(Integer, default=0)                    # [21]
    win_count = Column(Integer, default=0)                       # [22]
    battle_cry = Column(String(128), default="")                 # [23]
    available_battles = Column(Integer, default=9999)            # [25]
    last_battle_reset = Column(String(10), default="")           # YYYY-MM-DD 上次重置日期
    last_battle_time = Column(BigInteger, default=0)             # [27]
    boss_counter = Column(Integer, default=0)                    # [28] Boss 勝利計數
    tenka_counter = Column(Integer, default=0)                   # 武道會進度（0=未參賽, boss=可參賽, 遞減至制覇）

    # 戰技（原 Perl chara[30]：戰術選擇 = 戰鬥技能）
    tactic_id = Column(Integer, default=0)                       # [30]

    # 進度
    title_rank = Column(Integer, default=0)                      # [32]
    job_level = Column(Integer, default=0)                       # [33] 0-60
    bank_savings = Column(BigInteger, default=0)                 # [34]

    # 系統
    host = Column(String(128), default="")                       # [26]
    password_recovery = Column(String(64), default="")           # 密碼恢復用語
    protected = Column(Integer, default=0)                       # 管理員保護標記
    last_zone = Column(String(32), default="")                   # 上次狩獵區域
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # 關聯
    equipment = relationship("CharacterEquipment", back_populates="character", uselist=False, cascade="all, delete-orphan")
    job_masteries = relationship("JobMastery", back_populates="character", cascade="all, delete-orphan")
    warehouse_items = relationship("WarehouseItem", back_populates="character", cascade="all, delete-orphan")
