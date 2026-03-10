"""設定所有測試使用同一 SQLite 測試資料庫。"""

import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
