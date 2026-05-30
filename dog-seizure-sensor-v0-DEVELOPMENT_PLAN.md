# Dog Seizure Sensor V0 — Codex Development Plan

## Project Objective

Build a V0 data acquisition system for a dog seizure sensor using:

- ESP8266 ESP-12F dev board
- GY-521 / MPU-6050 IMU
- Wi-Fi batch upload
- Python FastAPI ingestion server
- SQLite storage
- Manual event labeling through an interactive timeline workbench
- Dataset export for future algorithm development
- Sliding-window dataset preparation for future categorical motion models

V0 is not a seizure detector or medical alerting device. It is a reliable raw IMU data collection and labeling system that produces training-ready labeled time windows.

---

## High-Level Architecture

```text
MPU-6050
	↓ I2C
ESP8266 firmware
	↓ Wi-Fi HTTP POST
FastAPI server
	↓
SQLite database
	↓
React labeling workbench + analysis/export scripts
	↓
Future sliding-window categorical model
```

---

## Engineering Principles

1. Prioritize data reliability over battery life.
2. Store raw IMU data, not only derived features.
3. Use batch uploads, not one request per sample.
4. Preserve device-relative sample timing.
5. Include sequence numbers to detect gaps.
6. Keep firmware simple and deterministic.
7. Build server-side validation before algorithm work.
8. Design labels as time ranges so they can be converted into fixed-size sliding-window training examples.
9. Do not implement seizure detection or medical alerting in V0.

---

## Timing Model

V0 uses device-relative timing as the source of truth for IMU samples.

- Each upload batch includes `device_ms_start`, the device uptime in milliseconds for the first sample in the batch.
- Each sample includes `dt_ms`, the offset in milliseconds from `device_ms_start`.
- The server stores `device_ms = device_ms_start + dt_ms` for every sample.
- `server_received_at` is stored for ingestion diagnostics only and must not be treated as sample time.
- Manual event labels are tied to a specific `session_id` and use the same device-relative millisecond coordinate system via `start_device_ms` and `end_device_ms`.
- The labeling UI should create, edit, and delete time-range labels against this same device-relative coordinate system.
- Optional wall-clock fields may be added later, but V0 exports and plotting should join samples to labels using `session_id` and device-relative time overlap.

---

## Labeling and Model Design

The project should treat labeling as the bridge between raw IMU collection and future categorical modeling. The user-facing labeling tool should not label individual rows. It should label continuous spans of time, because the future model will operate on fixed-size windows cut from the continuous IMU stream.

### Human Labels

Human labels are authoritative training targets. They are stored as event windows:

```text
session_id
event_type
severity
start_device_ms
end_device_ms
source = manual
notes
```

The labeling workbench should support:

- selecting a session
- viewing accel axes, gyro axes, accel magnitude, and gyro magnitude on a shared timeline
- zooming and panning through long sessions
- click-dragging or entering start/end points for an event
- selecting an existing event type or creating an allowed new category
- editing and deleting existing labels
- overlaying labels on the timeline
- exporting labeled samples and windowed datasets

Initial label categories should include:

- `seizure`
- `sleep_twitch`
- `scratching`
- `scooting`
- `shake_off`
- `walking`
- `running`
- `resting`
- `unknown`

### Sliding-Window Dataset

The first practical model should be a hierarchical, feature-based sliding-window system. Raw IMU samples are converted into fixed-size windows, engineered features are extracted, and model outputs are smoothed into reviewable segments.

Recommended initial window settings:

- sample rate: 50 Hz
- primary activity window: 2 seconds / 100 samples
- primary stride: 0.5 seconds / 25 samples
- context window: 5 seconds / 250 samples
- context stride: 1 second / 50 samples
- optional seizure-like candidate aggregation horizon: 9-10 seconds

Each generated window should include:

```text
session_id
device_id
window_start_device_ms
window_end_device_ms
sample_count
label
label_source
overlap_ratio
ax/ay/az/gx/gy/gz samples or derived features
```

Window label assignment rules:

- If a window overlaps one human label by at least 80 percent, assign that event type.
- If a window overlaps multiple incompatible labels, mark it `mixed` or exclude it from training.
- If a window has no human label, keep it `unlabeled` unless the user explicitly labeled the period as `resting`, `walking`, or another normal activity.
- Do not treat unlabeled time as normal by default.
- Split train/test data by session, not by random rows, to reduce leakage.
- Keep all windows from the same labeled event in the same train/test partition.

