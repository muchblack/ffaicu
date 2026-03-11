import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app.database import Base, engine
from app.models import *  # noqa: F401,F403 — 確保所有模型已註冊

logger = logging.getLogger(__name__)
from app.routers import (
    auth,
    bank,
    battle_champion,
    battle_monster,
    battle_select,
    character,
    job_change,
    message,
    ranking,
    shop,
    status,
    system,
    tactic,
    tournament,
    views,
    warehouse,
)

Base.metadata.create_all(bind=engine)


def _auto_migrate():
    """自動補齊 ORM 模型中存在但資料庫缺少的欄位（僅新增，不刪不改）。"""
    insp = inspect(engine)
    for table_name, table in Base.metadata.tables.items():
        if not insp.has_table(table_name):
            continue
        existing = {c["name"] for c in insp.get_columns(table_name)}
        for col in table.columns:
            if col.name not in existing:
                col_type = col.type.compile(engine.dialect)
                default = ""
                if col.default is not None:
                    dv = col.default.arg
                    default = f" DEFAULT '{dv}'" if isinstance(dv, str) else f" DEFAULT {dv}"
                stmt = f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type}{default}"
                with engine.begin() as conn:
                    conn.execute(text(stmt))
                logger.info("Auto-migrated: %s.%s (%s)", table_name, col.name, col_type)


_auto_migrate()

app = FastAPI(title="FF ADVENTURE いく改", version="2.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")

# API 路由
app.include_router(system.router)
app.include_router(auth.router)
app.include_router(status.router)
app.include_router(battle_champion.router)
app.include_router(battle_monster.router)
app.include_router(battle_select.router)
app.include_router(tournament.router)
app.include_router(shop.router)
app.include_router(bank.router)
app.include_router(warehouse.router)
app.include_router(job_change.router)
app.include_router(tactic.router)
app.include_router(character.router)
app.include_router(message.router)
app.include_router(ranking.router)

# 前端視圖路由
app.include_router(views.router)
