import subprocess
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
  sys.path.insert(0, str(REPO_ROOT))

from analysis.scripts.build_windows import build_window_exports, build_windows_for_session, classify_window
from app.database import get_database_path


def populate_window_session(client) -> str:
  session_id = "window-session"
  device_id = "beanie-v0-001"
  response = client.post("/api/v1/sessions", json={"session_id": session_id, "device_id": device_id})
  assert response.status_code == 201

  for sequence in range(8):
    payload = {
      "device_id": device_id,
      "boot_id": "boot-window-001",
      "firmware_version": "0.1.0",
      "sequence": sequence,
      "sample_hz": 50,
      "device_ms_start": sequence * 1000,
      "battery_mv": None,
      "samples": [
        {
          "dt_ms": sample_index * 20,
          "ax": 0.01 * (sequence + sample_index),
          "ay": -0.02 * sample_index,
          "az": 1.0,
          "gx": 0.5 * sample_index,
          "gy": -0.25 * sample_index,
          "gz": 0.1 * sequence,
        }
        for sample_index in range(50)
      ],
    }
    upload = client.post("/api/v1/imu/batch", json=payload)
    assert upload.status_code == 200

  walking = {
    "session_id": session_id,
    "event_type": "walking",
    "severity": 2,
    "start_device_ms": 1000,
    "end_device_ms": 3000,
    "source": "manual",
    "notes": "steady walk",
  }
  scratching = {
    "session_id": session_id,
    "event_type": "scratching",
    "severity": 3,
    "start_device_ms": 3500,
    "end_device_ms": 4200,
    "source": "manual",
    "notes": "short scratch",
  }
  assert client.post("/api/v1/events", json=walking).status_code == 201
  assert client.post("/api/v1/events", json=scratching).status_code == 201
  return session_id


def test_classify_window_keeps_unlabeled_distinct_from_unknown():
  events = pd.DataFrame(
    [
      {
        "id": 1,
        "event_type": "unknown",
        "start_device_ms": 1000,
        "end_device_ms": 3000,
      }
    ]
  )

  unlabeled = classify_window(events, 3000, 5000, overlap_threshold=0.8, mixed_policy="keep")
  unknown = classify_window(events, 1000, 3000, overlap_threshold=0.8, mixed_policy="keep")

  assert unlabeled["label"] == "unlabeled"
  assert unlabeled["label_source"] == "unlabeled"
  assert unknown["label"] == "unknown"
  assert unknown["label_source"] == "human"


def test_build_windows_excludes_boundary_mixed_windows_by_default():
  samples = pd.DataFrame(
    {
      "device_id": ["device-a"] * 300,
      "session_id": ["session-a"] * 300,
      "batch_sequence": [0] * 300,
      "sample_index": list(range(300)),
      "device_ms": [index * 20 for index in range(300)],
      "ax": [0.1] * 300,
      "ay": [0.2] * 300,
      "az": [1.0] * 300,
      "gx": [0.3] * 300,
      "gy": [0.4] * 300,
      "gz": [0.5] * 300,
    }
  )
  samples["accel_mag"] = (samples["ax"] ** 2 + samples["ay"] ** 2 + samples["az"] ** 2) ** 0.5
  samples["gyro_mag"] = (samples["gx"] ** 2 + samples["gy"] ** 2 + samples["gz"] ** 2) ** 0.5
  events = pd.DataFrame(
    [
      {
        "id": 1,
        "event_type": "walking",
        "start_device_ms": 0,
        "end_device_ms": 2000,
      },
      {
        "id": 2,
        "event_type": "scratching",
        "start_device_ms": 2000,
        "end_device_ms": 3000,
      },
    ]
  )

  windows, features = build_windows_for_session(
    samples=samples,
    events=events,
    window_ms=2000,
    stride_ms=1000,
    mixed_policy="exclude",
  )

  assert list(windows["label"]) == ["walking", "unlabeled"]
  assert len(features) == len(windows)
  assert "accel_mag_mean" in features.columns
  assert "gx_mean_abs_delta" in features.columns


def test_build_window_exports_writes_manifest_and_features(client, tmp_path):
  session_id = populate_window_session(client)

  exports = build_window_exports(
    db_path=get_database_path(),
    session_ids=[session_id],
    output_dir=tmp_path,
    window_ms=2000,
    stride_ms=1000,
    mixed_policy="keep",
  )

  assert len(exports) == 1
  export = exports[0]
  windows = pd.read_csv(export.windows_path)
  features = pd.read_csv(export.features_path)
  assert export.window_count == len(windows)
  assert len(features) == len(windows)
  assert {"walking", "mixed", "unlabeled"}.issubset(set(windows["label"]))
  assert "class_fractions_json" in windows.columns
  assert "accel_mag_rms" in features.columns
  assert int(features.iloc[0]["sample_count"]) == 100


def test_build_windows_cli_dry_run(client, tmp_path):
  session_id = populate_window_session(client)
  script_path = REPO_ROOT / "analysis" / "scripts" / "build_windows.py"

  result = subprocess.run(
    [
      sys.executable,
      str(script_path),
      "--db-path",
      str(get_database_path()),
      "--session-id",
      session_id,
      "--window-ms",
      "2000",
      "--stride-ms",
      "1000",
      "--mixed-policy",
      "keep",
      "--output-dir",
      str(tmp_path),
    ],
    check=True,
    capture_output=True,
    text=True,
  )

  assert f"{session_id} 2000ms/1000ms" in result.stdout
  assert (tmp_path / f"{session_id}_2000ms_1000ms_windows.csv").exists()
  assert (tmp_path / f"{session_id}_2000ms_1000ms_features.csv").exists()
