from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session as OrmSession

from app.database import get_database_path, get_db
from app.models import Batch, IMUSample, Session


router = APIRouter(prefix="/api/v1/status", tags=["status"])


@router.get("")
def api_status(db: OrmSession = Depends(get_db)) -> dict[str, object]:
  sample_stats = db.query(
    func.count(IMUSample.id),
    func.max(IMUSample.server_received_at),
  ).one()
  batch_stats = db.query(
    func.count(Batch.id),
    func.max(Batch.server_received_at),
  ).one()
  latest_session = (
    db.query(IMUSample.session_id, func.count(IMUSample.id), func.max(IMUSample.server_received_at))
    .group_by(IMUSample.session_id)
    .order_by(func.max(IMUSample.server_received_at).desc())
    .first()
  )
  latest_sample = db.query(IMUSample).order_by(IMUSample.id.desc()).first()

  return {
    "status": "ok",
    "server_time": datetime.now(UTC).isoformat(),
    "database_path": str(get_database_path()),
    "session_count": db.query(func.count(Session.session_id)).scalar() or 0,
    "batch_count": batch_stats[0] or 0,
    "sample_count": sample_stats[0] or 0,
    "latest_batch_received_at": batch_stats[1],
    "latest_sample_received_at": sample_stats[1],
    "latest_device_ms": latest_sample.device_ms if latest_sample else None,
    "latest_session": (
      {
        "session_id": latest_session[0],
        "sample_count": latest_session[1],
        "latest_received_at": latest_session[2],
      }
      if latest_session
      else None
    ),
  }
