#!/usr/bin/env python3
"""Build sliding-window model datasets from raw IMU samples and event spans."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DEFAULT_OUTPUT_DIR = Path("data/exports")
DEFAULT_WINDOW_CONFIGS = ((2000, 500), (5000, 1000))
SENSOR_COLUMNS = ("ax", "ay", "az", "gx", "gy", "gz")
FEATURE_COLUMNS = (*SENSOR_COLUMNS, "accel_mag", "gyro_mag")


@dataclass(frozen=True)
class WindowExport:
  session_id: str
  window_ms: int
  stride_ms: int
  windows_path: Path
  features_path: Path
  window_count: int
  feature_count: int


def safe_name(value: str) -> str:
  return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "session"


def load_session_samples(connection: sqlite3.Connection, session_id: str) -> pd.DataFrame:
  query = """
    SELECT
      device_id,
      session_id,
      boot_id,
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
    ORDER BY device_ms, batch_sequence, sample_index
  """
  samples = pd.read_sql_query(query, connection, params=(session_id,))
  if samples.empty:
    return samples

  samples["accel_mag"] = np.sqrt(samples["ax"] ** 2 + samples["ay"] ** 2 + samples["az"] ** 2)
  samples["gyro_mag"] = np.sqrt(samples["gx"] ** 2 + samples["gy"] ** 2 + samples["gz"] ** 2)
  return samples


def load_session_events(connection: sqlite3.Connection, session_id: str) -> pd.DataFrame:
  query = """
    SELECT
      id,
      session_id,
      event_type,
      severity,
      start_device_ms,
      end_device_ms,
      source,
      notes,
      created_at
    FROM events
    WHERE session_id = ?
    ORDER BY start_device_ms, id
  """
  return pd.read_sql_query(query, connection, params=(session_id,))


def classify_window(
  events: pd.DataFrame,
  window_start_ms: int,
  window_end_ms: int,
  overlap_threshold: float,
  mixed_policy: str,
) -> dict | None:
  window_duration_ms = window_end_ms - window_start_ms
  if window_duration_ms <= 0:
    raise ValueError("window_end_ms must be greater than window_start_ms")

  overlaps: dict[str, float] = {}
  event_ids: list[int] = []
  if not events.empty:
    for event in events.itertuples(index=False):
      overlap_ms = max(
        0,
        min(window_end_ms, int(event.end_device_ms)) - max(window_start_ms, int(event.start_device_ms)),
      )
      if overlap_ms <= 0:
        continue
      event_type = str(event.event_type)
      overlaps[event_type] = overlaps.get(event_type, 0.0) + (overlap_ms / window_duration_ms)
      event_ids.append(int(event.id))

  if not overlaps:
    label = "unlabeled"
    label_source = "unlabeled"
    overlap_ratio = 0.0
  elif len(overlaps) == 1:
    label, overlap_ratio = next(iter(overlaps.items()))
    if overlap_ratio >= overlap_threshold:
      label_source = "human"
    else:
      label = "mixed"
      label_source = "mixed"
  else:
    label = "mixed"
    label_source = "mixed"
    overlap_ratio = max(overlaps.values())

  if label == "mixed" and mixed_policy == "exclude":
    return None

  return {
    "label": label,
    "label_source": label_source,
    "overlap_ratio": round(float(overlap_ratio), 6),
    "event_ids_json": json.dumps(event_ids, separators=(",", ":")),
    "class_fractions_json": json.dumps(
      {key: round(float(value), 6) for key, value in sorted(overlaps.items())},
      separators=(",", ":"),
    ),
  }


def extract_features(window_samples: pd.DataFrame) -> dict:
  features: dict[str, float | int] = {"sample_count": int(len(window_samples))}
  for column in FEATURE_COLUMNS:
    values = window_samples[column].to_numpy(dtype=float)
    features[f"{column}_mean"] = float(np.mean(values))
    features[f"{column}_std"] = float(np.std(values))
    features[f"{column}_min"] = float(np.min(values))
    features[f"{column}_max"] = float(np.max(values))
    features[f"{column}_median"] = float(np.median(values))
    features[f"{column}_p05"] = float(np.percentile(values, 5))
    features[f"{column}_p95"] = float(np.percentile(values, 95))
    features[f"{column}_rms"] = float(np.sqrt(np.mean(np.square(values))))
    features[f"{column}_energy"] = float(np.sum(np.square(values)) / len(values))
    features[f"{column}_mean_abs_delta"] = float(np.mean(np.abs(np.diff(values)))) if len(values) > 1 else 0.0
  return features


def build_windows_for_session(
  samples: pd.DataFrame,
  events: pd.DataFrame,
  window_ms: int,
  stride_ms: int,
  overlap_threshold: float = 0.8,
  mixed_policy: str = "exclude",
  feature_set_version: str = "v0",
) -> tuple[pd.DataFrame, pd.DataFrame]:
  if window_ms <= 0:
    raise ValueError("window_ms must be positive")
  if stride_ms <= 0:
    raise ValueError("stride_ms must be positive")
  if not 0 < overlap_threshold <= 1:
    raise ValueError("overlap_threshold must be greater than 0 and less than or equal to 1")
  if mixed_policy not in {"exclude", "keep"}:
    raise ValueError("mixed_policy must be 'exclude' or 'keep'")
  if samples.empty:
    return pd.DataFrame(), pd.DataFrame()

  samples = samples.sort_values(["device_ms", "batch_sequence", "sample_index"]).reset_index(drop=True)
  device_id = str(samples.iloc[0]["device_id"])
  session_id = str(samples.iloc[0]["session_id"])
  min_device_ms = int(samples["device_ms"].min())
  max_device_ms = int(samples["device_ms"].max())
  last_start_ms = max_device_ms - window_ms + 1
  if last_start_ms < min_device_ms:
    return pd.DataFrame(), pd.DataFrame()

  manifest_rows: list[dict] = []
  feature_rows: list[dict] = []
  window_index = 0
  for window_start_ms in range(min_device_ms, last_start_ms + 1, stride_ms):
    window_end_ms = window_start_ms + window_ms
    mask = (samples["device_ms"] >= window_start_ms) & (samples["device_ms"] < window_end_ms)
    window_samples = samples.loc[mask]
    if window_samples.empty:
      continue

    classification = classify_window(events, window_start_ms, window_end_ms, overlap_threshold, mixed_policy)
    if classification is None:
      continue

    row = {
      "window_id": f"{safe_name(session_id)}-{window_ms}ms-{stride_ms}ms-{window_index:06d}",
      "session_id": session_id,
      "device_id": device_id,
      "window_start_device_ms": int(window_start_ms),
      "window_end_device_ms": int(window_end_ms),
      "window_center_device_ms": int(window_start_ms + (window_ms // 2)),
      "window_ms": int(window_ms),
      "stride_ms": int(stride_ms),
      "sample_count": int(len(window_samples)),
      "feature_set_version": feature_set_version,
      **classification,
    }
    manifest_rows.append(row)
    feature_rows.append({**row, **extract_features(window_samples)})
    window_index += 1

  return pd.DataFrame(manifest_rows), pd.DataFrame(feature_rows)


def resolve_window_configs(window_ms: int | None, stride_ms: int | None) -> list[tuple[int, int]]:
  if window_ms is None and stride_ms is None:
    return list(DEFAULT_WINDOW_CONFIGS)
  if window_ms is None or stride_ms is None:
    raise ValueError("--window-ms and --stride-ms must be provided together")
  return [(window_ms, stride_ms)]


def build_window_exports(
  db_path: Path,
  session_ids: Iterable[str],
  output_dir: Path = DEFAULT_OUTPUT_DIR,
  window_ms: int | None = None,
  stride_ms: int | None = None,
  overlap_threshold: float = 0.8,
  mixed_policy: str = "exclude",
  feature_set_version: str = "v0",
) -> list[WindowExport]:
  output_dir.mkdir(parents=True, exist_ok=True)
  exports: list[WindowExport] = []
  window_configs = resolve_window_configs(window_ms, stride_ms)

  with sqlite3.connect(db_path) as connection:
    for session_id in session_ids:
      samples = load_session_samples(connection, session_id)
      events = load_session_events(connection, session_id)
      for current_window_ms, current_stride_ms in window_configs:
        windows, features = build_windows_for_session(
          samples=samples,
          events=events,
          window_ms=current_window_ms,
          stride_ms=current_stride_ms,
          overlap_threshold=overlap_threshold,
          mixed_policy=mixed_policy,
          feature_set_version=feature_set_version,
        )
        filename_prefix = f"{safe_name(session_id)}_{current_window_ms}ms_{current_stride_ms}ms"
        windows_path = output_dir / f"{filename_prefix}_windows.csv"
        features_path = output_dir / f"{filename_prefix}_features.csv"
        windows.to_csv(windows_path, index=False)
        features.to_csv(features_path, index=False)
        exports.append(
          WindowExport(
            session_id=session_id,
            window_ms=current_window_ms,
            stride_ms=current_stride_ms,
            windows_path=windows_path,
            features_path=features_path,
            window_count=len(windows),
            feature_count=len(features),
          )
        )

  return exports


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Build sliding-window IMU datasets for model training.")
  parser.add_argument("--db-path", required=True, type=Path, help="Path to the SQLite database.")
  parser.add_argument(
    "--session-id",
    required=True,
    action="append",
    dest="session_ids",
    help="Session to export. Repeat for multiple sessions.",
  )
  parser.add_argument("--window-ms", type=int, help="Custom window size in device milliseconds.")
  parser.add_argument("--stride-ms", type=int, help="Custom stride in device milliseconds.")
  parser.add_argument("--overlap-threshold", type=float, default=0.8, help="Required label coverage for a hard class.")
  parser.add_argument(
    "--mixed-policy",
    choices=("exclude", "keep"),
    default="exclude",
    help="Whether mixed or boundary windows are excluded or retained as label=mixed.",
  )
  parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for CSV exports.")
  parser.add_argument("--feature-set-version", default="v0", help="Feature set version stamped into outputs.")
  return parser.parse_args()


def main() -> int:
  args = parse_args()
  exports = build_window_exports(
    db_path=args.db_path,
    session_ids=args.session_ids,
    output_dir=args.output_dir,
    window_ms=args.window_ms,
    stride_ms=args.stride_ms,
    overlap_threshold=args.overlap_threshold,
    mixed_policy=args.mixed_policy,
    feature_set_version=args.feature_set_version,
  )
  for export in exports:
    print(
      f"{export.session_id} {export.window_ms}ms/{export.stride_ms}ms: "
      f"{export.window_count} windows -> {export.windows_path}; "
      f"{export.feature_count} feature rows -> {export.features_path}"
    )
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
