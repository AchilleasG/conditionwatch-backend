from collections.abc import Generator
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from .config import get_settings


class Base(DeclarativeBase):
    pass


def _connect_args(url: str) -> dict:
    return {"check_same_thread": False} if url.startswith("sqlite") else {}


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=_connect_args(settings.database_url))
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def create_schema() -> None:
    from . import models  # noqa: F401
    Base.metadata.create_all(engine)
    # Lightweight forward migration for existing prototype deployments.
    columns = {column["name"] for column in inspect(engine).get_columns("frame_evaluations")}
    if "outcome" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE frame_evaluations ADD COLUMN outcome VARCHAR(24) NOT NULL DEFAULT 'success'"))
