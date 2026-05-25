from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "exports"

SAMPLE_QUERY = """
SELECT
  device_id,
  session_id,
  batch_sequence,
  sample_index,
  device_ms,
  server_received_at,
  ax,
  ay,
  az,
  gx,
  gy,
  gz
FROM imu_samples
WHERE session_id = ?
ORDER BY device_ms, sample_index
"""

EVENT_QUERY = """
SELECT
  id AS event_id,
  event_type,
  severity,
  start_device_ms AS event_start_device_ms,
  end_device_ms AS event_end_device_ms
FROM events
WHERE session_id = ?
ORDER BY start_device_ms, id
"""


def default_output_path(session_id: str) -> Path:
  safe_session_id = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in session_id)
  return DEFAULT_OUTPUT_DIR / f"{safe_session_id}_samples.csv"


def load_samples(connection: sqlite3.Connection, session_id: str) -> pd.DataFrame:
  samples = pd.read_sql_query(SAMPLE_QUERY, connection, params=(session_id,))
  if samples.empty:
    return samples

  samples["accel_mag"] = (samples["ax"] ** 2 + samples["ay"] ** 2 + samples["az"] ** 2) ** 0.5
  samples["gyro_mag"] = (samples["gx"] ** 2 + samples["gy"] ** 2 + samples["gz"] ** 2) ** 0.5
  return samples


def load_events(connection: sqlite3.Connection, session_id: str) -> pd.DataFrame:
  return pd.read_sql_query(EVENT_QUERY, connection, params=(session_id,))


def attach_first_overlapping_label(samples: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
  labeled = samples.copy()
  labeled["event_id"] = pd.NA
  labeled["event_type"] = pd.NA
  labeled["severity"] = pd.NA
  labeled["event_start_device_ms"] = pd.NA
  labeled["event_end_device_ms"] = pd.NA

  if labeled.empty or events.empty:
    return labeled

  for event in events.itertuples(index=False):
    mask = (
      labeled["event_id"].isna()
      & (labeled["device_ms"] >= event.event_start_device_ms)
      & (labeled["device_ms"] <= event.event_end_device_ms)
    )
    labeled.loc[mask, "event_id"] = event.event_id
    labeled.loc[mask, "event_type"] = event.event_type
    labeled.loc[mask, "severity"] = event.severity
    labeled.loc[mask, "event_start_device_ms"] = event.event_start_device_ms
    labeled.loc[mask, "event_end_device_ms"] = event.event_end_device_ms

  return labeled


def export_session(
  db_path: Path,
  session_id: str,
  include_labels: bool = False,
  output: Path | None = None,
) -> Path:
  output_path = output or default_output_path(session_id)
  output_path.parent.mkdir(parents=True, exist_ok=True)

  with sqlite3.connect(db_path) as connection:
    samples = load_samples(connection, session_id)
    if include_labels:
      samples = attach_first_overlapping_label(samples, load_events(connection, session_id))

  samples.to_csv(output_path, index=False)
  return output_path


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(description="Export one IMU session from SQLite to CSV.")
  parser.add_argument("--db-path", required=True, type=Path)
  parser.add_argument("--session-id", required=True)
  parser.add_argument("--include-labels", action="store_true")
  parser.add_argument("--output", type=Path)
  return parser


def main() -> None:
  args = build_parser().parse_args()
  output_path = export_session(
    db_path=args.db_path,
    session_id=args.session_id,
    include_labels=args.include_labels,
    output=args.output,
  )
  print(output_path)


if __name__ == "__main__":
  main()
