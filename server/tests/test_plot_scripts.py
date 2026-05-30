import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
  sys.path.insert(0, str(REPO_ROOT))

from analysis.scripts.plot_event import plot_event
from analysis.scripts.plot_session import plot_session
from app.database import get_database_path
from tests.test_events import valid_event_payload
from tests.test_imu_upload import valid_payload


def populate_event_window(client) -> int:
  assert client.post("/api/v1/sessions", json={"session_id": "plot-session", "device_id": "beanie-v0-001"}).status_code == 201
  payload = valid_payload(sequence=11)
  payload["device_ms_start"] = 1000
  payload["samples"] = [
    {"dt_ms": 0, "ax": 0.0, "ay": 0.0, "az": 1.0, "gx": 0.0, "gy": 0.0, "gz": 0.0},
    {"dt_ms": 20, "ax": 0.1, "ay": 0.0, "az": 1.0, "gx": 1.0, "gy": 0.0, "gz": 0.0},
    {"dt_ms": 40, "ax": 0.2, "ay": 0.1, "az": 1.0, "gx": 2.0, "gy": 1.0, "gz": 0.0},
  ]
  assert client.post("/api/v1/imu/batch", json=payload).status_code == 200

  event = valid_event_payload("plot-session")
  event["start_device_ms"] = 1020
  event["end_device_ms"] = 1040
  response = client.post("/api/v1/events", json=event)
  assert response.status_code == 201
  return response.json()["id"]


def test_plot_session_creates_png(client, tmp_path):
  populate_event_window(client)

  output_path = plot_session(get_database_path(), "plot-session", tmp_path)

  assert output_path.exists()
  assert output_path.suffix == ".png"
  assert output_path.stat().st_size > 0


def test_plot_event_creates_png(client, tmp_path):
  event_id = populate_event_window(client)

  output_path = plot_event(get_database_path(), event_id, padding_ms=20, output_dir=tmp_path)

  assert output_path.exists()
  assert output_path.suffix == ".png"
  assert output_path.stat().st_size > 0
