from datetime import datetime, timezone
from pathlib import Path
import logging
import tempfile
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from ..config import Settings, get_settings
from ..database import get_db
from ..models import Device, FrameEvaluation, SessionStatus, User, WatchSession, new_id
from ..schemas import CreateSessionResponse, DeviceTokenRequest, FrameResult, SessionOut, StartSessionRequest
from ..security import get_current_user
from ..services.devices import upsert_device
from ..services.firebase_service import FirebaseService
from ..services.openai_service import OpenAIService

router = APIRouter(prefix="/v1", tags=["watch sessions"])
logger = logging.getLogger(__name__)


def owned_session(db: Session, session_id: str, user: User, lock: bool = False) -> WatchSession:
    statement = select(WatchSession).where(WatchSession.id == session_id, WatchSession.user_id == user.id)
    if lock:
        statement = statement.with_for_update()
    session = db.scalar(statement)
    if session is None:
        raise HTTPException(status_code=404, detail="Watch session not found")
    return session


async def read_limited(upload: UploadFile, limit: int) -> bytes:
    content = await upload.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(status_code=413, detail="Upload too large")
    return content


@router.put("/devices/fcm-token", status_code=204)
def refresh_device_token(body: DeviceTokenRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    upsert_device(db, user, body.fcmToken)
    db.commit()


@router.post("/watch-sessions/from-audio", response_model=CreateSessionResponse, status_code=201)
async def create_from_audio(
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    content = await read_limited(audio, settings.max_audio_bytes)
    suffix = Path(audio.filename or "recording.m4a").suffix[:10] or ".m4a"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
            temp.write(content); temp_path = Path(temp.name)
        service = OpenAIService(settings)
        transcript = await run_in_threadpool(service.transcribe, temp_path)
        interpretation = await run_in_threadpool(service.normalize_condition, transcript, user.id)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    if not interpretation.is_visually_observable:
        raise HTTPException(status_code=422, detail=interpretation.clarification or "Condition is not visually observable")
    session = WatchSession(
        user_id=user.id,
        original_transcript=transcript,
        normalized_condition=interpretation.normalized_condition,
        sample_interval_ms=settings.default_sample_interval_ms,
    )
    db.add(session); db.commit(); db.refresh(session)
    return CreateSessionResponse(
        sessionId=session.id,
        originalTranscript=session.original_transcript,
        normalizedCondition=session.normalized_condition,
        sampleIntervalMs=session.sample_interval_ms,
    )


@router.post("/watch-sessions/{session_id}/start", status_code=204)
def start_session(
    session_id: str,
    body: StartSessionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = owned_session(db, session_id, user, lock=True)
    if session.status not in {SessionStatus.PENDING.value, SessionStatus.ACTIVE.value}:
        raise HTTPException(status_code=409, detail="Session cannot be started")
    session.normalized_condition = body.condition.strip()
    if body.fcmToken:
        device = upsert_device(db, user, body.fcmToken)
        session.device_id = device.id
    if session.device_id is None:
        raise HTTPException(status_code=422, detail="An FCM device token is required")
    session.status = SessionStatus.ACTIVE.value
    session.started_at = session.started_at or datetime.now(timezone.utc)
    db.commit()


@router.post("/watch-sessions/{session_id}/frames", response_model=FrameResult)
async def upload_frame(
    session_id: str,
    frame: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    session = owned_session(db, session_id, user)
    if session.status == SessionStatus.MATCHED.value:
        return FrameResult(accepted=False, matched=True, confidence=session.last_confidence)
    if session.status != SessionStatus.ACTIVE.value:
        raise HTTPException(status_code=409, detail="Session is not active")
    now = datetime.now(timezone.utc)
    if session.last_frame_at:
        previous = session.last_frame_at
        if previous.tzinfo is None:
            previous = previous.replace(tzinfo=timezone.utc)
        if (now - previous).total_seconds() * 1000 < settings.min_sample_interval_ms:
            return FrameResult(accepted=False, matched=False, confidence=session.last_confidence)
    image = await read_limited(frame, settings.max_frame_bytes)
    if len(image) < 4 or image[:2] != b"\xff\xd8":
        raise HTTPException(status_code=415, detail="A JPEG frame is required")
    service = OpenAIService(settings)
    decision = await run_in_threadpool(service.evaluate_image, image, session.normalized_condition, user.id)
    is_match = decision.matched and decision.confidence >= settings.vision_match_threshold
    evaluation = FrameEvaluation(
        id=new_id("eval"),
        session_id=session.id,
        matched=is_match,
        confidence=decision.confidence,
        explanation=decision.explanation,
        model=settings.openai_vision_model,
    )
    if settings.retain_evaluation_frames:
        from ..services.evaluation_frames import save_evaluation_frame
        try:
            await run_in_threadpool(save_evaluation_frame, settings, session.id, evaluation.id, image)
        except OSError:
            logger.exception("Could not retain evaluation frame %s", evaluation.id)
    db.add(evaluation)
    session.last_frame_at = now
    session.last_confidence = decision.confidence
    session.match_explanation = decision.explanation
    db.commit()
    if not is_match:
        return FrameResult(accepted=True, matched=False, confidence=decision.confidence)

    session = owned_session(db, session_id, user, lock=True)
    if session.status == SessionStatus.MATCHED.value:
        return FrameResult(accepted=True, matched=True, confidence=session.last_confidence)
    session.status = SessionStatus.MATCHED.value
    session.matched_at = now
    session.alert_status = "pending"
    db.commit()
    device = db.get(Device, session.device_id) if session.device_id else None
    if device and device.user_id == user.id and device.revoked_at is None:
        try:
            await run_in_threadpool(FirebaseService(settings).send_match, db, session, device)
        except Exception:
            pass  # The frame response still causes the initiating phone to alarm.
    return FrameResult(accepted=True, matched=True, confidence=decision.confidence)


@router.delete("/watch-sessions/{session_id}", status_code=204)
def stop_session(session_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    session = owned_session(db, session_id, user, lock=True)
    if session.status != SessionStatus.MATCHED.value:
        session.status = SessionStatus.STOPPED.value
    session.stopped_at = datetime.now(timezone.utc)
    db.commit()


@router.get("/watch-sessions", response_model=list[SessionOut])
def list_sessions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    sessions = db.scalars(select(WatchSession).where(WatchSession.user_id == user.id).order_by(WatchSession.created_at.desc()).limit(100)).all()
    return [SessionOut(id=s.id, condition=s.normalized_condition, status=s.status, sampleIntervalMs=s.sample_interval_ms, confidence=s.last_confidence) for s in sessions]
