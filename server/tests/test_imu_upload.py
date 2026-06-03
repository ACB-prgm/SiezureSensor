from app.models import Batch, Device, IMUSample, Session


def valid_payload(sequence: int = 1234, boot_id: str = "boot-test-001") -> dict:
  return {
    "device_id": "beanie-v0-001",
    "boot_id": boot_id,
    "firmware_version": "0.1.0",
    "sequence": sequence,
    "sample_hz": 50,
    "device_ms_start": 184240,
    "battery_mv": None,
    "reset_reason": "Power on",
    "reset_info": "Fatal exception:0 flag:0",
    "uptime_ms": 184500,
    "wifi_rssi": -55,
    "free_heap": 42000,
    "min_free_heap": 39800,
    "heap_fragmentation": 3,
    "queued_batch_count": 0,
    "dropped_batch_count": 0,
    "max_sample_lateness_ms": 7,
    "upload_skip_count": 3,
    "last_http_duration_ms": 82,
    "last_http_status": 200,
    "consecutive_upload_failures": 0,
    "wifi_disconnect_count": 1,
    "samples": [
      {
        "dt_ms": 0,
        "ax": 0.02,
        "ay": -0.04,
        "az": 0.98,
        "gx": 1.2,
        "gy": -0.8,
        "gz": 0.4,
      },
      {
        "dt_ms": 20,
        "ax": 0.03,
        "ay": -0.05,
        "az": 0.99,
        "gx": 1.3,
        "gy": -0.7,
        "gz": 0.5,
      },
    ],
  }


def test_valid_batch_returns_ack_and_persists_rows(client, db_session):
  payload = valid_payload()

  response = client.post("/api/v1/imu/batch", json=payload)

  assert response.status_code == 200
  assert response.json() == {
    "status": "ok",
    "device_id": payload["device_id"],
    "sequence": payload["sequence"],
    "samples_received": len(payload["samples"]),
  }

  assert db_session.query(Device).count() == 1
  assert db_session.query(Session).count() == 1
  assert db_session.query(Batch).count() == 1
  assert db_session.query(IMUSample).count() == len(payload["samples"])

  samples = db_session.query(IMUSample).order_by(IMUSample.sample_index).all()
  assert [sample.device_ms for sample in samples] == [184240, 184260]
  assert {sample.boot_id for sample in samples} == {payload["boot_id"]}

  batch = db_session.query(Batch).one()
  assert batch.session_id.endswith("-beanie-v0-001-auto")
  assert batch.boot_id == payload["boot_id"]
  assert batch.reset_reason == "Power on"
  assert batch.reset_info == "Fatal exception:0 flag:0"
  assert batch.uptime_ms == 184500
  assert batch.wifi_rssi == -55
  assert batch.free_heap == 42000
  assert batch.min_free_heap == 39800
  assert batch.heap_fragmentation == 3
  assert batch.max_sample_lateness_ms == 7
  assert batch.upload_skip_count == 3
  assert batch.last_http_duration_ms == 82
  assert batch.last_http_status == 200
  assert batch.consecutive_upload_failures == 0
  assert batch.wifi_disconnect_count == 1
  assert batch.sample_count == len(payload["samples"])
  assert '"device_id":"beanie-v0-001"' in batch.raw_payload_json


def test_empty_samples_is_rejected(client):
  payload = valid_payload()
  payload["samples"] = []

  response = client.post("/api/v1/imu/batch", json=payload)

  assert response.status_code == 422


def test_missing_required_top_level_field_is_rejected(client):
  payload = valid_payload()
  del payload["device_id"]

  response = client.post("/api/v1/imu/batch", json=payload)

  assert response.status_code == 422


def test_missing_boot_id_is_rejected(client):
  payload = valid_payload()
  del payload["boot_id"]

  response = client.post("/api/v1/imu/batch", json=payload)

  assert response.status_code == 422


def test_missing_required_sample_field_is_rejected(client):
  payload = valid_payload()
  del payload["samples"][0]["gx"]

  response = client.post("/api/v1/imu/batch", json=payload)

  assert response.status_code == 422


def test_duplicate_sequence_returns_409_without_duplicate_samples(client, db_session):
  payload = valid_payload(sequence=42)
  first_response = client.post("/api/v1/imu/batch", json=payload)

  second_response = client.post("/api/v1/imu/batch", json=payload)

  assert first_response.status_code == 200
  assert second_response.status_code == 409
  assert db_session.query(Batch).count() == 1
  assert db_session.query(IMUSample).count() == len(payload["samples"])


def test_same_sequence_from_different_boots_is_accepted(client, db_session):
  first_payload = valid_payload(sequence=42, boot_id="boot-a")
  second_payload = valid_payload(sequence=42, boot_id="boot-b")

  first_response = client.post("/api/v1/imu/batch", json=first_payload)
  second_response = client.post("/api/v1/imu/batch", json=second_payload)

  assert first_response.status_code == 200
  assert second_response.status_code == 200
  assert db_session.query(Batch).count() == 2
  assert db_session.query(IMUSample).count() == len(first_payload["samples"]) + len(second_payload["samples"])