### Model Path

The first model should be simple and debuggable:

1. Generate sliding windows from labeled sessions.
2. Extract per-window features such as accel magnitude mean/std/max, gyro magnitude mean/std/max, axis variance, jerk, RMS, percentiles, peak counts, and simple frequency-domain energy.
3. Train a RandomForest reference model.
4. Evaluate LightGBM or XGBoost on the same feature matrix.
5. Keep logistic regression and SVM as sanity-check baselines.
6. Compare against a later raw-window model such as a 1D CNN or TCN only after enough labeled data exists.
7. Smooth predictions over time before turning them into event spans.

Use two heads rather than one flat classifier:

- General activity head for `resting`, `walking`, `running`, `scratching`, `scooting`, `shake_off`, and `sleep_twitch`.
- Rare-event candidate head for `seizure` or seizure-like periods, optimized for high-recall human review and measured with false positives per hour.

Seizure-like output should be treated as candidate review support, not reliable medical alerting.

Future model predictions should be stored separately from human labels. A prediction record should include:

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

The workbench should eventually display model predictions as a separate overlay track and let the user accept, reject, or correct them. Accepted/corrected predictions can become human-reviewed labels, but raw model predictions should remain auditable and separate.

---

## Target Repo Structure

```text
dog-seizure-sensor/
	README.md
	.gitignore

	firmware/
		esp8266_mpu6050_logger/
			platformio.ini
			include/
				config.example.h
			src/
				main.cpp

	server/
		requirements.txt
		.env.example
		app/
			__init__.py
			main.py
			database.py
			models.py
			schemas.py
			routes/
				__init__.py
				health.py
				imu.py
				events.py
				export.py
		tests/
			test_health.py
			test_imu_upload.py
			test_events.py

	web/
		labeling_workbench/
			src/
			package.json

	analysis/
		scripts/
			export_session.py
			plot_session.py
			plot_event.py
			build_windows.py
		notebooks/
			01_inspect_raw_data.ipynb
			02_event_window_review.ipynb

	docs/
		hardware_wiring.md
		payload_schema.md
		v0_test_plan.md
		api_contract.md

	data/
		.gitkeep
```

---

## Data Contract

### Firmware Upload Endpoint

```http
POST /api/v1/imu/batch
Content-Type: application/json
```

### Request Body

```json
{
	"device_id": "beanie-v0-001",
	"firmware_version": "0.1.0",
	"session_id": "2026-05-23T20-15-00-beanie-v0-001",
	"sequence": 1234,
	"sample_hz": 50,
	"device_ms_start": 184240,
	"battery_mv": null,
	"samples": [
		{
			"dt_ms": 0,
			"ax": 0.02,
			"ay": -0.04,
			"az": 0.98,
			"gx": 1.2,
			"gy": -0.8,
			"gz": 0.4
		}
	]
}
```

### Successful Response

```json
{
	"status": "ok",
	"device_id": "beanie-v0-001",
	"sequence": 1234,
	"samples_received": 50
}
```

### Validation Rules

- `device_id` is required.
- `session_id` is required.
- `sequence` must be a non-negative integer.
- `sample_hz` must be greater than zero.
- `device_ms_start` must be a non-negative integer.
- `samples` must contain at least one sample.
- Each sample requires `dt_ms`, `ax`, `ay`, `az`, `gx`, `gy`, `gz`.
- `dt_ms` must be non-negative.
- Reject malformed payloads with a 422 or 400 response.

---

## Database Schema

Use SQLite for V0.

### `devices`

```sql
CREATE TABLE IF NOT EXISTS devices (
	device_id TEXT PRIMARY KEY,
	name TEXT,
	firmware_version TEXT,
	created_at TEXT NOT NULL,
	notes TEXT
);
```

### `sessions`

```sql
CREATE TABLE IF NOT EXISTS sessions (
	session_id TEXT PRIMARY KEY,
	device_id TEXT NOT NULL,
	started_at TEXT,
	ended_at TEXT,
	mount_location TEXT,
	notes TEXT,
	FOREIGN KEY (device_id) REFERENCES devices(device_id)
);
```

