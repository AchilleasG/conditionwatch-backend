import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..database import get_db
from ..models import FrameEvaluation, User, WatchSession
from ..services.evaluation_frames import evaluation_frame_path

router = APIRouter(prefix="/admin", tags=["admin"], include_in_schema=False)
templates = Jinja2Templates(directory="app/templates")
basic = HTTPBasic(auto_error=False)


def require_admin(
    credentials: HTTPBasicCredentials | None = Depends(basic),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.admin_password:
        raise HTTPException(status_code=503, detail="Admin dashboard is not configured")
    valid = credentials is not None
    valid = valid and secrets.compare_digest(credentials.username.encode(), settings.admin_username.encode())
    valid = valid and secrets.compare_digest(credentials.password.encode(), settings.admin_password.encode())
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required",
            headers={"WWW-Authenticate": 'Basic realm="ConditionWatch evaluations"'},
        )


@router.get("/", response_class=HTMLResponse)
def session_index(request: Request, _: None = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(
        select(WatchSession, User, func.count(FrameEvaluation.id))
        .join(User, User.id == WatchSession.user_id)
        .outerjoin(FrameEvaluation, FrameEvaluation.session_id == WatchSession.id)
        .group_by(WatchSession.id, User.id)
        .order_by(WatchSession.created_at.desc())
        .limit(250)
    ).all()
    return templates.TemplateResponse(
        request=request,
        name="admin_sessions.html",
        context={"rows": rows},
    )


@router.get("/sessions/{session_id}", response_class=HTMLResponse)
def session_detail(session_id: str, request: Request, _: None = Depends(require_admin), db: Session = Depends(get_db)):
    watch = db.get(WatchSession, session_id)
    if watch is None:
        raise HTTPException(status_code=404, detail="Watch session not found")
    user = db.get(User, watch.user_id)
    evaluations = db.scalars(
        select(FrameEvaluation)
        .where(FrameEvaluation.session_id == session_id)
        .order_by(FrameEvaluation.created_at.desc())
    ).all()
    return templates.TemplateResponse(
        request=request,
        name="admin_session.html",
        context={"watch": watch, "user": user, "evaluations": evaluations},
    )


@router.get("/sessions/{session_id}/evaluations/{evaluation_id}/frame")
def evaluation_frame(
    session_id: str,
    evaluation_id: str,
    _: None = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    evaluation = db.scalar(
        select(FrameEvaluation).where(
            FrameEvaluation.id == evaluation_id,
            FrameEvaluation.session_id == session_id,
        )
    )
    if evaluation is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    path = evaluation_frame_path(settings, session_id, evaluation_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Frame was not retained")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})
