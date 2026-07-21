from datetime import datetime, timezone
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, messaging
from sqlalchemy.orm import Session
from ..config import Settings
from ..models import Device, WatchSession


class FirebaseService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._initialized = False

    def _initialize(self) -> None:
        if self._initialized:
            return
        if firebase_admin._apps:
            self._initialized = True
            return
        options = {"projectId": self.settings.firebase_project_id} if self.settings.firebase_project_id else None
        if self.settings.firebase_credentials_json:
            cred = credentials.Certificate(str(Path(self.settings.firebase_credentials_json)))
            firebase_admin.initialize_app(cred, options)
        else:
            firebase_admin.initialize_app(options=options)
        self._initialized = True

    def send_match(self, db: Session, session: WatchSession, device: Device) -> str:
        self._initialize()
        message = messaging.Message(
            token=device.fcm_token,
            data={
                "type": "condition_met",
                "sessionId": session.id,
                "condition": session.normalized_condition,
                "confidence": f"{session.last_confidence or 0:.3f}",
            },
            android=messaging.AndroidConfig(priority="high"),
        )
        try:
            message_id = messaging.send(message)
            session.alert_status = "sent"
            db.commit()
            return message_id
        except Exception as exc:
            session.alert_status = "failed"
            if exc.__class__.__name__ in {"UnregisteredError", "SenderIdMismatchError"}:
                device.revoked_at = datetime.now(timezone.utc)
            db.commit()
            raise