### `batches`

```sql
CREATE TABLE IF NOT EXISTS batches (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	device_id TEXT NOT NULL,
	session_id TEXT NOT NULL,
	sequence INTEGER NOT NULL,
	sample_hz INTEGER NOT NULL,
	device_ms_start INTEGER NOT NULL,
	server_received_at TEXT NOT NULL,
	sample_count INTEGER NOT NULL,
	battery_mv INTEGER,
	raw_payload_json TEXT NOT NULL,
	UNIQUE(device_id, session_id, sequence)
);
```

### `imu_samples`

```sql
CREATE TABLE IF NOT EXISTS imu_samples (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	device_id TEXT NOT NULL,
	session_id TEXT NOT NULL,
	batch_sequence INTEGER NOT NULL,
	sample_index INTEGER NOT NULL,
	device_ms INTEGER NOT NULL,
	server_received_at TEXT NOT NULL,
	ax REAL NOT NULL,
	ay REAL NOT NULL,
	az REAL NOT NULL,
	gx REAL NOT NULL,
	gy REAL NOT NULL,
	gz REAL NOT NULL
);
```

### `events`

```sql
CREATE TABLE IF NOT EXISTS events (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	session_id TEXT NOT NULL,
	event_type TEXT NOT NULL,
	severity INTEGER,
	start_device_ms INTEGER NOT NULL,
	end_device_ms INTEGER NOT NULL,
	source TEXT NOT NULL DEFAULT 'manual',
	notes TEXT,
	created_at TEXT NOT NULL,
	FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
```

---

# Milestones and Tasks

## M0 — Repository Bootstrap

### Task M0.1 — Create repo structure

Create the repo tree exactly as listed in "Target Repo Structure".

Acceptance criteria:

- Required folders exist.
- Required placeholder files exist.
- `data/` is present but actual data files are ignored by Git.

### Task M0.2 — Add root `.gitignore`

Include ignores for:

```text
.env
__pycache__/
*.pyc
.venv/
venv/
data/*
!data/.gitkeep
*.sqlite
*.db
.pio/
.DS_Store
.ipynb_checkpoints/
```

Acceptance criteria:

- Runtime files, databases, and private config files are ignored.
- `data/.gitkeep` remains trackable.

### Task M0.3 — Add README

README must include:

- Project objective
- Hardware list
- Architecture diagram
- Local development setup
- Firmware setup
- Server startup
- V0 limitations

Acceptance criteria:

- A developer can understand the project and run the server from README instructions.

---

## M1 — Server Skeleton

### Task M1.1 — Create FastAPI app

Implement:

```text
server/app/main.py
server/app/routes/health.py
```

Endpoint:

```http
GET /health
```

Response:

```json
{"status": "ok"}
```

Acceptance criteria:

- `uvicorn app.main:app --reload` starts successfully from `server/`.
- `GET /health` returns 200.

### Task M1.2 — Add Python dependencies

Create `server/requirements.txt` with at minimum:

```text
fastapi
uvicorn[standard]
pydantic
sqlalchemy
python-dotenv
pandas
matplotlib
pytest
httpx
```

Acceptance criteria:

- `pip install -r requirements.txt` works.
- Tests can import FastAPI app.

### Task M1.3 — Add health endpoint test

Create `server/tests/test_health.py`.

Acceptance criteria:

- `pytest` passes.
- Health endpoint returns `{"status": "ok"}`.

---

## M2 — Database Layer

### Task M2.1 — Implement SQLite database connection

Create:

```text
server/app/database.py
server/app/models.py
```

Use SQLAlchemy.

Requirements:

- DB path configurable via environment variable.
- Default DB path when running from `server/`: `../data/seizure_sensor_v0.sqlite`
- Database parent directories are created automatically if missing.
- Tables are created automatically during app startup.

Acceptance criteria:

- Starting the app creates the SQLite database.
- Tables exist after startup.

### Task M2.2 — Implement SQLAlchemy models

Create models for:

- Device
- Session
- Batch
- IMUSample
- Event

Acceptance criteria:

- Models match the schema in this plan.
- App startup creates all tables.
- No import cycles.

---

## M3 — IMU Batch Upload API

### Task M3.1 — Create Pydantic schemas

