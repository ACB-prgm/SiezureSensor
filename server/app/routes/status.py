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
  latest_batch = db.query(Batch).order_by(Batch.id.desc()).first()

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
    "latest_boot_id": latest_batch.boot_id if latest_batch else None,
    "latest_reset_reason": latest_batch.reset_reason if latest_batch else None,
    "latest_wifi_rssi": latest_batch.wifi_rssi if latest_batch else None,
    "latest_free_heap": latest_batch.free_heap if latest_batch else None,
    "latest_queued_batch_count": latest_batch.queued_batch_count if latest_batch else None,
    "latest_dropped_batch_count": latest_batch.dropped_batch_count if latest_batch else None,
    "latest_max_sample_lateness_ms": latest_batch.max_sample_lateness_ms if latest_batch else None,
    "latest_upload_skip_count": latest_batch.upload_skip_count if latest_batch else None,
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
