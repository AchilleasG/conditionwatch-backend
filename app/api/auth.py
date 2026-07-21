from urllib.parse import urlencode
import secrets
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from firebase_admin import auth as firebase_auth
from firebase_admin.exceptions import FirebaseError
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..config import Settings, get_settings
from ..database import get_db
from ..models import User
from ..schemas import AuthResponse, FirebaseTokenRequest, LoginRequest, UserCreate
from ..security import create_access_token, hash_password, verify_password
from ..services.firebase_service import initialize_firebase

router = APIRouter(tags=["authentication"])
templates = Jinja2Templates(directory="app/templates")


def _authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    return user if user and user.is_active and verify_password(password, user.password_hash) else None


@router.post("/v1/auth/register", response_model=AuthResponse, status_code=201)
def register(body: UserCreate, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=email, display_name=body.display_name.strip(), password_hash=hash_password(body.password))
    db.add(user); db.commit(); db.refresh(user)
    return AuthResponse(access_token=create_access_token(user, settings), user=user)


@router.post("/v1/auth/login", response_model=AuthResponse)
def login(body: LoginRequest, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = _authenticate(db, body.email, body.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return AuthResponse(access_token=create_access_token(user, settings), user=user)


@router.post("/v1/auth/firebase", response_model=AuthResponse)
def firebase_login(body: FirebaseTokenRequest, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    try:
        initialize_firebase(settings)
        claims = firebase_auth.verify_id_token(body.id_token, check_revoked=True)
    except (FirebaseError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Firebase ID token")
    email = str(claims.get("email", "")).strip().lower()
    if not email or claims.get("email_verified") is not True:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="A verified email is required")
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        display_name = str(claims.get("name") or email.split("@", 1)[0]).strip()[:120]
        user = User(email=email, display_name=display_name, password_hash=hash_password(secrets.token_urlsafe(32)))
        db.add(user); db.commit(); db.refresh(user)
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")
    return AuthResponse(access_token=create_access_token(user, settings), user=user)


@router.get("/auth/mobile", response_class=HTMLResponse)
def mobile_login(request: Request, error: str | None = None):
    return templates.TemplateResponse(request=request, name="mobile_login.html", context={"error": error})


@router.post("/auth/mobile/submit")
def mobile_login_submit(
    email: str = Form(...),
    password: str = Form(...),
    display_name: str = Form(""),
    action: str = Form("login"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    normalized = email.strip().lower()
    user = _authenticate(db, normalized, password)
    if action == "register" and user is None:
        if db.scalar(select(User).where(User.email == normalized)):
            return RedirectResponse("/auth/mobile?error=" + urlencode({"": "Email already registered"})[1:], status_code=303)
        if len(password) < 10 or not display_name.strip():
            return RedirectResponse("/auth/mobile?error=" + urlencode({"": "Name and a 10-character password are required"})[1:], status_code=303)
        user = User(email=normalized, display_name=display_name.strip(), password_hash=hash_password(password))
        db.add(user); db.commit(); db.refresh(user)
    if user is None:
        return RedirectResponse("/auth/mobile?error=" + urlencode({"": "Invalid email or password"})[1:], status_code=303)
    query = urlencode({"token": create_access_token(user, settings)})
    return RedirectResponse(f"{settings.mobile_redirect_uri}?{query}", status_code=303)