Create:

```text
server/app/schemas.py
```

Schemas:

- `IMUSampleIn`
- `IMUBatchIn`
- `IMUBatchAck`
- `EventIn` with `session_id`, `event_type`, `severity`, `start_device_ms`, `end_device_ms`, `source`, and `notes`
- `EventOut` with the same event fields plus `id` and `created_at`

Acceptance criteria:

- Invalid payloads are rejected by FastAPI validation.
- Valid sample payloads parse successfully.
- Event payloads use device-relative milliseconds, not wall-clock timestamps.

### Task M3.2 — Implement IMU upload route

Create:

```text
server/app/routes/imu.py
```

Endpoint:

```http
POST /api/v1/imu/batch
```

Behavior:

1. Validate request body.
2. Insert or update device record.
3. Insert session record if missing.
4. Insert batch metadata.
5. Insert all individual samples.
6. Store original JSON payload in `batches.raw_payload_json`.
7. Return `IMUBatchAck`.

Acceptance criteria:

- Valid payload writes one batch row.
- Valid payload writes N sample rows.
- Response includes acknowledged sequence.
- Duplicate `(device_id, session_id, sequence)` does not silently create duplicate samples.
- Batch metadata and samples are written atomically in one database transaction.
- A failed batch write must not leave partial sample rows.

Recommended duplicate behavior for V0:

- Return 409 Conflict for duplicate sequence.

### Task M3.3 — Add IMU upload tests

Create:

```text
server/tests/test_imu_upload.py
```

Test cases:

- Valid batch returns 200.
- Empty `samples` is rejected.
- Missing required fields rejected.
- Duplicate sequence returns 409.
- Stored sample count equals payload sample count.

Acceptance criteria:

- All tests pass with `pytest`.

---

## M4 — Manual Event Labeling API

### Task M4.1 — Implement event route

Create:

```text
server/app/routes/events.py
```

Endpoints:

```http
POST /api/v1/events
GET /api/v1/events
GET /api/v1/events/{event_id}
```

Event types allowed for V0:

- `seizure`
- `sleep_twitch`
- `scratching`
- `scooting`
- `shake_off`
- `walking`
- `running`
- `resting`
- `unknown`

Acceptance criteria:

- Manual labels can be created.
- Events can be listed.
- Event payloads include `session_id`, `start_device_ms`, and `end_device_ms`.
- Event start must be before event end.
- Severity can be null or integer 1–5.
- Event labels can be joined to samples by `session_id` and overlapping `device_ms`.

### Task M4.2 — Add event tests

Create:

```text
server/tests/test_events.py
```

Acceptance criteria:

- Valid event creation succeeds.
- Invalid event type rejected.
- End before start rejected.
- Event listing returns created events.

---

## M5 — Export API

### Task M5.1 — Implement sample export endpoint

Create:

```text
server/app/routes/export.py
```

Endpoint:

```http
GET /api/v1/export/samples
```

Query params:

- `session_id`, optional
- `start_device_ms`, optional integer
- `end_device_ms`, optional integer
- `format`, default `csv`, allowed `csv`

V0 may export CSV only.

Required exported columns:

```text
device_id
session_id
batch_sequence
sample_index
device_ms
server_received_at
ax
ay
az
gx
gy
gz
accel_mag
gyro_mag
```

Acceptance criteria:

- Export returns CSV.
- Derived magnitude columns are included.
- Filtering by session works.
- Filtering by device-relative millisecond range works.

### Task M5.2 — Add labeled export script

Create:

```text
analysis/scripts/export_session.py
```

Behavior:

- Reads SQLite DB.
- Exports samples for a session.
- Optionally joins event labels by overlap where `sample.session_id = event.session_id` and `sample.device_ms` is between `event.start_device_ms` and `event.end_device_ms`.
- Writes CSV to `data/exports/`.

Acceptance criteria:

- Script can export a session from the command line.
- Output opens correctly in pandas.

---

## M6 — Analysis Utilities

### Task M6.1 — Create session plotting script

Create:

```text
analysis/scripts/plot_session.py
```

Behavior:

- Accepts `--db-path` and `--session-id`.
- Loads IMU samples.
- Computes:
	- `accel_mag = sqrt(ax^2 + ay^2 + az^2)`
	- `gyro_mag = sqrt(gx^2 + gy^2 + gz^2)`
