from collections.abc import Generator
from pathlib import Path
import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker


DATABASE_PATH_ENV = "SEIZURE_SENSOR_DB_PATH"
DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "seizure_sensor_v0.sqlite"

Base = declarative_base()

_engine: Engine | None = None
_engine_path: Path | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_database_path() -> Path:
  configured_path = os.getenv(DATABASE_PATH_ENV)
  if configured_path:
    return Path(configured_path).expanduser().resolve()
  return DEFAULT_DB_PATH


def get_engine() -> Engine:
  global _engine, _engine_path, _SessionLocal

  db_path = get_database_path()
  if _engine is None or _engine_path != db_path:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(
      f"sqlite:///{db_path}",
      connect_args={"check_same_thread": False},
      future=True,
    )
    _engine_path = db_path
    _SessionLocal = sessionmaker(
      autocommit=False,
      autoflush=False,
      bind=_engine,
      future=True,
    )

  return _engine


def get_session_local() -> sessionmaker[Session]:
  get_engine()
  if _SessionLocal is None:
    raise RuntimeError("Database session factory was not initialized")
  return _SessionLocal


def init_db() -> None:
  import app.models  # noqa: F401  Registers SQLAlchemy models with Base.

  Base.metadata.create_all(bind=get_engine())


def get_db() -> Generator[Session, None, None]:
  db = get_session_local()()
  try:
    yield db
  finally:
    db.close()
