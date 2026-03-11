# FF Adventure いく改 v2.0

**FF Adventure いく改**（Final Fantasy 冒險 いく改）的 Python 完全重構版。

原作為 2000 年代的 Perl CGI 瀏覽器 RPG 遊戲（29 個 CGI 腳本、6 個核心模組、140+ 個技能檔案、純檔案系統儲存），現以 Python 全面改寫，完整還原原版的戰鬥公式、升級機制與技能系統。

## 技術架構

| 層級 | 技術 |
|------|------|
| Web 框架 | FastAPI + Jinja2 模板 |
| ORM | SQLAlchemy 2.0 |
| 資料庫 | SQLite（開發）/ MariaDB（生產），透過 `DATABASE_URL` 切換 |
| 認證 | JWT (HS256)，存於 HttpOnly Cookie |
| 技能系統 | JSON 資料驅動（81 角色技能 + 25 飾品技能 + 81 魔物技能 + 25 冠軍飾品技能），安全公式解析器（不使用 eval） |

```
HTTP 請求 → FastAPI 路由 → 服務層 → SQLAlchemy 模型 → 資料庫
                         → 戰鬥引擎（純邏輯，零 I/O）
```

## 快速開始

### 環境需求

- Python 3.11+

### 安裝

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 設定

專案已附帶 `.env`，預設使用 SQLite。如需自訂：

```env
DATABASE_URL=sqlite:///./dev.db
SECRET_KEY=your-secret-key-here
```

若使用 MariaDB：

```bash
pip install ".[mariadb]"
```

```env
DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/ffaicu
```

### 匯入遊戲資料

從原始 Perl 資料檔案匯入怪物、武器、防具、飾品：

```bash
python scripts/seed_data.py
```

匯入內容：
- 667 隻怪物（10 個區域）
- 160 把武器
- 129 件防具
- 86 個飾品

### 啟動伺服器

```bash
uvicorn app.main:app --reload
```

瀏覽器開啟 http://127.0.0.1:8000/view/home

### 執行測試

```bash
python -m pytest tests/ -v
```

## 遊戲功能

### 角色系統
- 建立角色（選擇初始職業）
- 7 維能力值（力量、魔力、信仰、體力、敏捷、速度、魅力）+ 業值
- 31 個職業，各有獨立攻擊公式與升級成長率
- 升級時各屬性 50% 機率獨立成長，HP 與體力連動（比照原版）
- 轉職系統與職業修練度
- 業值可手動分配到任意屬性

### 戰鬥系統
- **怪物戰鬥** — 10 個區域，管理員可動態開關
- **冠軍挑戰** — 擊敗現任冠軍即可取代
- **PvP 對戰** — 指定對手進行對戰
- **武道會** — 錦標賽模式

戰鬥引擎為純邏輯模組，支援：暴擊、Limit Break、技能觸發、飾品效果、迴避判定、職業防禦加成、塔羅牌、即死攻擊、傷害反彈、戰鬥逃脫等。

### 技能系統
- **角色必殺技**（81 種）— 進攻型、防禦型，含觸發條件與公式
- **飾品技能**（25 種）— 減傷、增傷、回復、即死等
- **魔物技能**（81 種）— 與角色技能對應
- **冠軍飾品技能**（25 種）— 冠軍專用變體
- 所有技能以 JSON 定義，透過安全公式解析器（recursive descent parser）執行

### 經濟系統
- 武器店 / 防具店 / 飾品店（飾品顯示能力加成與戰鬥技能）
- 銀行（存取款，千 G 為單位）
- 倉庫

### 社交系統
- 訊息收發
- 全體廣播
- 排行榜（12 個分類）

### 管理後台
- 角色管理（搜尋、保護、刪除不活躍角色）
- 商品管理（武器 / 防具 / 飾品 CRUD）
- 魔物管理（按區域瀏覽、新增 / 編輯 / 刪除）
- 區域開關（暫時關閉特定狩獵區域）
- 職業與技能一覽
- 全體廣播
- 資料總覽（角色、武器、防具、飾品、魔物統計）

## 目錄結構

