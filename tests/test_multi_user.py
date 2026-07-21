from app.database import SessionLocal
from app.models import WatchSession


def register(client, email):
    response = client.post("/v1/auth/register", json={"email": email, "display_name": email.split('@')[0], "password": "correct-horse-battery"})
    return response.json()


def test_user_cannot_read_or_stop_another_users_session(client):
    alice = register(client, "alice@example.com")
    bob = register(client, "bob@example.com")
    with SessionLocal() as db:
        session = WatchSession(user_id=alice["user"]["id"], original_transcript="dog", normalized_condition="A dog is on the couch")
        db.add(session); db.commit(); session_id = session.id

    bob_headers = {"Authorization": f"Bearer {bob['access_token']}"}
    assert client.delete(f"/v1/watch-sessions/{session_id}", headers=bob_headers).status_code == 404
    assert client.get("/v1/watch-sessions", headers=bob_headers).json() == []


def test_fcm_token_moves_to_current_authenticated_owner(client):
    alice = register(client, "alice@example.com")
    bob = register(client, "bob@example.com")
    token = "fcm-token-that-is-definitely-long-enough"
    for auth in (alice, bob):
        response = client.put("/v1/devices/fcm-token", json={"fcmToken": token}, headers={"Authorization": f"Bearer {auth['access_token']}"})
        assert response.status_code == 204
    from app.models import Device
    with SessionLocal() as db:
        device = db.query(Device).filter(Device.fcm_token == token).one()
        assert device.user_id == bob["user"]["id"]
