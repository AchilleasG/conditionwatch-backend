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
