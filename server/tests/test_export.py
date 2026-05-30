import csv
from io import StringIO
from math import sqrt

from tests.test_imu_upload import valid_payload


REQUIRED_COLUMNS = [
  "device_id",
  "session_id",
  "boot_id",
  "batch_sequence",
  "sample_index",
  "device_ms",
  "server_received_at",
  "ax",
  "ay",
  "az",
  "gx",
  "gy",
  "gz",
  "accel_mag",
  "gyro_mag",
]


def rows_from_response(response) -> list[dict[str, str]]:
  return list(csv.DictReader(StringIO(response.text)))


def insert_batch(client, session_id: str, sequence: int, device_ms_start: int = 1000):
  payload = valid_payload(sequence=sequence)
  payload["device_ms_start"] = device_ms_start
  create_response = client.post("/api/v1/sessions", json={"session_id": session_id, "device_id": payload["device_id"]})
  assert create_response.status_code in {201, 409}
  response = client.post("/api/v1/imu/batch", json=payload)
  assert response.status_code == 200
  return payload


def test_export_samples_returns_csv_with_required_columns(client):
  insert_batch(client, "session-a", 1)

  response = client.get("/api/v1/export/samples")

  assert response.status_code == 200
  assert response.headers["content-type"].startswith("text/csv")
  rows = rows_from_response(response)
  assert list(rows[0].keys()) == REQUIRED_COLUMNS


def test_export_samples_filters_by_session(client):
  insert_batch(client, "session-a", 1)
  insert_batch(client, "session-b", 2)

  response = client.get("/api/v1/export/samples", params={"session_id": "session-b"})

  assert response.status_code == 200
  rows = rows_from_response(response)
  assert len(rows) == 2
  assert {row["session_id"] for row in rows} == {"session-b"}


def test_export_samples_filters_by_device_ms_range(client):
  insert_batch(client, "session-a", 1, device_ms_start=1000)

  response = client.get(
    "/api/v1/export/samples",
    params={"start_device_ms": 1020, "end_device_ms": 1020},
  )

  assert response.status_code == 200
  rows = rows_from_response(response)
  assert len(rows) == 1
  assert rows[0]["device_ms"] == "1020"


def test_export_samples_includes_correct_derived_magnitudes(client):
  payload = insert_batch(client, "session-a", 1)

  response = client.get("/api/v1/export/samples", params={"session_id": "session-a"})

  assert response.status_code == 200
  rows = rows_from_response(response)
  first_sample = payload["samples"][0]
  expected_accel_mag = sqrt(first_sample["ax"] ** 2 + first_sample["ay"] ** 2 + first_sample["az"] ** 2)
  expected_gyro_mag = sqrt(first_sample["gx"] ** 2 + first_sample["gy"] ** 2 + first_sample["gz"] ** 2)
  assert float(rows[0]["accel_mag"]) == expected_accel_mag
  assert float(rows[0]["gyro_mag"]) == expected_gyro_mag


def test_export_rejects_non_csv_format(client):
  response = client.get("/api/v1/export/samples", params={"format": "json"})

  assert response.status_code == 400
