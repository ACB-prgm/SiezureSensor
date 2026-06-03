from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session as OrmSession

from app.database import get_db
from app.models import ActiveDeviceSession, Batch, Device, Session
from app.routes.sessions import summarize_session
from app.schemas import ActiveSessionIn, ActiveSessionOut, BootSummaryOut
from app.session_assignment import set_active_session


router = APIRouter(prefix="/api/v1/devices", tags=["devices"])


def now_iso() -> str:
  return datetime.now(UTC).isoformat()


def active_session_to_out(db: OrmSession, active: ActiveDeviceSession) -> ActiveSessionOut:
  session = db.get(Session, active.session_id)
  if session is None:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Active session record points to a missing session",
    )
  return ActiveSessionOut(
    device_id=active.device_id,
    session_id=active.session_id,
    updated_at=active.updated_at,
    session=summarize_session(db, session),
  )


@router.get("/{device_id}/active-session", response_model=ActiveSessionOut | None)
def get_active_session(device_id: str, db: OrmSession = Depends(get_db)) -> ActiveSessionOut | None:
  active = db.get(ActiveDeviceSession, device_id)
  if active is None:
    return None
  return active_session_to_out(db, active)


@router.post("/{device_id}/active-session", response_model=ActiveSessionOut)
def update_active_session(
  device_id: str,
  payload: ActiveSessionIn,
  db: OrmSession = Depends(get_db),
) -> ActiveSessionOut:
  if db.get(Device, device_id) is None:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Device not found",
    )

  session = db.get(Session, payload.session_id)
  if session is None or session.device_id != device_id:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Session not found for device",
    )

  active = set_active_session(db, device_id, payload.session_id, now_iso())
  db.commit()
  db.refresh(active)
  return active_session_to_out(db, active)


@router.get("/{device_id}/boots", response_model=list[BootSummaryOut])
def list_device_boots(
  device_id: str,
  session_id: str | None = None,
  limit: int = Query(default=50, ge=1, le=500),
  db: OrmSession = Depends(get_db),
) -> list[BootSummaryOut]:
  query = db.query(
    Batch.device_id.label("device_id"),
    Batch.session_id.label("session_id"),
    Batch.boot_id.label("boot_id"),
    func.max(Batch.reset_reason).label("reset_reason"),
    func.max(Batch.reset_info).label("reset_info"),
    func.min(Batch.server_received_at).label("first_received_at"),
    func.max(Batch.server_received_at).label("last_received_at"),
    func.min(Batch.sequence).label("min_sequence"),
    func.max(Batch.sequence).label("max_sequence"),
    func.count(Batch.id).label("batch_count"),
    func.coalesce(func.sum(Batch.sample_count), 0).label("sample_count"),
    func.min(Batch.device_ms_start).label("min_device_ms_start"),
    func.max(Batch.device_ms_start).label("max_device_ms_start"),
    func.max(Batch.uptime_ms).label("latest_uptime_ms"),
    func.max(Batch.last_http_status).label("latest_http_status"),
    func.max(Batch.last_http_duration_ms).label("latest_http_duration_ms"),
    func.max(Batch.consecutive_upload_failures).label("max_consecutive_upload_failures"),
    func.max(Batch.wifi_disconnect_count).label("max_wifi_disconnect_count"),
    func.max(Batch.queued_batch_count).label("max_queued_batch_count"),
    func.max(Batch.dropped_batch_count).label("max_dropped_batch_count"),
    func.max(Batch.max_sample_lateness_ms).label("max_sample_lateness_ms"),
    func.max(Batch.upload_skip_count).label("max_upload_skip_count"),
    func.min(Batch.wifi_rssi).label("min_wifi_rssi"),
    func.max(Batch.wifi_rssi).label("max_wifi_rssi"),
    func.min(Batch.free_heap).label("min_free_heap"),
    func.min(Batch.min_free_heap).label("min_reported_free_heap"),
    func.max(Batch.heap_fragmentation).label("max_heap_fragmentation"),
  ).filter(Batch.device_id == device_id)

  if session_id is not None:
    query = query.filter(Batch.session_id == session_id)

  rows = (
    query.group_by(Batch.device_id, Batch.session_id, Batch.boot_id)
    .order_by(func.max(Batch.server_received_at).desc())
    .limit(limit)
    .all()
  )

  return [BootSummaryOut(**row._asdict()) for row in rows]
