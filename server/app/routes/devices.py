from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as OrmSession

from app.database import get_db
from app.models import ActiveDeviceSession, Device, Session
from app.routes.sessions import summarize_session
from app.schemas import ActiveSessionIn, ActiveSessionOut
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
