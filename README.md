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

複製設定範本：

```bash
cp app/.config.example.py app/config.py
```

環境變數透過 `.env` 設定，預設使用 SQLite：

```env
DATABASE_URL=sqlite:///./dev.db
SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=43200
```

`app/config.py` 內含所有遊戲常數（冷卻時間、經驗倍數、金幣上限等），可依需求調整。此檔案已被 `.gitignore` 排除，不會提交至版本庫。

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

### 啟動開發伺服器

```bash
uvicorn app.main:app --reload
```

瀏覽器開啟 http://127.0.0.1:8000/view/home

### 執行測試

```bash
python -m pytest tests/ -v
```

## 正式環境部署

以下為在 Linux 伺服器上部署的步驟（以 Ubuntu/Debian 為例）。

### 1. 系統準備

```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv nginx
```

### 2. 建立專案目錄

```bash
sudo useradd -r -s /bin/false ffaicu
sudo mkdir -p /opt/ffaicu
sudo chown ffaicu:ffaicu /opt/ffaicu

# 上傳或 clone 專案
cd /opt/ffaicu
git clone <repo-url> .
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[mariadb]"
```

### 3. 設定資料庫（MariaDB）

```bash
sudo apt install -y mariadb-server
sudo mysql -u root -e "
  CREATE DATABASE ffaicu CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
  CREATE USER 'ffaicu'@'localhost' IDENTIFIED BY 'your-db-password';
  GRANT ALL PRIVILEGES ON ffaicu.* TO 'ffaicu'@'localhost';
  FLUSH PRIVILEGES;
"
```

### 4. 設定環境變數

```bash
cp app/.config.example.py app/config.py
```

編輯 `.env`：

```env
DATABASE_URL=mysql+pymysql://ffaicu:your-db-password@localhost:3306/ffaicu
SECRET_KEY=<使用 openssl rand -hex 32 產生>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=43200
```

編輯 `app/config.py`，將遊戲常數調整為正式環境值（冷卻時間、經驗倍數等）。可參考 `app/.config.example.py` 的預設值。

### 5. 初始化資料庫

```bash
cd /opt/ffaicu
source .venv/bin/activate

# 首次啟動會自動建表（main.py 中的 create_all + _auto_migrate）
# 匯入遊戲資料
python scripts/seed_data.py
```

### 6. 設定 systemd 服務

建立 `/etc/systemd/system/ffaicu.service`：

```ini
[Unit]
Description=FF Adventure いく改 v2.0
After=network.target mariadb.service

[Service]
Type=exec
User=ffaicu
Group=ffaicu
WorkingDirectory=/opt/ffaicu
ExecStart=/opt/ffaicu/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5
Environment=PATH=/opt/ffaicu/.venv/bin:/usr/bin

[Install]
WantedBy=multi-user.target
```

啟用並啟動：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ffaicu
sudo systemctl status ffaicu
```

### 7. 設定 Nginx 反向代理

建立 `/etc/nginx/sites-available/ffaicu`：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 10M;

    location /static/ {
        alias /opt/ffaicu/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

啟用站點：

```bash
sudo ln -s /etc/nginx/sites-available/ffaicu /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 8. HTTPS（選配）

使用 Let's Encrypt 自動取得憑證：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 部署後驗證

```bash
# 檢查服務狀態
sudo systemctl status ffaicu

# 查看應用日誌
sudo journalctl -u ffaicu -f

# 測試連線
curl -I http://localhost:8000/view/home
```

### 更新部署

```bash
cd /opt/ffaicu
git pull
source .venv/bin/activate
pip install -e ".[mariadb]"
sudo systemctl restart ffaicu
```

新增的資料庫欄位會由 `_auto_migrate()` 自動補齊，無需手動執行遷移。

## 遊戲功能

### 角色系統
- 建立角色（選擇初始職業）
- 7 維能力值（力量、魔力、信仰、體力、敏捷、速度、魅力）+ 業值
- 31 個職業，各有獨立攻擊公式與升級成長率
- 升級時各屬性 50% 機率獨立成長，HP 與體力連動（比照原版）
- 轉職系統與職業熟練度（精通需達 60）
- 稱號系統（新手→冒險者→熟練者→勇者→傳說的霸者），透過傳說之地晉升
- 業值（karma）用於技能公式計算與轉職條件

