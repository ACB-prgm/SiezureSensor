from collections.abc import Generator
from pathlib import Path
import os

from sqlalchemy import event, inspect, text
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
      connect_args={"check_same_thread": False, "timeout": 30},
      future=True,
    )
    configure_sqlite(_engine)
    _engine_path = db_path
    _SessionLocal = sessionmaker(
      autocommit=False,
      autoflush=False,
      bind=_engine,
      future=True,
    )

  return _engine


def configure_sqlite(engine: Engine) -> None:
  @event.listens_for(engine, "connect")
  def set_sqlite_pragmas(dbapi_connection, _) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


def get_session_local() -> sessionmaker[Session]:
  get_engine()
  if _SessionLocal is None:
    raise RuntimeError("Database session factory was not initialized")
  return _SessionLocal


def column_names(engine: Engine, table_name: str) -> set[str]:
  inspector = inspect(engine)
  if table_name not in inspector.get_table_names():
    return set()
  return {column["name"] for column in inspector.get_columns(table_name)}


def add_column_if_missing(engine: Engine, table_name: str, column_name: str, column_sql: str) -> None:
  if column_name not in column_names(engine, table_name):
    with engine.begin() as connection:
      connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}"))


def has_unique_index(engine: Engine, table_name: str, expected_columns: list[str]) -> bool:
  with engine.connect() as connection:
    indexes = connection.execute(text(f"PRAGMA index_list({table_name})")).mappings().all()
    for index in indexes:
      if not index["unique"]:
        continue
      index_name = str(index["name"]).replace('"', '""')
      indexed_columns = [
        row["name"]
        for row in connection.execute(text(f'PRAGMA index_info("{index_name}")')).mappings().all()
      ]
      if indexed_columns == expected_columns:
        return True
  return False


def migrate_batches_table(engine: Engine) -> None:
  inspector = inspect(engine)
  if "batches" not in inspector.get_table_names():
    return

  columns = column_names(engine, "batches")
  optional_columns = {
    "reset_reason": "reset_reason VARCHAR",
    "reset_info": "reset_info TEXT",
    "uptime_ms": "uptime_ms INTEGER",
    "wifi_rssi": "wifi_rssi INTEGER",
    "free_heap": "free_heap INTEGER",
    "min_free_heap": "min_free_heap INTEGER",
    "heap_fragmentation": "heap_fragmentation INTEGER",
    "queued_batch_count": "queued_batch_count INTEGER",
    "dropped_batch_count": "dropped_batch_count INTEGER",
    "max_sample_lateness_ms": "max_sample_lateness_ms INTEGER",
    "upload_skip_count": "upload_skip_count INTEGER",
    "last_http_duration_ms": "last_http_duration_ms INTEGER",
    "last_http_status": "last_http_status INTEGER",
    "consecutive_upload_failures": "consecutive_upload_failures INTEGER",
    "wifi_disconnect_count": "wifi_disconnect_count INTEGER",
  }
  needs_rebuild = "boot_id" not in columns
  needs_rebuild = needs_rebuild or not has_unique_index(engine, "batches", ["device_id", "boot_id", "sequence"])

  if not needs_rebuild:
    for column_name, column_sql in optional_columns.items():
      add_column_if_missing(engine, "batches", column_name, column_sql)
    return

  def select_expr(column_name: str, fallback_sql: str) -> str:
    return column_name if column_name in columns else fallback_sql

  with engine.begin() as connection:
    connection.execute(text("DROP TABLE IF EXISTS batches_migrated"))
    connection.execute(
      text(
        """
        CREATE TABLE batches_migrated (
          id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
          device_id VARCHAR NOT NULL,
          session_id VARCHAR NOT NULL,
          boot_id VARCHAR NOT NULL,
          sequence INTEGER NOT NULL,
          sample_hz INTEGER NOT NULL,
          device_ms_start INTEGER NOT NULL,
          server_received_at VARCHAR NOT NULL,
          sample_count INTEGER NOT NULL,
          battery_mv INTEGER,
          reset_reason VARCHAR,
          reset_info TEXT,
          uptime_ms INTEGER,
          wifi_rssi INTEGER,
          free_heap INTEGER,
          min_free_heap INTEGER,
          heap_fragmentation INTEGER,
          queued_batch_count INTEGER,
          dropped_batch_count INTEGER,
          max_sample_lateness_ms INTEGER,
          upload_skip_count INTEGER,
          last_http_duration_ms INTEGER,
          last_http_status INTEGER,
          consecutive_upload_failures INTEGER,
          wifi_disconnect_count INTEGER,
          raw_payload_json TEXT NOT NULL,
          CONSTRAINT uq_batch_device_boot_sequence UNIQUE (device_id, boot_id, sequence)
        )
        """
      )
    )
    connection.execute(
      text(
        f"""
        INSERT INTO batches_migrated (
          id,
          device_id,
          session_id,
          boot_id,
          sequence,
          sample_hz,
          device_ms_start,
          server_received_at,
          sample_count,
          battery_mv,
          reset_reason,
          reset_info,
          uptime_ms,
          wifi_rssi,
          free_heap,
          min_free_heap,
          heap_fragmentation,
          queued_batch_count,
          dropped_batch_count,
          max_sample_lateness_ms,
          upload_skip_count,
          last_http_duration_ms,
          last_http_status,
          consecutive_upload_failures,
          wifi_disconnect_count,
          raw_payload_json
        )
        SELECT
          id,
          device_id,
          session_id,
          {select_expr("boot_id", "'legacy-' || session_id")},
          sequence,
          sample_hz,
          device_ms_start,
          server_received_at,
          sample_count,
          battery_mv,
          {select_expr("reset_reason", "NULL")},
          {select_expr("reset_info", "NULL")},
          {select_expr("uptime_ms", "NULL")},
          {select_expr("wifi_rssi", "NULL")},
          {select_expr("free_heap", "NULL")},
          {select_expr("min_free_heap", "NULL")},
          {select_expr("heap_fragmentation", "NULL")},
          {select_expr("queued_batch_count", "NULL")},
          {select_expr("dropped_batch_count", "NULL")},
          {select_expr("max_sample_lateness_ms", "NULL")},
          {select_expr("upload_skip_count", "NULL")},
          {select_expr("last_http_duration_ms", "NULL")},
          {select_expr("last_http_status", "NULL")},
          {select_expr("consecutive_upload_failures", "NULL")},
          {select_expr("wifi_disconnect_count", "NULL")},
          raw_payload_json
        FROM batches
        """
      )
    )
    connection.execute(text("DROP TABLE batches"))
    connection.execute(text("ALTER TABLE batches_migrated RENAME TO batches"))


