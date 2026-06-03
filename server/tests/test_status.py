from tests.test_imu_upload import valid_payload


def test_status_endpoint_returns_database_summary(client):
  response = client.get("/api/v1/status")

  assert response.status_code == 200
  body = response.json()
  assert body["status"] == "ok"
  assert body["session_count"] == 0
  assert body["batch_count"] == 0
  assert body["sample_count"] == 0
  assert body["latest_session"] is None


def test_status_endpoint_returns_latest_device_diagnostics(client):
  payload = valid_payload(sequence=7, boot_id="boot-status-001")
  response = client.post("/api/v1/imu/batch", json=payload)
  assert response.status_code == 200

  status_response = client.get("/api/v1/status")

  assert status_response.status_code == 200
  body = status_response.json()
  assert body["latest_boot_id"] == "boot-status-001"
  assert body["latest_reset_reason"] == payload["reset_reason"]
  assert body["latest_reset_info"] == payload["reset_info"]
  assert body["latest_uptime_ms"] == payload["uptime_ms"]
  assert body["latest_wifi_rssi"] == payload["wifi_rssi"]
  assert body["latest_free_heap"] == payload["free_heap"]
  assert body["latest_min_free_heap"] == payload["min_free_heap"]
  assert body["latest_heap_fragmentation"] == payload["heap_fragmentation"]
  assert body["latest_last_http_duration_ms"] == payload["last_http_duration_ms"]
  assert body["latest_last_http_status"] == payload["last_http_status"]
  assert body["latest_consecutive_upload_failures"] == payload["consecutive_upload_failures"]
  assert body["latest_wifi_disconnect_count"] == payload["wifi_disconnect_count"]