- Produces simple plots:
	- accel axes over time
	- gyro axes over time
	- accel magnitude over time
	- gyro magnitude over time

Acceptance criteria:

- Script runs against populated DB.
- Script saves plots to `data/plots/`.

### Task M6.2 — Create event plotting script

Create:

```text
analysis/scripts/plot_event.py
```

Behavior:

- Accepts `--event-id`.
- Loads event window.
- Adds configurable padding before/after event.
- Plots samples around event.

Acceptance criteria:

- Script plots event-centered window.
- Output saved to `data/plots/`.

---

## M7 — Firmware Bench Read

### Task M7.1 — Create PlatformIO project

Create:

```text
firmware/esp8266_mpu6050_logger/platformio.ini
firmware/esp8266_mpu6050_logger/src/main.cpp
firmware/esp8266_mpu6050_logger/include/config.example.h
```

Target board should be appropriate for generic ESP8266 / ESP-12E / NodeMCU-style development.

Acceptance criteria:

- PlatformIO project builds.
- Config example documents Wi-Fi SSID, password, server URL, device ID.

### Task M7.2 — Implement I2C scanner mode

Add temporary or compile-time debug mode to scan I2C bus.

Expected sensor address:

```text
0x68
```

Acceptance criteria:

- Serial monitor prints detected I2C device address.
- MPU-6050 appears at `0x68`.

### Task M7.3 — Read MPU-6050 data

Implement:

- MPU initialization
- accel read
- gyro read
- serial print at approximately 50 Hz

Acceptance criteria:

- Serial output shows changing accel/gyro values.
- Still sensor has acceleration magnitude near 1 g.
- Motion causes visible changes.

---

## M8 — Firmware Batch Upload

### Task M8.1 — Implement Wi-Fi connection

Firmware must:

- Connect to Wi-Fi.
- Print local IP.
- Reconnect if disconnected.

Acceptance criteria:

- Device joins Wi-Fi reliably.
- Reconnect logic does not block permanently.

### Task M8.2 — Implement sample batching

Requirements:

- Sample at 50 Hz.
- Batch 50 samples per upload.
- Each sample includes:
	- `dt_ms`
	- `ax`, `ay`, `az`
	- `gx`, `gy`, `gz`
- Each batch includes:
	- `device_id`
	- `firmware_version`
	- `session_id`
	- `sequence`
	- `sample_hz`
	- `device_ms_start`
	- `battery_mv`

Acceptance criteria:

- Serial monitor shows batches being prepared once per second.
- Sequence number increments monotonically.

### Task M8.3 — Implement HTTP POST upload

Firmware posts JSON to:

```text
{SERVER_URL}/api/v1/imu/batch
```

Acceptance criteria:

- Server receives real sensor batches.
- Server response is printed over serial.
- Failed upload does not crash firmware.
- Device continues attempting future uploads.

### Task M8.4 — Long-run firmware test

Run device for 30 minutes.

Acceptance criteria:

- No firmware crash.
- Server receives roughly 90,000 samples at 50 Hz for 30 minutes.
- Missing sequence numbers are identifiable.
- Memory leak is not obvious from runtime behavior.

---

## M9 — Interactive Labeling Workbench

### Task M9.1 — Create local web workbench

Create:

```text
web/labeling_workbench/
```

Behavior:

- Runs locally against the FastAPI server.
- Lists available sessions.
- Loads one session at a time.
- Displays accel axes, gyro axes, accel magnitude, and gyro magnitude on a shared timeline.
- Supports zooming and panning.

Acceptance criteria:

- User can choose a session and inspect its IMU timeline without running analysis scripts manually.
- Workbench can handle at least a 15-minute session without becoming unusable.

### Task M9.2 — Add session and event API support for workbench

Create or expand endpoints as needed:

```http
GET /api/v1/sessions
GET /api/v1/sessions/{session_id}/samples
DELETE /api/v1/events/{event_id}
PATCH /api/v1/events/{event_id}
```

Behavior:

- Session list returns enough metadata to choose a recording.
- Sample endpoint returns downsampled or range-filtered data suitable for timeline rendering.
- Event update/delete endpoints allow correcting labels from the UI.

