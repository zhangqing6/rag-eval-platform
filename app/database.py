from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings


def _ensure_sqlite_dir(url: str) -> None:
    if url.startswith("sqlite:///./") or url.startswith("sqlite:///"):
        # sqlite:///./data/eval.db -> ./data
        path_part = url.replace("sqlite:///./", "").replace("sqlite:///", "")
        if "/" in path_part or "\\" in path_part:
            parent = Path(path_part).parent
            parent.mkdir(parents=True, exist_ok=True)


_settings = get_settings()
_ensure_sqlite_dir(_settings.database_url)
connect_args = {"check_same_thread": False} if "sqlite" in _settings.database_url else {}
engine = create_engine(_settings.database_url, echo=False, connect_args=connect_args)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
