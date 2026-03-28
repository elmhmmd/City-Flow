"""Prediction, user, and performance endpoint tests — 8 tests."""

DEMAND_PARAMS = {"zone_id": "48453001100", "timestamp": "2021-06-01T08:00:00"}
BATCH_ITEM = {"zone_id": "48453001100", "timestamp": "2021-06-01T08:00:00", "vehicle_type": "scooter"}


def test_demand_no_auth(client):
    r = client.get("/api/v1/predictions/demand", params=DEMAND_PARAMS)
    assert r.status_code in (401, 403)


def test_demand_authenticated(client, auth_headers):
    r = client.get("/api/v1/predictions/demand", params=DEMAND_PARAMS, headers=auth_headers)
    assert r.status_code == 200


def test_demand_response_shape(client, auth_headers):
    r = client.get("/api/v1/predictions/demand", params=DEMAND_PARAMS, headers=auth_headers)
    data = r.json()
    assert "predicted_trips" in data
    assert "confidence_interval" in data
    assert "weather" in data
    assert data["predicted_trips"] == 5.0


def test_batch_predictions(client, auth_headers):
    payload = {"predictions": [BATCH_ITEM] * 3}
    r = client.post("/api/v1/predictions/batch", json=payload, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["total"] == 3


def test_batch_no_auth(client):
    r = client.post("/api/v1/predictions/batch", json={"predictions": [BATCH_ITEM]})
    assert r.status_code in (401, 403)


def test_batch_too_large(client, auth_headers):
    payload = {"predictions": [BATCH_ITEM] * 501}
    r = client.post("/api/v1/predictions/batch", json=payload, headers=auth_headers)
    assert r.status_code == 422


def test_me_endpoint(client, auth_headers):
    r = client.get("/api/v1/users/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["username"] == "admin"
    assert r.json()["role"] == "admin"


def test_create_user_invalid_role(client, auth_headers):
    r = client.post(
        "/api/v1/users",
        params={"username": "newuser", "password": "pass123", "role": "superuser"},
        headers=auth_headers,
    )
    assert r.status_code == 400
