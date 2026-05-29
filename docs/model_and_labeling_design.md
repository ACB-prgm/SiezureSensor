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

## Sliding-Window Model Shape

The first model should be a sliding-window classifier. It will classify fixed-size windows cut from the continuous IMU stream.

Recommended starting settings:

- Sample rate: 50 Hz
- Window size A: 2 seconds / 100 samples
- Window size B: 5 seconds / 250 samples
- Stride: 50 percent overlap
- Prediction cadence: every 1 second for 2 second windows, or every 2.5 seconds for 5 second windows

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
- If a window overlaps multiple incompatible labels, mark it `mixed` or exclude it from training.
- If a window has no human label, mark it `unlabeled`.
- Do not map `unlabeled` to `resting` or `normal`.
- Store `overlap_ratio` so label quality can be audited later.

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

- Generate labeled sliding windows.
- Extract features per window.
- Train a RandomForest, gradient boosting model, or logistic regression classifier.
- Evaluate by holding out entire sessions, not random rows.

Initial features:

- accel magnitude mean, standard deviation, min, max
- gyro magnitude mean, standard deviation, min, max
- per-axis mean and variance
- jerk-like changes between adjacent samples
- simple frequency energy if useful

Raw-window models such as a 1D CNN can be evaluated later after enough labeled data exists.

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
