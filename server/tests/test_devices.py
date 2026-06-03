from app.models import ActiveDeviceSession
from tests.test_imu_upload import valid_payload


def test_get_active_session_returns_null_when_missing(client):
  response = client.get("/api/v1/devices/beanie-v0-001/active-session")

  assert response.status_code == 200
  assert response.json() is None


def test_create_session_marks_device_active(client, db_session):
  response = client.post("/api/v1/sessions", json={"session_id": "manual-session", "device_id": "beanie-v0-001"})

  assert response.status_code == 201
  active = db_session.get(ActiveDeviceSession, "beanie-v0-001")
  assert active is not None
  assert active.session_id == "manual-session"


def test_update_active_session_routes_future_uploads(client):
  assert client.post("/api/v1/sessions", json={"session_id": "session-a", "device_id": "beanie-v0-001"}).status_code == 201
  assert client.post("/api/v1/sessions", json={"session_id": "session-b", "device_id": "beanie-v0-001"}).status_code == 201

  response = client.post("/api/v1/devices/beanie-v0-001/active-session", json={"session_id": "session-a"})

  assert response.status_code == 200
  body = response.json()
  assert body["device_id"] == "beanie-v0-001"
  assert body["session_id"] == "session-a"
  assert body["session"]["session_id"] == "session-a"


def test_update_active_session_rejects_wrong_device_session(client):
  assert client.post("/api/v1/sessions", json={"session_id": "session-a", "device_id": "beanie-v0-001"}).status_code == 201
  assert client.post("/api/v1/sessions", json={"session_id": "session-b", "device_id": "beanie-v0-002"}).status_code == 201

  response = client.post("/api/v1/devices/beanie-v0-001/active-session", json={"session_id": "session-b"})

  assert response.status_code == 404


def test_list_device_boots_returns_session_boot_diagnostics(client):
  assert client.post("/api/v1/sessions", json={"session_id": "session-a", "device_id": "beanie-v0-001"}).status_code == 201
  first = valid_payload(sequence=1, boot_id="boot-a")
  first["device_ms_start"] = 1000
  second = valid_payload(sequence=2, boot_id="boot-a")
  second["device_ms_start"] = 2000
  second["dropped_batch_count"] = 2
  second["consecutive_upload_failures"] = 4
  other_boot = valid_payload(sequence=1, boot_id="boot-b")
  other_boot["device_ms_start"] = 3000
  other_boot["reset_reason"] = "Hardware Watchdog"

  assert client.post("/api/v1/imu/batch", json=first).status_code == 200
  assert client.post("/api/v1/imu/batch", json=second).status_code == 200
  assert client.post("/api/v1/imu/batch", json=other_boot).status_code == 200

  response = client.get("/api/v1/devices/beanie-v0-001/boots", params={"session_id": "session-a"})

  assert response.status_code == 200
  rows = response.json()
  assert {row["boot_id"] for row in rows} == {"boot-a", "boot-b"}
  boot_a = next(row for row in rows if row["boot_id"] == "boot-a")
  assert boot_a["batch_count"] == 2
  assert boot_a["sample_count"] == 4
  assert boot_a["min_sequence"] == 1
  assert boot_a["max_sequence"] == 2
  assert boot_a["max_dropped_batch_count"] == 2
  assert boot_a["max_consecutive_upload_failures"] == 4
  assert boot_a["min_free_heap"] == first["free_heap"]
  assert boot_a["min_reported_free_heap"] == first["min_free_heap"]
