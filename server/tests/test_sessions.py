from tests.test_export import insert_batch


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
