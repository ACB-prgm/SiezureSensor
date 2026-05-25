from app.models import Batch, Device, IMUSample, Session


def valid_payload(sequence: int = 1234) -> dict:
  return {
    "device_id": "beanie-v0-001",
    "firmware_version": "0.1.0",
    "session_id": "2026-05-23T20-15-00-beanie-v0-001",
    "sequence": sequence,
    "sample_hz": 50,
    "device_ms_start": 184240,
    "battery_mv": None,
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

  batch = db_session.query(Batch).one()
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