### 戰鬥系統
- **怪物戰鬥** — 10 個區域，管理員可動態開關
- **冠軍挑戰** — 擊敗現任冠軍即可取代
- **PvP 對戰** — 指定對手進行對戰
- **Boss 戰鬥** — 傳說之地，依稱號等級解鎖
- **武道會** — 玩家逐場挑戰制（打敗冠軍取得參賽資格）

戰鬥引擎為純邏輯模組，支援：暴擊、Limit Break、技能觸發、飾品效果、迴避判定、職業防禦加成、塔羅牌、即死攻擊、傷害反彈、戰鬥逃脫等。

### 技能系統
- **角色必殺技**（81 種）— 進攻型、防禦型，含觸發條件與公式
- **飾品技能**（25 種）— 減傷、增傷、回復、即死等
- **魔物技能**（81 種）— 與角色技能對應
- **冠軍飾品技能**（25 種）— 冠軍專用變體
- 所有技能以 JSON 定義，透過安全公式解析器（recursive descent parser）執行

### 經濟系統
- 武器店 / 防具店 / 飾品店（飾品顯示能力加成與戰鬥技能）
- 購買時自動將舊裝備存入倉庫（倉庫滿時阻止購買）
- 銀行（存取款，千 G 為單位）
- 金幣不足時自動從銀行補差額
- 倉庫（武器 / 防具 / 飾品分類存放）

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

## 遊戲常數

可在 `app/config.py` 調整的主要遊戲參數：

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `turn` | 150 | 戰鬥最大回合數 |
| `b_time` | 30 | PvP / 冠軍戰冷卻秒數 |
| `m_time` | 30 | 魔物戰鬥冷卻秒數 |
| `sentou_limit` | 9999 | 每日可戰鬥次數上限 |
| `exp_multiplier` | 1.0 | 經驗值倍數 |
| `gold_multiplier` | 1.0 | 金幣倍數 |
| `job_level_per_win` | 1.0 | 勝利時職業熟練度增加量 |
| `lv_up` | 300 | 升級經驗係數（exp ≥ level × lv_up 時升級）|
| `gold_max` | 999999999999 | 持有金幣上限 |
| `yado_dai` | 10 | 旅店費用係數（費用 = level × yado_dai）|

完整參數請參考 `app/.config.example.py`。

## 目錄結構

```
├── app/
│   ├── main.py              # FastAPI 入口，自動建表 + 自動遷移
│   ├── config.py            # 環境設定與遊戲常數（gitignored）
│   ├── .config.example.py   # 設定範本（已提交）
│   ├── database.py          # SQLAlchemy 引擎
│   ├── dependencies.py      # 依賴注入（DB session、JWT 認證）
│   ├── models/              # SQLAlchemy ORM 模型（14 個表）
│   ├── routers/             # API 路由（17 模組）+ 前端視圖路由
│   ├── services/            # 業務邏輯層（8 個服務）
│   ├── schemas/             # Pydantic 請求/回應定義
│   ├── engine/              # 戰鬥引擎（純邏輯，可獨立測試）
│   │   ├── battle_core.py   # 統一戰鬥迴圈
│   │   ├── battle_state.py  # Combatant / RoundState / BattleResult
│   │   ├── critical.py      # 暴擊率計算
│   │   ├── damage.py        # 職業攻擊公式（查 jobs.json）
│   │   ├── evasion.py       # 迴避判定
│   │   ├── formula_parser.py # 安全公式解析器（recursive descent）
│   │   ├── skill_executor.py # JSON 技能效果執行器（20+ 效果類型）
│   │   └── level_up.py      # 升級邏輯（比照原版公式）
│   └── templates/           # Jinja2 HTML 模板（32 頁，復古 RPG 風格）
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
├── static/
│   └── rpg.css              # 遊戲 UI 樣式
└── tests/                   # pytest 測試
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
| `GET/POST /tournament` | 武道會 |
| `GET/POST /shop/{weapon,armor,accessory}` | 商店 |
| `GET/POST /bank` | 銀行 |
| `GET/POST /warehouse` | 倉庫 |
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
| `tensyoku.cgi`（轉職） | `app/services/character_service.py` |
| `tenka.cgi`（武道會） | `app/services/tournament_service.py` |
| 升級公式（`battle.pl` L127-233） | `app/engine/level_up.py` |

## 授權

本專案為 FF Adventure いく改 v2.00 的非官方重構。
