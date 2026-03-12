from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./dev.db"
    secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 43200  # 30 days
    admin_password: str = "1111"

    # 遊戲常數（原 ffadventure.ini）
    lv_up: int = 300             # 升級所需經驗值係數（exp >= level * lv_up 時升級）
    turn: int = 150              # 戰鬥最大回合數
    limit_days: int = 60         # 未戰鬥超過此天數的角色可被自動刪除
    gold_max: int = 999999999999          # 持有金幣上限
    bank_max: int = 999999999999000       # 銀行存款上限
    chara_max_lv: int = 99999    # 角色等級上限
    chara_max_hp: int = 99999999 # HP 上限
    chara_max_stat: int = 99999  # 單項能力值上限（STR/MAG/FAI/VIT/DEX/SPD/CHA/業）
    item_max: int = 8            # 武器倉庫格數上限
    def_max: int = 8             # 防具倉庫格數上限
    acs_max: int = 8             # 飾品倉庫格數上限
    b_time: int = 30             # 對人戰鬥冷卻秒數（PvP / 冠軍戰）
    m_time: int = 30             # 魔物戰鬥冷卻秒數（野外 / Boss）
    sentou_limit: int = 9999     # 每日可戰鬥次數上限
    yado_dai: int = 10           # 旅店費用係數（費用 = level * yado_dai）

    # 獎勵倍數
    exp_multiplier: float = 1.0  # 經驗值倍數（戰鬥獎勵）
    gold_multiplier: float = 1.0 # 金錢倍數（戰鬥獎勵）
    job_level_per_win: float = 1.0  # 戰鬥勝利時職業熟練度增加量（0=不增加）
    job_change_penalty: bool = True  # 轉職時精通<20是否扣屬性值

    # 武道會（原 tenka.cgi）
    tenka_su: int = 3            # 武道會參賽人數
    kiso_exp: int = 30           # 武道會經驗值乘數（對手等級 × 此值）
    syoukin: int = 500           # 武道會賞金係數
    boss: int = 10               # 武道會計數器初始值（打敗冠軍後設定此值）

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
