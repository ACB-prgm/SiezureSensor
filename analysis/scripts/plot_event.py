from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
  sys.path.insert(0, str(REPO_ROOT))

from analysis.scripts.plot_session import DEFAULT_OUTPUT_DIR, safe_name


EVENT_QUERY = """
SELECT
  id,
  session_id,
  event_type,
  start_device_ms,
  end_device_ms
FROM events
WHERE id = ?
"""

WINDOW_QUERY = """
SELECT
  device_ms,
  ax,
  ay,
  az,
  gx,
  gy,
  gz
FROM imu_samples
WHERE session_id = ?
  AND device_ms >= ?
  AND device_ms <= ?
ORDER BY device_ms, sample_index
"""


def load_event_window(db_path: Path, event_id: int, padding_ms: int) -> tuple[pd.Series, pd.DataFrame]:
  with sqlite3.connect(db_path) as connection:
    events = pd.read_sql_query(EVENT_QUERY, connection, params=(event_id,))
    if events.empty:
      raise ValueError(f"No event found for event_id={event_id}")

    event = events.iloc[0]
    window_start = max(0, int(event["start_device_ms"]) - padding_ms)
    window_end = int(event["end_device_ms"]) + padding_ms
    samples = pd.read_sql_query(
      WINDOW_QUERY,
      connection,
      params=(event["session_id"], window_start, window_end),
    )

  if samples.empty:
    raise ValueError(f"No samples found for event_id={event_id}")

  samples["accel_mag"] = (samples["ax"] ** 2 + samples["ay"] ** 2 + samples["az"] ** 2) ** 0.5
  samples["gyro_mag"] = (samples["gx"] ** 2 + samples["gy"] ** 2 + samples["gz"] ** 2) ** 0.5
  samples["time_s"] = (samples["device_ms"] - int(event["start_device_ms"])) / 1000.0
  return event, samples


def plot_event(
  db_path: Path,
  event_id: int,
  padding_ms: int = 5000,
  output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Path:
  event, samples = load_event_window(db_path, event_id, padding_ms)
  output_dir.mkdir(parents=True, exist_ok=True)
  output_path = output_dir / f"event_{event_id}_{safe_name(event['event_type'])}.png"

  event_start_s = 0.0
  event_end_s = (int(event["end_device_ms"]) - int(event["start_device_ms"])) / 1000.0

  fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
  axes[0].plot(samples["time_s"], samples["ax"], label="ax")
  axes[0].plot(samples["time_s"], samples["ay"], label="ay")
  axes[0].plot(samples["time_s"], samples["az"], label="az")
  axes[0].plot(samples["time_s"], samples["accel_mag"], label="accel_mag", color="black", linewidth=1)
  axes[0].set_ylabel("accel (g)")
  axes[0].legend(loc="upper right")

  axes[1].plot(samples["time_s"], samples["gx"], label="gx")
  axes[1].plot(samples["time_s"], samples["gy"], label="gy")
  axes[1].plot(samples["time_s"], samples["gz"], label="gz")
  axes[1].plot(samples["time_s"], samples["gyro_mag"], label="gyro_mag", color="black", linewidth=1)
  axes[1].set_ylabel("gyro (deg/s)")
  axes[1].set_xlabel("time from event start (s)")
  axes[1].legend(loc="upper right")

  for axis in axes:
    axis.axvline(event_start_s, color="green", linestyle="--", linewidth=1)
    axis.axvline(event_end_s, color="red", linestyle="--", linewidth=1)

  fig.suptitle(f"Event {event_id}: {event['event_type']}")
  fig.tight_layout()
  fig.savefig(output_path)
  plt.close(fig)
  return output_path


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(description="Plot one event-centered IMU window.")
  parser.add_argument("--db-path", required=True, type=Path)
  parser.add_argument("--event-id", required=True, type=int)
  parser.add_argument("--padding-ms", type=int, default=5000)
  parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
  return parser


def main() -> None:
  args = build_parser().parse_args()
  print(plot_event(args.db_path, args.event_id, args.padding_ms, args.output_dir))


if __name__ == "__main__":
  main()
