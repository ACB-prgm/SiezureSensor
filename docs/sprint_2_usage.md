# Sprint 2 Usage

Sprint 2 adds manual labels, CSV export, labeled session export, and PNG plotting.

## Event Labels

Events are tied to an existing `session_id` and use device-relative milliseconds.

```http
POST /api/v1/events
GET /api/v1/events
GET /api/v1/events/{event_id}
```

Allowed event types:

- `seizure`
- `sleep_twitch`
- `scratching`
- `scooting`
- `shake_off`
- `walking`
- `running`
- `resting`
- `unknown`

Example:

```sh
curl -X POST http://127.0.0.1:8000/api/v1/events \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id": "example-session",
    "event_type": "walking",
    "severity": 1,
    "start_device_ms": 1000,
    "end_device_ms": 5000,
    "source": "manual",
    "notes": "walk test"
  }'
```

## CSV Export API

```http
GET /api/v1/export/samples
```

Query params:

- `session_id`, optional
- `start_device_ms`, optional
- `end_device_ms`, optional
- `format`, optional, must be `csv`

Example:

```sh
curl 'http://127.0.0.1:8000/api/v1/export/samples?session_id=example-session' \
  -o data/exports/example-session.csv
```

CSV output includes raw IMU columns plus `accel_mag` and `gyro_mag`.

## Labeled Session Export

```sh
python analysis/scripts/export_session.py \
  --db-path data/seizure_sensor_v0.sqlite \
  --session-id example-session \
  --include-labels
```

Label joins use `session_id` and `device_ms` overlap. If multiple events overlap a sample, the first event ordered by `start_device_ms` then `id` is used.

## Plotting

Session plot:

```sh
python analysis/scripts/plot_session.py \
  --db-path data/seizure_sensor_v0.sqlite \
  --session-id example-session
```

Event plot:

```sh
python analysis/scripts/plot_event.py \
  --db-path data/seizure_sensor_v0.sqlite \
  --event-id 1 \
  --padding-ms 5000
```

Plot outputs are PNG files under `data/plots/` by default.
