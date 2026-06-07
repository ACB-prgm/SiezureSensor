from tests.test_export import insert_batch
from app.models import Batch, Event, IMUSample, Session


def test_create_session_succeeds_with_new_device(client):
  response = client.post(
    "/api/v1/sessions",
    json={
      "session_id": "manual-session",
      "device_id": "beanie-v0-002",
      "mount_location": "collar",
      "notes": "manual setup",
    },
  )

  assert response.status_code == 201
  body = response.json()
  assert body["session_id"] == "manual-session"
  assert body["device_id"] == "beanie-v0-002"
  assert body["mount_location"] == "collar"
  assert body["sample_count"] == 0
  assert body["batch_count"] == 0


def test_create_session_rejects_duplicate_session_id(client):
  payload = {"session_id": "manual-session", "device_id": "beanie-v0-002"}
  assert client.post("/api/v1/sessions", json=payload).status_code == 201

  response = client.post("/api/v1/sessions", json=payload)

  assert response.status_code == 409


def test_list_sessions_returns_metadata(client):
  insert_batch(client, "session-a", 1, device_ms_start=1000)
  insert_batch(client, "session-b", 2, device_ms_start=2000)

  response = client.get("/api/v1/sessions")

  assert response.status_code == 200
  body = response.json()
  assert [session["session_id"] for session in body] == ["session-a", "session-b"]
  session_a = body[0]
  assert session_a["device_id"] == "beanie-v0-001"
  assert session_a["sample_count"] == 2
  assert session_a["batch_count"] == 1
  assert session_a["min_device_ms"] == 1000
  assert session_a["max_device_ms"] == 1020
  assert session_a["first_server_received_at"]
  assert session_a["last_server_received_at"]


def test_list_session_samples_filters_by_device_ms_range(client):
  insert_batch(client, "session-a", 1, device_ms_start=1000)

  response = client.get(
    "/api/v1/sessions/session-a/samples",
    params={"start_device_ms": 1020, "end_device_ms": 1020},
  )

  assert response.status_code == 200
  body = response.json()
  assert len(body) == 1
  assert body[0]["device_ms"] == 1020
  assert body[0]["accel_mag"] > 0
  assert body[0]["gyro_mag"] > 0


def test_list_session_samples_downsamples_to_max_points(client):
  insert_batch(client, "session-a", 1, device_ms_start=1000)
  insert_batch(client, "session-a", 2, device_ms_start=1040)

  response = client.get("/api/v1/sessions/session-a/samples", params={"max_points": 2})

  assert response.status_code == 200
  body = response.json()
  assert len(body) == 2
  assert body[0]["device_ms"] == 1000


def test_session_sample_window_defaults_to_latest_points_with_metadata(client):
  insert_batch(client, "session-a", 1, device_ms_start=1000)
  insert_batch(client, "session-a", 2, device_ms_start=1040)

  response = client.get("/api/v1/sessions/session-a/sample-window", params={"max_points": 2})

  assert response.status_code == 200
  body = response.json()
  assert body["total_sample_count"] == 4
  assert body["window_start_index"] == 2
  assert body["window_end_index"] == 3
  assert [sample["device_ms"] for sample in body["samples"]] == [1040, 1060]


def test_session_sample_window_filters_by_server_time(client, db_session):
  insert_batch(client, "session-a", 1, device_ms_start=1000)
  insert_batch(client, "session-a", 2, device_ms_start=1040)
  first_batch_received_at = (
    db_session.query(IMUSample.server_received_at)
    .filter(IMUSample.session_id == "session-a")
    .order_by(IMUSample.id)
    .first()[0]
  )

  response = client.get(
    "/api/v1/sessions/session-a/sample-window",
    params={"end_server_received_at": first_batch_received_at, "max_points": 20},
  )

  assert response.status_code == 200
  body = response.json()
  assert body["total_sample_count"] == 4
  assert body["window_start_index"] == 0
  assert [sample["device_ms"] for sample in body["samples"]] == [1000, 1020]


def test_list_session_samples_missing_session_returns_404(client):
  response = client.get("/api/v1/sessions/missing/samples")

  assert response.status_code == 404


def test_list_session_samples_rejects_invalid_range(client):
  insert_batch(client, "session-a", 1, device_ms_start=1000)

  response = client.get(
    "/api/v1/sessions/session-a/samples",
    params={"start_device_ms": 2000, "end_device_ms": 1000},
  )

  assert response.status_code == 400


def test_delete_session_removes_owned_data(client, db_session):
  insert_batch(client, "session-a", 1)
  insert_batch(client, "session-b", 2)
  event = {
    "session_id": "session-a",
    "event_type": "walking",
    "severity": 1,
    "start_device_ms": 1000,
    "end_device_ms": 1020,
    "source": "manual",
    "notes": "junk",
  }
  assert client.post("/api/v1/events", json=event).status_code == 201

  response = client.delete("/api/v1/sessions/session-a")

  assert response.status_code == 204
  assert db_session.get(Session, "session-a") is None
  assert db_session.query(Batch).filter(Batch.session_id == "session-a").count() == 0
  assert db_session.query(IMUSample).filter(IMUSample.session_id == "session-a").count() == 0
  assert db_session.query(Event).filter(Event.session_id == "session-a").count() == 0
  assert db_session.get(Session, "session-b") is not None


def test_delete_active_session_is_rejected(client):
  insert_batch(client, "session-a", 1)

  response = client.delete("/api/v1/sessions/session-a")

  assert response.status_code == 409


def test_delete_missing_session_returns_404(client):
  response = client.delete("/api/v1/sessions/missing")

  assert response.status_code == 404
