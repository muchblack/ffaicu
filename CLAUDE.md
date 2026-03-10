# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案概述

**FF Adventure いく改 v2.0** — 從 Perl CGI 完全重構為 Python 的瀏覽器 RPG 遊戲。

- **框架**: FastAPI + SQLAlchemy 2.0 + Jinja2
- **資料庫**: SQLAlchemy ORM，透過 `DATABASE_URL` 環境變數切換 SQLite（開發）/ MariaDB（生產）
- **認證**: JWT (HS256) 存於 HttpOnly cookie
- **技能系統**: JSON 資料驅動（data/skills/），不用 eval，使用安全的公式解析器

## 常用指令

```bash
# 安裝依賴
pip install -e ".[dev]"

# 開發伺服器
cd ffaicu-py && uvicorn app.main:app --reload

# 跑全部測試
cd ffaicu-py && python -m pytest tests/ -v

# 跑單一測試
python -m pytest tests/test_formula_parser.py::test_complex_formula -v

# MariaDB 連線（需安裝 pymysql）
pip install ".[mariadb]"
# 在 .env 設定 DATABASE_URL=mysql+pymysql://user:pass@host/db
```

## 架構

```
HTTP → FastAPI routers → services → SQLAlchemy models → DB
                       → engine (純邏輯，零 I/O)
```

### 目錄結構

- `app/routers/` — FastAPI 路由（對應原 CGI 腳本）
- `app/models/` — SQLAlchemy ORM 模型（對應原 charalog/*.cgi 等檔案儲存）
- `app/schemas/` — Pydantic request/response schemas
- `app/services/` — 業務邏輯層
- `app/engine/` — **戰鬥引擎**（純邏輯、無 I/O、可獨立測試）
  - `battle_core.py` — 統一戰鬥迴圈
  - `damage.py` — 職業公式查表（讀 data/jobs.json）
  - `formula_parser.py` — 安全公式解析器（recursive descent，不用 eval）
  - `skill_executor.py` — JSON 技能效果執行器
- `data/` — 靜態遊戲資料（JSON）
  - `jobs.json` — 31 個職業定義 + 攻擊公式
  - `skills/` — 角色/飾品/魔物/冠軍技能 JSON
- `scripts/` — 一次性遷移工具（舊 Perl 資料 → DB）

### 戰鬥引擎設計原則

- **Combatant** / **RoundState** / **BattleResult** 是 dataclass，無副作用
- BattleEngine.execute() 是純函數，輸入兩個 Combatant + BattleMode，輸出 BattleResult
- 職業攻擊公式全部在 `data/jobs.json` 查表，不寫死在程式碼
- 技能效果在 `data/skills/*.json` 定義，skill_executor 解析執行
- 公式字串（如 `"(str + job_level) * rand(50)"`）由 formula_parser 安全解析

### 資料庫切換

`app/config.py` 讀 `.env` 的 `DATABASE_URL`：
- SQLite: `sqlite:///./dev.db`
- MariaDB: `mysql+pymysql://user:pass@host:3306/dbname`

### 原始 Perl 對照

原始 Perl CGI 程式碼在上層目錄 `../`（*.cgi + *.pl）。改寫時參照：
- `regist.pl` → `app/models/` + `app/services/`
- `battle.pl` / `wbattle.pl` / `mbattle.pl` → `app/engine/`
- `data/ffadventure.ini` → `app/config.py` + `data/jobs.json`
- `tech/*.pl` → `data/skills/character_skills.json`
