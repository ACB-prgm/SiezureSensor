from app.models import Event

from tests.test_imu_upload import valid_payload


def create_session(client, session_id: str = "session-with-data") -> None:
  assert client.post("/api/v1/sessions", json={"session_id": session_id, "device_id": "beanie-v0-001"}).status_code == 201
  payload = valid_payload()
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


def test_overlapping_event_creation_returns_409(client):
  create_session(client)
  assert client.post("/api/v1/events", json=valid_event_payload()).status_code == 201
  overlapping = valid_event_payload()
  overlapping["start_device_ms"] = 184250
  overlapping["end_device_ms"] = 184350

  response = client.post("/api/v1/events", json=overlapping)

  assert response.status_code == 409


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


def test_scooting_event_type_is_allowed(client):
  create_session(client)
  payload = valid_event_payload()
  payload["event_type"] = "scooting"

  response = client.post("/api/v1/events", json=payload)

  assert response.status_code == 201
  assert response.json()["event_type"] == "scooting"


def test_patch_event_updates_fields_and_preserves_created_at(client):
  create_session(client)
  created = client.post("/api/v1/events", json=valid_event_payload()).json()

  response = client.patch(
    f"/api/v1/events/{created['id']}",
    json={
      "event_type": "walking",
      "severity": None,
      "start_device_ms": 184260,
      "end_device_ms": 184520,
      "source": "manual_review",
      "notes": None,
    },
  )

  assert response.status_code == 200
  body = response.json()
  assert body["event_type"] == "walking"
  assert body["severity"] is None
  assert body["start_device_ms"] == 184260
  assert body["end_device_ms"] == 184520
  assert body["source"] == "manual_review"
  assert body["notes"] is None
  assert body["created_at"] == created["created_at"]


def test_patch_event_rejects_invalid_payloads(client):
  create_session(client)
  created = client.post("/api/v1/events", json=valid_event_payload()).json()

  invalid_type = client.patch(f"/api/v1/events/{created['id']}", json={"event_type": "bad_type"})
  invalid_severity = client.patch(f"/api/v1/events/{created['id']}", json={"severity": 6})
  invalid_range = client.patch(
    f"/api/v1/events/{created['id']}",
    json={"start_device_ms": 500, "end_device_ms": 400},
  )
  missing_session = client.patch(f"/api/v1/events/{created['id']}", json={"session_id": "missing"})

  assert invalid_type.status_code == 422
  assert invalid_severity.status_code == 422
  assert invalid_range.status_code == 422
  assert missing_session.status_code == 404


def test_patch_event_rejects_overlap(client):
  create_session(client)
  first = client.post("/api/v1/events", json=valid_event_payload()).json()
  second = valid_event_payload()
  second["start_device_ms"] = 184400
  second["end_device_ms"] = 184500
  second_id = client.post("/api/v1/events", json=second).json()["id"]

  response = client.patch(
    f"/api/v1/events/{second_id}",
    json={"start_device_ms": first["start_device_ms"] + 10, "end_device_ms": first["end_device_ms"] + 10},
  )

  assert response.status_code == 409


def test_patch_missing_event_returns_404(client):
  response = client.patch("/api/v1/events/999", json={"event_type": "walking"})

  assert response.status_code == 404


def test_delete_event_removes_label_or_returns_404(client):
  create_session(client)
  created = client.post("/api/v1/events", json=valid_event_payload()).json()

  deleted = client.delete(f"/api/v1/events/{created['id']}")
  found_after_delete = client.get(f"/api/v1/events/{created['id']}")
  missing_delete = client.delete("/api/v1/events/999")

  assert deleted.status_code == 204
  assert found_after_delete.status_code == 404
  assert missing_delete.status_code == 404
