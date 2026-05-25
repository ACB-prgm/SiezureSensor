from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "plots"

SESSION_QUERY = """
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
ORDER BY device_ms, sample_index
"""


def safe_name(value: str) -> str:
  return "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in value)


def load_session_samples(db_path: Path, session_id: str) -> pd.DataFrame:
  with sqlite3.connect(db_path) as connection:
    samples = pd.read_sql_query(SESSION_QUERY, connection, params=(session_id,))

  if samples.empty:
    raise ValueError(f"No samples found for session_id={session_id}")

  samples["accel_mag"] = (samples["ax"] ** 2 + samples["ay"] ** 2 + samples["az"] ** 2) ** 0.5
  samples["gyro_mag"] = (samples["gx"] ** 2 + samples["gy"] ** 2 + samples["gz"] ** 2) ** 0.5
  samples["time_s"] = (samples["device_ms"] - samples["device_ms"].iloc[0]) / 1000.0
  return samples


def plot_session(db_path: Path, session_id: str, output_dir: Path = DEFAULT_OUTPUT_DIR) -> Path:
  samples = load_session_samples(db_path, session_id)
  output_dir.mkdir(parents=True, exist_ok=True)
  output_path = output_dir / f"{safe_name(session_id)}_session.png"

  fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
  axes[0].plot(samples["time_s"], samples["ax"], label="ax")
  axes[0].plot(samples["time_s"], samples["ay"], label="ay")
  axes[0].plot(samples["time_s"], samples["az"], label="az")
  axes[0].set_ylabel("accel (g)")
  axes[0].legend(loc="upper right")

  axes[1].plot(samples["time_s"], samples["gx"], label="gx")
  axes[1].plot(samples["time_s"], samples["gy"], label="gy")
  axes[1].plot(samples["time_s"], samples["gz"], label="gz")
  axes[1].set_ylabel("gyro (deg/s)")
  axes[1].legend(loc="upper right")

  axes[2].plot(samples["time_s"], samples["accel_mag"], color="black")
  axes[2].set_ylabel("accel mag")

  axes[3].plot(samples["time_s"], samples["gyro_mag"], color="black")
  axes[3].set_ylabel("gyro mag")
  axes[3].set_xlabel("time (s)")

  fig.suptitle(f"Session {session_id}")
  fig.tight_layout()
  fig.savefig(output_path)
  plt.close(fig)
  return output_path


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(description="Plot one IMU session.")
  parser.add_argument("--db-path", required=True, type=Path)
  parser.add_argument("--session-id", required=True)
  parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
  return parser


def main() -> None:
  args = build_parser().parse_args()
  print(plot_session(args.db_path, args.session_id, args.output_dir))


if __name__ == "__main__":
  main()
