from math import sqrt

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session as OrmSession

from app.database import get_db
from app.models import Batch, IMUSample, Session
from app.schemas import SessionSampleOut, SessionSummaryOut


router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def sample_to_out(sample: IMUSample) -> SessionSampleOut:
  return SessionSampleOut(
    device_id=sample.device_id,
    session_id=sample.session_id,
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

  samples = query.order_by(IMUSample.device_ms, IMUSample.sample_index).all()
  if len(samples) > max_points:
    step = max(1, len(samples) // max_points)
    samples = samples[::step][:max_points]

  return [sample_to_out(sample) for sample in samples]
