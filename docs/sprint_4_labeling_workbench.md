# Sprint 4 Labeling Workbench

Sprint 4 adds a local React workbench for visually labeling IMU sessions. Labels remain server-side event records tied to `session_id`, `start_device_ms`, and `end_device_ms`.

## Run

Start FastAPI:

```sh
cd server
. .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Start the workbench:

```sh
cd web/labeling_workbench
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

If the API runs elsewhere, create `web/labeling_workbench/.env`:

```sh
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Workflow

1. Select a session from the left panel.
2. Inspect accel axes, gyro axes, accel magnitude, and gyro magnitude.
3. Use the mouse wheel to zoom and drag the timeline to pan.
4. Click `Select range`.
5. Drag across the timeline to choose start and end device milliseconds.
6. Pick an event type, optional severity, source, and notes.
7. Click `Create label`.
8. Use the label list to edit or delete mistakes.

The UI displays readable timing, but all saved labels use device-relative milliseconds.

## API Endpoints

Workbench session endpoints:

```http
GET /api/v1/sessions
GET /api/v1/sessions/{session_id}/samples?start_device_ms=0&end_device_ms=10000&max_points=2000
```

Event endpoints:

```http
POST /api/v1/events
GET /api/v1/events?session_id={session_id}
GET /api/v1/events/{event_id}
PATCH /api/v1/events/{event_id}
DELETE /api/v1/events/{event_id}
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

## Verification

Run:

```sh
cd server
.venv/bin/python -m pytest

cd ../web/labeling_workbench
npm run build
```

Manual check:

1. Start the server and workbench.
2. Open a session with samples.
3. Create a short test label.
4. Edit the label timing or event type.
5. Delete the test label.
6. Confirm the label list and event API reflect each action.
