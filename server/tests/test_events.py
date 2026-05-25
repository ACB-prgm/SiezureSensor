from app.models import Event

from tests.test_imu_upload import valid_payload


def create_session(client, session_id: str = "session-with-data") -> None:
  payload = valid_payload()
  payload["session_id"] = session_id
  response = client.post("/api/v1/imu/batch", json=payload)
  assert response.status_code == 200


def valid_event_payload(session_id: str = "session-with-data") -> dict:
  return {
    "session_id": session_id,
    "event_type": "scratching",
    "severity": 2,
    "start_device_ms": 184240,
    "end_device_ms": 184300,
    "source": "manual",
    "notes": "short scratch",
  }


def test_valid_event_creation_succeeds(client, db_session):
  create_session(client)

  response = client.post("/api/v1/events", json=valid_event_payload())

  assert response.status_code == 201
  body = response.json()
  assert body["id"] == 1
  assert body["session_id"] == "session-with-data"
  assert body["event_type"] == "scratching"
  assert body["severity"] == 2
  assert body["start_device_ms"] == 184240
  assert body["end_device_ms"] == 184300
  assert body["source"] == "manual"
  assert body["notes"] == "short scratch"
  assert body["created_at"]
  assert db_session.query(Event).count() == 1


def test_invalid_event_type_rejected(client):
  create_session(client)
  payload = valid_event_payload()
  payload["event_type"] = "not_allowed"

  response = client.post("/api/v1/events", json=payload)

  assert response.status_code == 422


def test_end_before_start_rejected(client):
  create_session(client)
  payload = valid_event_payload()
  payload["start_device_ms"] = 200
  payload["end_device_ms"] = 100

  response = client.post("/api/v1/events", json=payload)

  assert response.status_code == 422


def test_missing_session_returns_404(client):
  response = client.post("/api/v1/events", json=valid_event_payload("missing-session"))

  assert response.status_code == 404


def test_event_listing_returns_created_events(client):
  create_session(client)
  first = valid_event_payload()
  second = valid_event_payload()
  second["event_type"] = "walking"
  second["start_device_ms"] = 184320
  second["end_device_ms"] = 184500

  assert client.post("/api/v1/events", json=second).status_code == 201
  assert client.post("/api/v1/events", json=first).status_code == 201

  response = client.get("/api/v1/events")

  assert response.status_code == 200
  body = response.json()
  assert [event["event_type"] for event in body] == ["scratching", "walking"]


def test_get_event_returns_correct_event_or_404(client):
  create_session(client)
  created = client.post("/api/v1/events", json=valid_event_payload())
  event_id = created.json()["id"]

  found = client.get(f"/api/v1/events/{event_id}")
  missing = client.get("/api/v1/events/999")

  assert found.status_code == 200
  assert found.json()["id"] == event_id
  assert missing.status_code == 404
