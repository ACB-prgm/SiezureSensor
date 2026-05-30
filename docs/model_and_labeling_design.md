# Model and Labeling Design

## Purpose

The project should collect raw IMU data, let a human label meaningful time ranges, and later convert those labels into fixed-size examples for a categorical motion model.

The labeling workflow must fit the future model shape. Labels are stored as time spans, not individual sample annotations.

## Human Labels

Human labels are authoritative. They describe a period of time in a single session:

```text
session_id
event_type
severity
start_device_ms
end_device_ms
source
notes
```

`device_ms` is the source of truth. Server receive time is useful for diagnostics, but it should not be used to align samples and labels.

Initial event categories:

- `seizure`
- `sleep_twitch`
- `scratching`
- `scooting`
- `shake_off`
- `walking`
- `running`
- `resting`
- `unknown`

Unlabeled time is not normal by default. Normal activity should be labeled explicitly as `resting`, `walking`, or another category.

## Labeling Workbench

The local workbench should be the main way to label data.

Core workflow:

1. Select a session.
2. Inspect accel axes, gyro axes, accel magnitude, and gyro magnitude on a shared timeline.
3. Zoom and pan through the session.
4. Select a start and end point on the timeline.
5. Assign an event type, severity, and notes.
6. Save the label through the FastAPI event API.
7. Edit or delete incorrect labels.

The UI should overlay labels on the timeline so the user can review coverage and boundaries.

## Recommended Modeling Strategy

The first practical system should be a hierarchical, feature-based local pipeline:

- Human labels remain authoritative time spans.
- Raw IMU is converted into multi-scale windows.
- Engineered features are extracted from each window.
- A RandomForest is the day-one reference model.
- LightGBM or XGBoost should be evaluated on the same feature matrix next.
- Rules and temporal post-processing convert per-window probabilities into reviewable segments.
- Seizure-like activity is handled as a high-recall candidate-review track, not as a trusted medical alert.

This is more appropriate than starting with a raw deep model because early data will be small, imbalanced, and label-limited. Raw-window 1D CNN or TCN models become attractive later after the label ontology and dataset are stable.

## Sliding-Window Shape

The first model family should classify fixed-size windows cut from the continuous IMU stream.

Recommended starting settings:

- Sample rate: 50 Hz
- Primary activity window: 2 seconds / 100 samples
- Primary stride: 0.5 seconds / 25 samples
- Context window: 5 seconds / 250 samples
- Context stride: 1 second / 50 samples
- Optional aggregation horizon for seizure-like candidates: 9-10 seconds

Example:

```text
[0.0s - 2.0s] -> scratching
[1.0s - 3.0s] -> scratching
[2.0s - 4.0s] -> mixed
[3.0s - 5.0s] -> unlabeled
```

## Window Label Rules

Each generated window should be assigned a training label from overlap with human event windows.

Rules:

- If a window strongly overlaps exactly one label, assign that event type.
- The initial strong-overlap threshold should be 80 percent.
- If a window overlaps multiple incompatible labels, mark it `mixed` or exclude it from training.
- If a window has no human label, mark it `unlabeled`.
- Do not map `unlabeled` to `resting` or `normal`.
- Store `overlap_ratio` so label quality can be audited later.
- Keep all windows from the same labeled event in the same train/test partition.

Useful output columns:

```text
session_id
device_id
window_start_device_ms
window_end_device_ms
sample_count
label
label_source
overlap_ratio
```

## Baseline Model

The first model should be simple and debuggable before trying deep learning.

Recommended first pass:

- Generate labeled multi-scale windows.
- Extract engineered features per window.
- Train a RandomForest reference model.
- Compare LightGBM or XGBoost using the same feature table.
- Keep logistic regression or SVM as sanity-check baselines, not the primary model.
- Evaluate by holding out entire sessions, days, or dogs, not random rows.

Initial features:

- accel magnitude mean, standard deviation, min, max
- gyro magnitude mean, standard deviation, min, max
- per-axis mean and variance
- jerk-like changes between adjacent samples
- RMS, percentiles, signal energy, peak counts, and zero-crossing-style features
- simple frequency energy if useful

Raw-window models such as a 1D CNN can be evaluated later after enough labeled data exists.

## Hierarchical Heads

The first system should not be one flat classifier for everything.

Use two related heads:

- General activity head: predicts classes such as `resting`, `walking`, `running`, `scratching`, `scooting`, `shake_off`, and `sleep_twitch`.
- Rare-event candidate head: surfaces `seizure` or seizure-like windows for human review with high recall, class-specific thresholds, and conservative post-processing.

The rare-event head should optimize review usefulness, not autonomous alerting. It should use a stricter persistence rule, a cooldown period, and false-positives-per-hour reporting.

## Evaluation Protocol

Do not random-split windows. Overlapping windows are highly correlated and will leak information.

Recommended evaluation:

- If there is one dog, split by session or day with a purge gap around boundaries.
- If there are multiple dogs, use grouped splits by dog and report leave-one-dog-out or GroupKFold results.
- Keep all windows from the same event span in the same split.
- Report macro F1, per-class precision/recall/F1, and confusion matrix for activity classes.
- Report event sensitivity, false positives per hour, event precision, and detection latency for seizure-like candidates.
- Calibrate or at least inspect confidence before using prediction confidence in the UI.

## Prediction Review

Future model predictions should be stored separately from human labels.

Prediction records should include:

```text
model_version
session_id
window_start_device_ms
window_end_device_ms
predicted_label
confidence
review_status
reviewed_event_id
```

The workbench should eventually show predictions as a separate overlay track. The user should be able to accept, reject, or correct predictions. Accepted or corrected predictions can become human-reviewed labels, while the original prediction remains auditable.