def migrate_imu_samples_table(engine: Engine) -> None:
  inspector = inspect(engine)
  if "imu_samples" not in inspector.get_table_names():
    return

  add_column_if_missing(engine, "imu_samples", "boot_id", "boot_id VARCHAR")


def migrate_events_table(engine: Engine) -> None:
  inspector = inspect(engine)
  if "events" not in inspector.get_table_names():
    return

  add_column_if_missing(engine, "events", "start_server_received_at", "start_server_received_at VARCHAR")
  add_column_if_missing(engine, "events", "end_server_received_at", "end_server_received_at VARCHAR")


def create_index_if_missing(engine: Engine, index_name: str, table_name: str, columns_sql: str) -> None:
  with engine.begin() as connection:
    connection.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_sql})"))


def create_query_indexes(engine: Engine) -> None:
  inspector = inspect(engine)
  table_names = set(inspector.get_table_names())
  if "imu_samples" in table_names:
    create_index_if_missing(engine, "ix_imu_samples_session_id", "imu_samples", "session_id")
    create_index_if_missing(engine, "ix_imu_samples_session_id_id", "imu_samples", "session_id, id")
    create_index_if_missing(engine, "ix_imu_samples_session_id_device_ms", "imu_samples", "session_id, device_ms")
  if "batches" in table_names:
    create_index_if_missing(engine, "ix_batches_session_id", "batches", "session_id")
    create_index_if_missing(engine, "ix_batches_session_id_received", "batches", "session_id, server_received_at")
    create_index_if_missing(engine, "ix_batches_id_received", "batches", "id, server_received_at")
  if "events" in table_names:
    create_index_if_missing(engine, "ix_events_session_id", "events", "session_id")
    create_index_if_missing(engine, "ix_events_session_id_server_time", "events", "session_id, start_server_received_at, end_server_received_at")


def migrate_existing_db(engine: Engine) -> None:
  migrate_batches_table(engine)
  migrate_imu_samples_table(engine)
  migrate_events_table(engine)
  create_query_indexes(engine)


def init_db() -> None:
  import app.models  # noqa: F401  Registers SQLAlchemy models with Base.

  engine = get_engine()
  Base.metadata.create_all(bind=engine)
  migrate_existing_db(engine)


def get_db() -> Generator[Session, None, None]:
  db = get_session_local()()
  try:
    yield db
  finally:
    db.close()
