from app.schemas import ConditionInterpretation, VisionDecision


class FakeOpenAI:
    def transcribe(self, path):
        return "Let me know when the dog gets on the couch"

    def normalize_condition(self, transcript, user_id):
        return ConditionInterpretation(normalized_condition="A dog is visibly on the couch.", is_visually_observable=True)

    def evaluate_image(self, jpeg, condition, user_id):
        return VisionDecision(matched=True, confidence=0.94, explanation="A dog is clearly on the couch")


class FakeFirebase:
    sent = []

    def send_match(self, db, session, device):
        self.sent.append((session.user_id, device.user_id, device.fcm_token, session.id))
        session.alert_status = "sent"; db.commit()
        return "message-id"


def test_complete_targeted_match_pipeline(client, monkeypatch):
    import app.api.sessions as routes
    monkeypatch.setattr(routes, "OpenAIService", lambda settings: FakeOpenAI())
    monkeypatch.setattr(routes, "FirebaseService", lambda settings: FakeFirebase())
    FakeFirebase.sent.clear()

    registration = client.post("/v1/auth/register", json={"email": "watcher@example.com", "display_name": "Watcher", "password": "correct-horse-battery"}).json()
    headers = {"Authorization": f"Bearer {registration['access_token']}"}
    created = client.post("/v1/watch-sessions/from-audio", headers=headers, files={"audio": ("command.m4a", b"fake-audio", "audio/mp4")})
    assert created.status_code == 201
    session_id = created.json()["sessionId"]
    token = "specific-fcm-token-for-this-users-phone"
    assert client.post(f"/v1/watch-sessions/{session_id}/start", headers=headers, json={"condition": created.json()["normalizedCondition"], "fcmToken": token}).status_code == 204

    frame = client.post(f"/v1/watch-sessions/{session_id}/frames", headers=headers, files={"frame": ("frame.jpg", b"\xff\xd8fake-jpeg\xff\xd9", "image/jpeg")})
    assert frame.status_code == 200
    assert frame.json() == {"accepted": True, "matched": True, "confidence": 0.94}
    assert len(FakeFirebase.sent) == 1
    target_user, device_user, sent_token, sent_session = FakeFirebase.sent[0]
    assert target_user == device_user == registration["user"]["id"]
    assert sent_token == token
    assert sent_session == session_id

    assert client.get("/admin/").status_code == 401
    dashboard = client.get("/admin/", auth=("test-admin", "test-admin-password"))
    assert dashboard.status_code == 200
    assert "A dog is visibly on the couch" in dashboard.text
    detail = client.get(f"/admin/sessions/{session_id}", auth=("test-admin", "test-admin-password"))
    assert detail.status_code == 200
    assert "A dog is clearly on the couch" in detail.text
    from app.database import SessionLocal
    from app.models import FrameEvaluation
    from sqlalchemy import select
    with SessionLocal() as db:
        evaluation_id = db.scalar(select(FrameEvaluation.id).where(FrameEvaluation.session_id == session_id))
    retained = client.get(
        f"/admin/sessions/{session_id}/evaluations/{evaluation_id}/frame",
        auth=("test-admin", "test-admin-password"),
    )
    assert retained.status_code == 200
    assert retained.content == b"\xff\xd8fake-jpeg\xff\xd9"

    repeated = client.post(f"/v1/watch-sessions/{session_id}/frames", headers=headers, files={"frame": ("frame.jpg", b"\xff\xd8again\xff\xd9", "image/jpeg")})
    assert repeated.json()["matched"] is True
    assert len(FakeFirebase.sent) == 1
