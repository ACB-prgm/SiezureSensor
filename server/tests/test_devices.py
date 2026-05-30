from app.models import ActiveDeviceSession


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
