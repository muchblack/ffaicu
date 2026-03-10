from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.models import *  # noqa: F401,F403 — 確保所有模型已註冊
from app.routers import (
    admin,
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
app.include_router(admin.router)

# 前端視圖路由
app.include_router(views.router)
