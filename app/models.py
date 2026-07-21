from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class SessionStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    MATCHED = "matched"
    STOPPED = "stopped"


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("usr"))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    devices: Mapped[list["Device"]] = relationship(back_populates="user")
    watch_sessions: Mapped[list["WatchSession"]] = relationship(back_populates="user")


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (UniqueConstraint("fcm_token", name="uq_devices_fcm_token"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("dev"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    fcm_token: Mapped[str] = mapped_column(Text)
    platform: Mapped[str] = mapped_column(String(24), default="android")
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user: Mapped[User] = relationship(back_populates="devices")
    sessions: Mapped[list["WatchSession"]] = relationship(back_populates="device")


class WatchSession(Base):
    __tablename__ = "watch_sessions"
    __table_args__ = (Index("ix_session_user_status", "user_id", "status"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("ws"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[str | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"), nullable=True)
    original_transcript: Mapped[str] = mapped_column(Text)
    normalized_condition: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default=SessionStatus.PENDING.value)
    sample_interval_ms: Mapped[int] = mapped_column(Integer, default=1500)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    matched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_frame_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    match_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    alert_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    user: Mapped[User] = relationship(back_populates="watch_sessions")
    device: Mapped[Device | None] = relationship(back_populates="sessions")
    evaluations: Mapped[list["FrameEvaluation"]] = relationship(back_populates="session")


class FrameEvaluation(Base):
    __tablename__ = "frame_evaluations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("eval"))
    session_id: Mapped[str] = mapped_column(ForeignKey("watch_sessions.id", ondelete="CASCADE"), index=True)
    matched: Mapped[bool] = mapped_column(Boolean)
    confidence: Mapped[float] = mapped_column(Float)
    explanation: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    session: Mapped[WatchSession] = relationship(back_populates="evaluations")
