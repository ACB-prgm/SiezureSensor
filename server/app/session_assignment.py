from datetime import UTC, datetime
import re

from sqlalchemy.orm import Session as OrmSession

from app.models import ActiveDeviceSession, Device, Session


AUTO_SESSION_NOTE = "Auto-created from first upload with no active session."


def now_iso() -> str:
  return datetime.now(UTC).isoformat()


def sanitize_session_part(value: str) -> str:
  return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-") or "device"


def auto_session_id(device_id: str, created_at: datetime | None = None) -> str:
  timestamp = (created_at or datetime.now().astimezone()).strftime("%Y-%m-%dT%H-%M-%S")
  return f"{timestamp}-{sanitize_session_part(device_id)}-auto"


def ensure_device(db: OrmSession, device_id: str, firmware_version: str | None, created_at: str) -> Device:
  device = db.get(Device, device_id)
  if device is None:
    device = Device(
      device_id=device_id,
      firmware_version=firmware_version,
      created_at=created_at,
    )
    db.add(device)
  else:
    device.firmware_version = firmware_version or device.firmware_version
  return device


def set_active_session(db: OrmSession, device_id: str, session_id: str, updated_at: str) -> ActiveDeviceSession:
  active = db.get(ActiveDeviceSession, device_id)
  if active is None:
    active = ActiveDeviceSession(device_id=device_id, session_id=session_id, updated_at=updated_at)
    db.add(active)
  else:
    active.session_id = session_id
    active.updated_at = updated_at
  return active


def create_auto_session(db: OrmSession, device_id: str, created_at: str) -> Session:
  base_session_id = auto_session_id(device_id)
  session_id = base_session_id
  suffix = 2
  while db.get(Session, session_id) is not None:
    session_id = f"{base_session_id}-{suffix}"
    suffix += 1

  session = Session(
    session_id=session_id,
    device_id=device_id,
    started_at=created_at,
    ended_at=None,
    mount_location=None,
    notes=AUTO_SESSION_NOTE,
  )
  db.add(session)
  return session


def get_or_create_active_session(db: OrmSession, device_id: str, created_at: str) -> Session:
  active = db.get(ActiveDeviceSession, device_id)
  if active is not None:
    session = db.get(Session, active.session_id)
    if session is not None:
      return session

  session = create_auto_session(db, device_id, created_at)
  set_active_session(db, device_id, session.session_id, created_at)
  return session
