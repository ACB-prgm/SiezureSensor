from datetime import UTC, datetime
from math import sqrt

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session as OrmSession

from app.database import get_db
from app.models import Batch, Device, IMUSample, Session
from app.schemas import SessionCreateIn, SessionSampleOut, SessionSummaryOut
from app.session_assignment import set_active_session


router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def now_iso() -> str:
  return datetime.now(UTC).isoformat()


def sample_to_out(sample: IMUSample) -> SessionSampleOut:
  return SessionSampleOut(
    device_id=sample.device_id,
    session_id=sample.session_id,
    boot_id=sample.boot_id or f"legacy-{sample.session_id}",
    batch_sequence=sample.batch_sequence,
    sample_index=sample.sample_index,
    device_ms=sample.device_ms,
    server_received_at=sample.server_received_at,
    ax=sample.ax,
    ay=sample.ay,
    az=sample.az,
    gx=sample.gx,
    gy=sample.gy,
    gz=sample.gz,
    accel_mag=sqrt(sample.ax**2 + sample.ay**2 + sample.az**2),
    gyro_mag=sqrt(sample.gx**2 + sample.gy**2 + sample.gz**2),
  )


def summarize_session(db: OrmSession, session: Session) -> SessionSummaryOut:
  sample_stats = (
    db.query(
      func.count(IMUSample.id),
      func.min(IMUSample.device_ms),
      func.max(IMUSample.device_ms),
      func.min(IMUSample.server_received_at),
      func.max(IMUSample.server_received_at),
    )
    .filter(IMUSample.session_id == session.session_id)
    .one()
  )
  batch_count = db.query(func.count(Batch.id)).filter(Batch.session_id == session.session_id).scalar() or 0

  return SessionSummaryOut(
    session_id=session.session_id,
    device_id=session.device_id,
    started_at=session.started_at,
    ended_at=session.ended_at,
    mount_location=session.mount_location,
    notes=session.notes,
    sample_count=sample_stats[0] or 0,
    batch_count=batch_count,
    min_device_ms=sample_stats[1],
    max_device_ms=sample_stats[2],
    first_server_received_at=sample_stats[3],
    last_server_received_at=sample_stats[4],
  )


@router.get("", response_model=list[SessionSummaryOut])
def list_sessions(db: OrmSession = Depends(get_db)) -> list[SessionSummaryOut]:
  sessions = db.query(Session).order_by(Session.session_id).all()
  return [summarize_session(db, session) for session in sessions]


@router.post("", response_model=SessionSummaryOut, status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionCreateIn, db: OrmSession = Depends(get_db)) -> SessionSummaryOut:
  if db.get(Session, payload.session_id) is not None:
    raise HTTPException(
      status_code=status.HTTP_409_CONFLICT,
      detail="Session already exists",
    )

  if db.get(Device, payload.device_id) is None:
    db.add(
      Device(
        device_id=payload.device_id,
        firmware_version=None,
        created_at=now_iso(),
      )
    )

  session = Session(
    session_id=payload.session_id,
    device_id=payload.device_id,
    started_at=payload.started_at,
    ended_at=payload.ended_at,
    mount_location=payload.mount_location,
    notes=payload.notes,
  )
  db.add(session)
  set_active_session(db, payload.device_id, payload.session_id, now_iso())
  db.commit()
  db.refresh(session)

  return summarize_session(db, session)


@router.get("/{session_id}/samples", response_model=list[SessionSampleOut])
def list_session_samples(
  session_id: str,
  start_device_ms: int | None = Query(default=None, ge=0),
  end_device_ms: int | None = Query(default=None, ge=0),
  max_points: int = Query(default=2000, ge=1, le=20000),
  db: OrmSession = Depends(get_db),
) -> list[SessionSampleOut]:
  if start_device_ms is not None and end_device_ms is not None and start_device_ms > end_device_ms:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="start_device_ms must be less than or equal to end_device_ms",
    )

  if db.get(Session, session_id) is None:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Session not found",
    )

  query = db.query(IMUSample).filter(IMUSample.session_id == session_id)
  if start_device_ms is not None:
    query = query.filter(IMUSample.device_ms >= start_device_ms)
  if end_device_ms is not None:
    query = query.filter(IMUSample.device_ms <= end_device_ms)

  total_samples = query.count()
  if total_samples > max_points:
    tail_count = min(5000, max(1, max_points // 4))
    tail_samples = query.order_by(IMUSample.id.desc()).limit(tail_count).all()
    oldest_tail_id = min((sample.id for sample in tail_samples), default=None)
    older_query = query.filter(IMUSample.id < oldest_tail_id) if oldest_tail_id is not None else query
    remaining_points = max(0, max_points - len(tail_samples))
    samples = []

    if remaining_points > 0:
      first_sample = older_query.order_by(IMUSample.id).first()
      if first_sample:
        samples.append(first_sample)

    if remaining_points > 1:
      older_total = older_query.count()
      step = max(1, older_total // remaining_points)
      middle_samples = (
        older_query.filter(IMUSample.id % step == 0)
        .order_by(IMUSample.id)
        .limit(remaining_points - 1)
        .all()
      )
      samples.extend(middle_samples)

    samples.extend(tail_samples)

    samples_by_id = {sample.id: sample for sample in samples if sample is not None}
    samples = sorted(samples_by_id.values(), key=lambda sample: sample.id)
  else:
    samples = query.order_by(IMUSample.id).all()

  return [sample_to_out(sample) for sample in samples]
