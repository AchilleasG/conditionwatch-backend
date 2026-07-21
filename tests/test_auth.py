def test_register_login_and_duplicate_protection(client):
    body = {"email": "alex@example.com", "display_name": "Alex", "password": "correct-horse-battery"}
    created = client.post("/v1/auth/register", json=body)
    assert created.status_code == 201
    assert created.json()["user"]["email"] == "alex@example.com"
    assert created.json()["access_token"]

    duplicate = client.post("/v1/auth/register", json=body)
    assert duplicate.status_code == 409

    login = client.post("/v1/auth/login", json={"email": body["email"], "password": body["password"]})
    assert login.status_code == 200
    assert login.json()["user"]["id"] == created.json()["user"]["id"]


def test_bad_password_is_rejected(client):
    client.post("/v1/auth/register", json={"email": "a@example.com", "display_name": "A", "password": "long-enough-password"})
    response = client.post("/v1/auth/login", json={"email": "a@example.com", "password": "wrong"})
    assert response.status_code == 401


def test_firebase_login_creates_and_reuses_user(client, monkeypatch):
    claims = {"uid": "firebase-alex", "email": "alex@gmail.com", "email_verified": True, "name": "Alex Google"}
    monkeypatch.setattr("app.api.auth.initialize_firebase", lambda settings: None)
    monkeypatch.setattr("app.api.auth.firebase_auth.verify_id_token", lambda token, check_revoked: claims)
    first = client.post("/v1/auth/firebase", json={"id_token": "x" * 100})
    second = client.post("/v1/auth/firebase", json={"id_token": "y" * 100})
    assert first.status_code == 200
    assert first.json()["user"]["id"] == second.json()["user"]["id"]
    assert first.json()["user"]["display_name"] == "Alex Google"


def test_firebase_login_requires_verified_email(client, monkeypatch):
    monkeypatch.setattr("app.api.auth.initialize_firebase", lambda settings: None)
    monkeypatch.setattr("app.api.auth.firebase_auth.verify_id_token", lambda token, check_revoked: {"email": "x@gmail.com", "email_verified": False})
    response = client.post("/v1/auth/firebase", json={"id_token": "x" * 100})
    assert response.status_code == 401