```
├── app/
│   ├── main.py              # FastAPI 入口，自動建表
│   ├── config.py            # 環境設定與 21 項遊戲常數
│   ├── database.py          # SQLAlchemy 引擎
│   ├── dependencies.py      # 依賴注入（DB session、JWT 認證）
│   ├── models/              # SQLAlchemy ORM 模型（14 個表）
│   ├── routers/             # API 路由（16 模組）+ 前端視圖路由
│   ├── services/            # 業務邏輯層
│   ├── schemas/             # Pydantic 請求/回應定義
│   ├── engine/              # 戰鬥引擎（純邏輯，可獨立測試）
│   │   ├── battle_core.py   # 統一戰鬥迴圈
│   │   ├── battle_state.py  # Combatant / RoundState / BattleResult
│   │   ├── damage.py        # 職業攻擊公式（查 jobs.json）
│   │   ├── formula_parser.py # 安全公式解析器（recursive descent）
│   │   ├── skill_executor.py # JSON 技能效果執行器（20+ 效果類型）
│   │   └── level_up.py      # 升級邏輯（比照原版公式）
│   └── templates/           # Jinja2 HTML 模板（復古 RPG 風格）
├── data/
│   ├── jobs.json            # 31 個職業定義、攻擊公式、升級成長率
│   ├── tactics.json         # 戰術定義
│   ├── skills/              # 技能 JSON
│   │   ├── character_skills.json        # 角色必殺技（81 種）
│   │   ├── accessory_skills.json        # 飾品技能（25 種）
│   │   ├── monster_skills.json          # 魔物技能（81 種）
│   │   └── champion_accessory_skills.json # 冠軍飾品技能（25 種）
│   └── importData/          # 原始 Perl 資料（供 seed_data.py 匯入）
├── scripts/
│   └── seed_data.py         # 從原始 Perl 資料匯入 DB
├── static/                  # CSS / JS / 圖片
└── tests/                   # pytest 測試（20 個測試案例）
```

## API 端點

遊戲提供兩種存取方式：

- **HTML 前端** — `/view/*` 路徑，透過瀏覽器操作遊戲
- **JSON API** — RESTful API，供程式化存取

### 主要 API 路由

| 路徑 | 說明 |
|------|------|
| `GET /` | 首頁（冠軍資訊、線上玩家） |
| `POST /auth/login` | 登入 |
| `POST /auth/register` | 建立角色 |
| `GET /status` | 角色狀態 |
| `POST /battle/champion` | 冠軍戰 |
| `POST /battle/monster` | 怪物戰（zone 參數） |
| `GET/POST /battle/select` | PvP 對戰 |
| `GET/POST /shop/{weapon,armor,accessory}` | 商店 |
| `GET/POST /bank` | 銀行 |
| `GET/POST /job/change` | 轉職 |
| `GET /ranking` | 排行榜 |
| `GET/POST /message` | 訊息 |
| `POST /admin/*` | 管理後台 |

## 原始 Perl 版對照

原始 Perl CGI 程式碼位於 `/code/cgi/ffaicu/`。主要對應關係：

| 原始 Perl | Python 對應 |
|-----------|-------------|
| `battle.pl` / `wbattle.pl` / `mbattle.pl` | `app/engine/` |
| `regist.pl`（角色 I/O） | `app/models/` + `app/services/` |
| `data/ffadventure.ini`（遊戲常數） | `app/config.py` |
| `data/syoku.ini`（職業定義） | `data/jobs.json` |
| `data/*mons.ini`（怪物資料） | `monsters` 表（透過 seed_data.py 匯入） |
| `data/item/*.ini` / `def/*.ini` / `acs/*.ini` | 商品目錄表 |
| `tech/*.pl`（81 個角色技能） | `data/skills/character_skills.json` |
| `wtech/*.pl`（81 個魔物技能） | `data/skills/monster_skills.json` |
| `acstech/*.pl`（25 個飾品技能） | `data/skills/accessory_skills.json` |
| `wacstech/*.pl`（25 個冠軍飾品技能） | `data/skills/champion_accessory_skills.json` |
| 升級公式（`battle.pl` L127-233） | `app/engine/level_up.py` |

## 授權

本專案為 FF Adventure いく改 v2.00 的非官方重構。
