from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app

client = TestClient(app)


def setup_module():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def teardown_module():
    Base.metadata.drop_all(bind=engine)


def test_register_and_login():
    # 註冊
    resp = client.post("/auth/register", json={
        "id": "testuser",
        "password": "testpass",
        "password_recovery": "secret",
        "name": "測試角色",
        "sex": 1,
        "image_id": 0,
        "job_class": 0,
    })
    assert resp.status_code == 200, resp.json()
    assert resp.json()["character_id"] == "testuser"
    assert "ffa_token" in resp.cookies

    # 登入
    resp2 = client.post("/auth/login", json={
        "id": "testuser",
        "password": "testpass",
    })
    assert resp2.status_code == 200
    assert resp2.json()["character_name"] == "測試角色"


def test_duplicate_register():
    resp = client.post("/auth/register", json={
        "id": "testuser",
        "password": "testpass",
        "password_recovery": "secret",
        "name": "測試角色二",
    })
    assert resp.status_code == 409


def test_wrong_password():
    resp = client.post("/auth/login", json={
        "id": "testuser",
        "password": "wrongpass",
    })
    assert resp.status_code == 401


def test_status_without_auth():
    # 使用新 client 確保無 cookie
    from fastapi.testclient import TestClient as TC
    fresh = TC(app)
    resp = fresh.get("/status")
    assert resp.status_code == 401
