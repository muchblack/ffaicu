"""整合測試：完整遊戲流程。"""

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app

client = TestClient(app)


def setup_module():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def teardown_module():
    Base.metadata.drop_all(bind=engine)


def _register_and_login(user_id: str, name: str) -> TestClient:
    c = TestClient(app)
    c.post("/auth/register", json={
        "id": user_id, "password": "testpass", "password_recovery": "secret",
        "name": name, "sex": 1, "image_id": 0, "job_class": 0,
    })
    return c


def test_full_game_flow():
    # 1. 註冊兩個角色
    player1 = _register_and_login("player1", "勇者雷恩")
    player2 = _register_and_login("player2", "魔法師露娜")

    # 2. 查看首頁（/ 重導向到 /view/home）
    resp = player1.get("/", follow_redirects=False)
    assert resp.status_code == 307

    # 3. 查看狀態
    resp = player1.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["character"]["name"] == "勇者雷恩"
    assert data["character"]["level"] == 1

    # 4. 旅店（HP 已滿應該失敗）
    resp = player1.post("/status/inn")
    assert resp.status_code == 400

    # 5. 查看能力值
    resp = player1.get("/character/stats")
    assert resp.status_code == 200
    assert resp.json()["str"] == 10

    # 6. 查看排行榜
    resp = player1.get("/ranking")
    assert resp.status_code == 200
    assert len(resp.json()["rankings"]) == 2

    # 7. PvP 對戰列表
    resp = player1.get("/battle/select")
    assert resp.status_code == 200
    opponents = resp.json()
    assert len(opponents) == 1
    assert opponents[0]["name"] == "魔法師露娜"

    # 8. PvP 對戰
    resp = player1.post("/battle/select", json={"opponent_id": "player2"})
    assert resp.status_code == 200
    assert resp.json()["outcome"] in ("win", "lose", "draw", "timeout")

    # 9. 職業一覽
    resp = player1.get("/job/change")
    assert resp.status_code == 200
    assert len(resp.json()["jobs"]) == 31

    # 10. 轉職（能力值不足應返回錯誤）
    resp = player1.post("/job/change", json={"job_class": 1})
    assert resp.status_code == 200
    assert "error" in resp.json()  # MAG 不足無法轉職

    # 11. 戰術一覽
    resp = player1.get("/tactic")
    assert resp.status_code == 200

    # 12. 銀行
    resp = player1.get("/bank")
    assert resp.status_code == 200
    assert resp.json()["gold"] == 0  # 新角色沒有錢

    # 13. 倉庫
    resp = player1.get("/warehouse")
    assert resp.status_code == 200
    assert resp.json() == []

    # 14. 訊息
    resp = player1.get("/message")
    assert resp.status_code == 200

    # 15. 發送訊息
    resp = player1.post("/message/send", json={
        "recipient_id": "player2", "content": "你好！"
    })
    assert resp.status_code == 200

    # 16. 接收者讀取訊息
    resp = player2.get("/message")
    assert resp.status_code == 200
    assert len(resp.json()["inbox"]) == 1
    assert resp.json()["inbox"][0]["content"] == "你好！"


def test_admin_flow():
    admin = TestClient(app)

    # 列出角色
    resp = admin.post("/admin/list-characters", json={"admin_password": "1111"})
    assert resp.status_code == 200
    assert len(resp.json()) >= 2

    # 搜尋角色
    resp = admin.post("/admin/search", json={"admin_password": "1111", "query": "player1"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "勇者雷恩"

    # 保護角色
    resp = admin.post("/admin/protect", json={"admin_password": "1111", "character_id": "player1"})
    assert resp.status_code == 200

    # 新增武器
    resp = admin.post("/admin/add-weapon", json={
        "admin_password": "1111",
        "id": 1001, "name": "鐵劍", "attack": 100, "price": 2500,
    })
    assert resp.status_code == 200

    # 錯誤密碼
    resp = admin.post("/admin/list-characters", json={"admin_password": "wrong"})
    assert resp.status_code == 403


def test_shop_buy_weapon():
    # 先通過 admin 添加武器
    admin = TestClient(app)
    admin.post("/admin/add-weapon", json={
        "admin_password": "1111",
        "id": 2001, "name": "木棒", "attack": 5, "price": 10,
    })

    # 玩家沒有錢，買不起
    player = _register_and_login("shoptest", "商人測試")
    resp = player.post("/shop/weapon/buy", json={"item_id": 2001})
    assert resp.status_code == 200
    assert "error" in resp.json()  # 金幣不足

    # 查看武器列表
    resp = player.get("/shop/weapon")
    assert resp.status_code == 200
    assert any(w["name"] == "木棒" for w in resp.json())
