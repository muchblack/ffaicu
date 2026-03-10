from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./dev.db"
    secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 43200  # 30 days

    # 遊戲常數（原 ffadventure.ini）
    lv_up: int = 300
    turn: int = 150
    limit_days: int = 60
    gold_max: int = 999999999999
    bank_max: int = 999999999999000
    chara_max_lv: int = 99999
    chara_max_hp: int = 99999999
    chara_max_stat: int = 99999
    item_max: int = 8
    def_max: int = 8
    acs_max: int = 8
    b_time: int = 30
    m_time: int = 30
    sentou_limit: int = 9999
    yado_dai: int = 10

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
