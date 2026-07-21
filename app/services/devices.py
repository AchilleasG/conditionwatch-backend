from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import Device, User


def upsert_device(db: Session, user: User, fcm_token: str) -> Device:
    device = db.scalar(select(Device).where(Device.fcm_token == fcm_token))
    now = datetime.now(timezone.utc)
    if device is None:
        device = Device(user_id=user.id, fcm_token=fcm_token, last_seen_at=now)
        db.add(device)
    else:
        device.user_id = user.id
        device.last_seen_at = now
        device.revoked_at = None
    db.flush()
    return device
