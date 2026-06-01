# Sprint 5 Dataset Prep

Sprint 5 turns reviewed session data into repeatable sliding-window datasets for the first local model experiments. Human labels remain stored as event time spans in the API database; window labels are derived only when exporting a training dataset.

## Build Window CSVs

Default export builds both planned scales:

- `2000 ms` windows with `500 ms` stride for the primary activity classifier.
- `5000 ms` windows with `1000 ms` stride for slower context features.

```bash
python analysis/scripts/build_windows.py \
  --db-path server/data/seizure_sensor.sqlite \
  --session-id 2026-05-30T14-30-12-beanie-v0-001-auto
```

Use a custom single window configuration when comparing model inputs:

```bash
python analysis/scripts/build_windows.py \
  --db-path server/data/seizure_sensor.sqlite \
  --session-id 2026-05-30T14-30-12-beanie-v0-001-auto \
  --window-ms 2000 \
  --stride-ms 500 \
  --mixed-policy keep \
  --output-dir data/exports
```

Each run writes two CSVs per session/window configuration:

- `{session_id}_{window_ms}ms_{stride_ms}ms_windows.csv` is the dataset manifest with timing, label, overlap, and event metadata.
- `{session_id}_{window_ms}ms_{stride_ms}ms_features.csv` adds engineered IMU features suitable for RandomForest, LightGBM, or XGBoost experiments.

## Label Derivation

The exporter uses human event spans from `events` and never changes the source labels.

- A window with no overlapping event is exported as `label=unlabeled`.
- A window covered by exactly one event class for at least `--overlap-threshold` is assigned that class with `label_source=human`.
- A boundary window or a window overlapping multiple classes becomes `mixed`.
- `mixed` windows are excluded by default; pass `--mixed-policy keep` to keep them for analysis.
- `unknown` is only used when a human explicitly labels a span as `unknown`; unlabeled time is not silently treated as normal/resting.

## Feature Set

Feature set `v0` computes summary statistics for `ax`, `ay`, `az`, `gx`, `gy`, `gz`, `accel_mag`, and `gyro_mag`:

- mean, standard deviation, min, max, median, p05, p95
- RMS and energy
- mean absolute sample-to-sample delta

The exported feature table keeps one row per window and includes the same label metadata as the manifest so the first model scripts can train directly from the CSV.
