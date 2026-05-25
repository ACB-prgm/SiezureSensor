from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as OrmSession

from app.database import get_db
from app.models import Event, Session
from app.schemas import EventIn, EventOut


router = APIRouter(prefix="/api/v1/events", tags=["events"])


def now_iso() -> str:
  return datetime.now(UTC).isoformat()


def event_to_out(event: Event) -> EventOut:
  return EventOut(
    id=event.id,
    session_id=event.session_id,
    event_type=event.event_type,
    severity=event.severity,
    start_device_ms=event.start_device_ms,
    end_device_ms=event.end_device_ms,
    source=event.source,
    notes=event.notes,
    created_at=event.created_at,
  )


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_event(payload: EventIn, db: OrmSession = Depends(get_db)) -> EventOut:
  if db.get(Session, payload.session_id) is None:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Session not found",
    )

  event = Event(
    session_id=payload.session_id,
    event_type=payload.event_type,
    severity=payload.severity,
    start_device_ms=payload.start_device_ms,
    end_device_ms=payload.end_device_ms,
    source=payload.source,
    notes=payload.notes,
    created_at=now_iso(),
  )
  db.add(event)
  db.commit()
  db.refresh(event)

  return event_to_out(event)


@router.get("", response_model=list[EventOut])
def list_events(session_id: str | None = None, db: OrmSession = Depends(get_db)) -> list[EventOut]:
  query = db.query(Event)
  if session_id is not None:
    query = query.filter(Event.session_id == session_id)

  events = query.order_by(Event.start_device_ms, Event.id).all()
  return [event_to_out(event) for event in events]


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: int, db: OrmSession = Depends(get_db)) -> EventOut:
  event = db.get(Event, event_id)
  if event is None:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Event not found",
    )

  return event_to_out(event)
