from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session as OrmSession

from app.database import get_db
from app.models import Event, Session
from app.schemas import EventIn, EventOut, EventUpdate


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
    start_server_received_at=event.start_server_received_at,
    end_server_received_at=event.end_server_received_at,
    source=event.source,
    notes=event.notes,
    created_at=event.created_at,
  )


def has_overlapping_event(
  db: OrmSession,
  session_id: str,
  start_device_ms: int,
  end_device_ms: int,
  start_server_received_at: str | None = None,
  end_server_received_at: str | None = None,
  exclude_event_id: int | None = None,
) -> bool:
  query = db.query(Event).filter(Event.session_id == session_id)
  if start_server_received_at is not None and end_server_received_at is not None:
    query = query.filter(
      Event.start_server_received_at.isnot(None),
      Event.end_server_received_at.isnot(None),
      Event.start_server_received_at < end_server_received_at,
      Event.end_server_received_at > start_server_received_at,
    )
  else:
    query = query.filter(
      Event.start_device_ms < end_device_ms,
      Event.end_device_ms > start_device_ms,
    )
  if exclude_event_id is not None:
    query = query.filter(Event.id != exclude_event_id)
  return bool(db.query(query.exists()).scalar())


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_event(payload: EventIn, db: OrmSession = Depends(get_db)) -> EventOut:
  if db.get(Session, payload.session_id) is None:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Session not found",
    )
  if has_overlapping_event(
    db,
    payload.session_id,
    payload.start_device_ms,
    payload.end_device_ms,
    payload.start_server_received_at,
    payload.end_server_received_at,
  ):
    raise HTTPException(
      status_code=status.HTTP_409_CONFLICT,
      detail="Event overlaps an existing label",
    )

  event = Event(
    session_id=payload.session_id,
    event_type=payload.event_type,
    severity=payload.severity,
    start_device_ms=payload.start_device_ms,
    end_device_ms=payload.end_device_ms,
    start_server_received_at=payload.start_server_received_at,
    end_server_received_at=payload.end_server_received_at,
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


@router.patch("/{event_id}", response_model=EventOut)
def update_event(event_id: int, payload: EventUpdate, db: OrmSession = Depends(get_db)) -> EventOut:
  event = db.get(Event, event_id)
  if event is None:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Event not found",
    )

  next_session_id = payload.session_id if payload.session_id is not None else event.session_id
  next_start_device_ms = payload.start_device_ms if payload.start_device_ms is not None else event.start_device_ms
  next_end_device_ms = payload.end_device_ms if payload.end_device_ms is not None else event.end_device_ms

  if db.get(Session, next_session_id) is None:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Session not found",
    )
  if next_start_device_ms >= next_end_device_ms:
    raise HTTPException(
      status_code=422,
      detail="start_device_ms must be less than end_device_ms",
    )
  next_start_server_received_at = None
  next_end_server_received_at = None
  if "start_server_received_at" in payload.model_fields_set and "end_server_received_at" in payload.model_fields_set:
    next_start_server_received_at = payload.start_server_received_at
    next_end_server_received_at = payload.end_server_received_at
  if has_overlapping_event(
    db,
    next_session_id,
    next_start_device_ms,
    next_end_device_ms,
    next_start_server_received_at,
    next_end_server_received_at,
    exclude_event_id=event_id,
  ):
    raise HTTPException(
      status_code=status.HTTP_409_CONFLICT,
      detail="Event overlaps an existing label",
    )

  event.session_id = next_session_id
  if payload.event_type is not None:
    event.event_type = payload.event_type
  if "severity" in payload.model_fields_set:
    event.severity = payload.severity
  event.start_device_ms = next_start_device_ms
  event.end_device_ms = next_end_device_ms
  if "start_server_received_at" in payload.model_fields_set:
    event.start_server_received_at = payload.start_server_received_at
  if "end_server_received_at" in payload.model_fields_set:
    event.end_server_received_at = payload.end_server_received_at
  if payload.source is not None:
    event.source = payload.source
  if "notes" in payload.model_fields_set:
    event.notes = payload.notes

  db.commit()
  db.refresh(event)
  return event_to_out(event)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: int, db: OrmSession = Depends(get_db)) -> Response:
  event = db.get(Event, event_id)
  if event is None:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Event not found",
    )

  db.delete(event)
  db.commit()
  return Response(status_code=status.HTTP_204_NO_CONTENT)
