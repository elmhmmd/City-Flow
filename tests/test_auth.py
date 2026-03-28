"""Auth endpoint tests — 7 tests."""


def test_login_success(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "pass"})
    assert r.status_code == 401


def test_login_missing_fields(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin"})
    assert r.status_code == 422


def test_refresh_token(client):
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
    rt = login.json()["refresh_token"]
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": rt})
    assert r.status_code == 200
    assert "access_token" in r.json()
    assert "refresh_token" in r.json()


def test_refresh_invalid_token(client):
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": "garbage.token.value"})
    assert r.status_code == 401


def test_refresh_already_used_token(client):
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
    rt = login.json()["refresh_token"]
    client.post("/api/v1/auth/refresh", json={"refresh_token": rt})
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": rt})
    assert r.status_code == 401
