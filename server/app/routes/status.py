from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session as OrmSession

from app.database import get_database_path, get_db
from app.models import Batch, IMUSample, Session


router = APIRouter(prefix="/api/v1/status", tags=["status"])


@router.get("")
def api_status(db: OrmSession = Depends(get_db)) -> dict[str, object]:
  batch_stats = db.query(
    func.count(Batch.id),
    func.coalesce(func.sum(Batch.sample_count), 0),
  ).one()
  latest_sample = db.query(IMUSample).order_by(IMUSample.id.desc()).first()
  latest_batch = db.query(Batch).order_by(Batch.id.desc()).first()
  latest_session_sample_count = (
    db.query(func.coalesce(func.sum(Batch.sample_count), 0))
    .filter(Batch.session_id == latest_batch.session_id)
    .scalar()
    if latest_batch
    else None
  )

  return {
    "status": "ok",
    "server_time": datetime.now(UTC).isoformat(),
    "database_path": str(get_database_path()),
    "session_count": db.query(func.count(Session.session_id)).scalar() or 0,
    "batch_count": batch_stats[0] or 0,
    "sample_count": batch_stats[1] or 0,
    "latest_batch_received_at": latest_batch.server_received_at if latest_batch else None,
    "latest_sample_received_at": latest_sample.server_received_at if latest_sample else None,
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
        "session_id": latest_batch.session_id,
        "sample_count": latest_session_sample_count or 0,
        "latest_received_at": latest_batch.server_received_at,
      }
      if latest_batch
      else None
    ),
  }