Acceptance criteria:

- Workbench does not need to read SQLite directly.
- Event edits remain validated by the server.
- Large sessions can be inspected by fetching ranges or downsampled timeline data.

### Task M9.3 — Implement timeline event labeling

Behavior:

- User can select start and end points on the timeline.
- User can assign an event type, severity, source, and notes.
- User can choose an existing category or create/select from the allowed category list.
- Existing labels render as overlays on the timeline.
- Labels are saved through the existing event API.

Acceptance criteria:

- User can create a label without manually typing device milliseconds.
- User can edit and delete mistaken labels.
- Saved labels use `session_id`, `start_device_ms`, and `end_device_ms`.
- Label overlays align visually with the signal timeline.

---

## M10 — Sliding-Window Dataset Preparation

### Task M10.1 — Add window generation script

Create:

```text
analysis/scripts/build_windows.py
```

Behavior:

- Reads one or more labeled sessions from SQLite.
- Generates fixed-size sliding windows from raw IMU samples.
- Supports configurable `--window-ms` and `--stride-ms`.
- Assigns each window a label using overlap with human event windows.
- Writes a dataset manifest and features/arrays under `data/exports/`.

Acceptance criteria:

- Script can generate 2 second / 100 sample windows for 50 Hz data.
- Script can generate 5 second / 250 sample windows for 50 Hz data.
- Unlabeled windows remain `unlabeled`, not automatically `resting` or `normal`.
- Mixed-overlap windows are marked `mixed` or excluded by a documented option.
- Output includes `session_id`, `device_id`, `window_start_device_ms`, `window_end_device_ms`, `label`, and `overlap_ratio`.

### Task M10.2 — Add baseline feature extraction

Behavior:

- Computes simple per-window features for accel and gyro channels.
- Includes accel magnitude and gyro magnitude summary statistics.
- Includes variance and jerk-style features where practical.

Acceptance criteria:

- Feature output is reproducible from the raw SQLite database.
- Feature columns are documented.
- Generated feature CSV opens in pandas.

### Task M10.3 — Document model design

Create:

```text
docs/model_and_labeling_design.md
```

Include:

- human label semantics
- sliding-window settings
- overlap label assignment rules
- train/test split guidance
- future prediction review workflow

Acceptance criteria:

- Labeling decisions are clearly connected to future model training.
- The document explains why unlabeled time is not treated as normal by default.

---

## M11 — Data Quality Validation

### Task M11.1 — Create synthetic activity test checklist

Create:

```text
docs/v0_test_plan.md
```

Include tests:

- still on table
- rotate sensor by hand
- shake sensor gently
- shake sensor aggressively
- attach to collar/harness and walk
- dog resting
- dog scratching
- dog scooting if safely observable
- dog shaking off

Acceptance criteria:

- Each test has expected signal characteristics.
- Each test has pass/fail notes section.

### Task M11.2 — Collect first baseline session

Use the real device and real server.

Acceptance criteria:

- At least 15 minutes of continuous data.
- Session can be plotted and inspected in the labeling workbench.
- Sequence gaps are documented.
- Accel and gyro magnitudes are plausible.
- At least a few known periods are labeled through the workbench.

---

## M12 — Documentation

### Task M12.1 — Hardware wiring documentation

Create:

```text
docs/hardware_wiring.md
```

Include:

| MPU-6050 | ESP8266 |
|---|---|
| VCC | 3V3 |
| GND | GND |
| SCL | D1 / GPIO5 |
| SDA | D2 / GPIO4 |
| INT | unused |
| AD0 | GND/floating for 0x68 |

Acceptance criteria:

- Wiring is clear enough to rebuild from scratch.
- Notes mention shared 3.3 V supply and shared ground.

### Task M12.2 — API contract documentation

Create:

```text
docs/api_contract.md
```

Include:

- endpoint list
- request payload examples
- response examples
- validation rules
- duplicate sequence behavior
- workbench-oriented session/sample/event endpoints

Acceptance criteria:

- A firmware developer can implement against the API without reading server code.

### Task M12.3 — Payload schema documentation

Create:

```text
docs/payload_schema.md
```

Include:

- field definitions
- units
- sample timing model
- sequence number purpose

Acceptance criteria:

- Data semantics are clear.

