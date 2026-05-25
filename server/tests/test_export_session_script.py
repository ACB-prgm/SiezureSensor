import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
  sys.path.insert(0, str(REPO_ROOT))

from analysis.scripts.export_session import export_session
from app.database import get_database_path
from tests.test_events import valid_event_payload
from tests.test_imu_upload import valid_payload


def populate_labeled_session(client) -> str:
  payload = valid_payload(sequence=7)
  payload["session_id"] = "script-session"
  payload["device_ms_start"] = 1000
  response = client.post("/api/v1/imu/batch", json=payload)
  assert response.status_code == 200

  event = valid_event_payload("script-session")
  event["start_device_ms"] = 1020
  event["end_device_ms"] = 1040
  event["event_type"] = "walking"
  event_response = client.post("/api/v1/events", json=event)
  assert event_response.status_code == 201
  return payload["session_id"]


def test_export_session_writes_csv_with_labels(client, tmp_path):
  session_id = populate_labeled_session(client)
  output_path = tmp_path / "session.csv"

  written_path = export_session(
    db_path=get_database_path(),
    session_id=session_id,
    include_labels=True,
    output=output_path,
  )

  assert written_path == output_path
  exported = pd.read_csv(output_path)
  assert list(exported["session_id"].unique()) == [session_id]
  assert "event_type" in exported.columns
  labeled_rows = exported[exported["event_type"] == "walking"]
  assert len(labeled_rows) == 1
  assert int(labeled_rows.iloc[0]["device_ms"]) == 1020


def test_export_session_cli_dry_run(client, tmp_path):
  session_id = populate_labeled_session(client)
  output_path = tmp_path / "cli-session.csv"
  script_path = REPO_ROOT / "analysis" / "scripts" / "export_session.py"

  result = subprocess.run(
    [
      sys.executable,
      str(script_path),
      "--db-path",
      str(get_database_path()),
      "--session-id",
      session_id,
      "--include-labels",
      "--output",
      str(output_path),
    ],
    check=True,
    capture_output=True,
    text=True,
  )

  assert str(output_path) in result.stdout
  with sqlite3.connect(get_database_path()) as connection:
    db_count = connection.execute("SELECT COUNT(*) FROM imu_samples WHERE session_id = ?", (session_id,)).fetchone()[0]
  exported = pd.read_csv(output_path)
  assert len(exported) == db_count