---

# Codex Implementation Guidance

Use this plan as the source of truth. Work milestone-by-milestone. Do not jump ahead to ML, BLE, battery optimization, alerting, or on-device detection.
The labeling workbench and sliding-window dataset preparation are not ML model training; they are required data infrastructure for future modeling.

When implementing code:

- Prefer small, testable commits.
- Add tests for each server endpoint.
- Keep firmware config out of source control.
- Avoid committing real sensor data.
- Keep the API stable once firmware upload is implemented.
- Preserve raw payloads for debugging.
- Use explicit units in variable names when practical.

---

## Suggested Codex Prompt for Initial Repo Build

```text
You are implementing V0 of a dog seizure sensor data acquisition system.

Use the DEVELOPMENT_PLAN.md file as the source of truth.

Start with milestones M0 through M3 only:
- create the repository structure
- add README and .gitignore
- build the FastAPI server skeleton
- add SQLite database models
- implement POST /api/v1/imu/batch
- add pytest coverage for health and IMU upload

Do not implement firmware yet.
Do not implement seizure detection or ML.
Do not implement model training yet.
Do not optimize battery life.
Keep the code simple, typed, and testable.
After implementation, summarize changed files and how to run tests.
```

---

## Suggested Codex Prompt for Firmware Build

```text
Continue implementing V0 of the dog seizure sensor data acquisition system.

Use DEVELOPMENT_PLAN.md as the source of truth.

Implement milestones M7 and M8:
- PlatformIO ESP8266 project
- config.example.h
- MPU-6050 I2C scanner/debug mode
- 50 Hz accel/gyro sampling
- 50-sample batching
- HTTP POST upload to /api/v1/imu/batch
- serial debug output
- reconnect handling

Do not implement BLE.
Do not implement seizure detection.
Do not optimize battery life yet.
After implementation, summarize changed files, firmware configuration steps, and bench test procedure.
```

---

## Suggested Codex Prompt for Analysis Tools

```text
Continue implementing V0 of the dog seizure sensor data acquisition system.

Use DEVELOPMENT_PLAN.md as the source of truth.

Implement milestones M5 and M6:
- CSV export endpoint
- session export script
- session plotting script
- event plotting script
- derived accel_mag and gyro_mag columns
- basic documentation for running analysis scripts

Do not implement ML model training yet.
Do not implement alerting.
After implementation, summarize changed files and example commands.
```

---

## Suggested Codex Prompt for Labeling Workbench

```text
Continue implementing V0 of the dog seizure sensor data acquisition system.

Use DEVELOPMENT_PLAN.md as the source of truth.

Implement milestone M9:
- local labeling workbench
- session list and session sample endpoints
- timeline chart for accel/gyro/magnitude
- event overlays
- create, edit, and delete labels from selected timeline ranges

Do not implement model training yet.
Do not implement medical alerting.
Keep labels stored as session_id plus device-relative start/end milliseconds.
After implementation, summarize changed files and how to run the server and workbench.
```

---

## Suggested Codex Prompt for Windowed Dataset Prep

```text
Continue implementing V0 of the dog seizure sensor data acquisition system.

Use DEVELOPMENT_PLAN.md as the source of truth.

Implement milestone M10:
- sliding-window dataset generation
- configurable window and stride
- overlap-based label assignment
- baseline feature extraction
- documentation of dataset semantics

Do not implement production seizure detection.
Do not treat unlabeled time as normal.
Split evaluation data by session, not random rows.
After implementation, summarize generated outputs and verification commands.
```

---

# V0 Definition of Done

V0 is complete when:

1. ESP8266 reads MPU-6050 at 50 Hz.
2. Device uploads batched IMU samples to local FastAPI server.
3. Server stores raw samples in SQLite.
4. Duplicate batch sequences are handled explicitly.
5. Manual event labels can be created.
6. Samples can be exported as CSV.
7. Session and event windows can be plotted.
8. Labels can be created, edited, and deleted from an interactive timeline workbench.
9. Sliding-window datasets can be generated from human-labeled time ranges.
10. At least one 15-minute baseline session is collected and reviewed.
11. Documentation exists for wiring, API, payload schema, labeling workflow, model design, and test procedure.
12. No seizure detection or medical alerting logic is implemented in V0.
