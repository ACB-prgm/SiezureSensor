import { useEffect, useRef, useState } from "react";

import {
  API_BASE_URL,
  createEvent,
  createSession,
  deleteEvent,
  getApiControlStatus,
  getApiRuntimeStatus,
  listEvents,
  listSessionSamples,
  listSessions,
  startApiService,
  stopApiService,
  updateEvent,
} from "./api";
import Timeline from "./Timeline";
import {
  EVENT_TYPES,
  type ApiControlStatus,
  type ApiRuntimeStatus,
  type EventLabel,
  type EventPayload,
  type EventType,
  type SelectionRange,
  type SessionCreatePayload,
  type SessionSample,
  type SessionSummary,
  type ViewRange,
} from "./types";

type LabelFormState = {
  eventType: EventType;
  severity: string;
  notes: string;
};

const DEFAULT_FORM: LabelFormState = {
  eventType: "scratching",
  severity: "",
  notes: "",
};

type SessionFormState = {
  sessionId: string;
  deviceId: string;
  mountLocation: string;
  notes: string;
};

const DEFAULT_SESSION_FORM: SessionFormState = {
  sessionId: "",
  deviceId: "beanie-v0-001",
  mountLocation: "",
  notes: "",
};

function formatDuration(session: SessionSummary): string {
  if (session.min_device_ms === null || session.max_device_ms === null) {
    return "No samples";
  }
  const seconds = Math.max(0, session.max_device_ms - session.min_device_ms) / 1000;
  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`;
  }
  return `${(seconds / 60).toFixed(1)}m`;
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "Not recorded";
  }
  return new Date(value).toLocaleString();
}

function formatAge(value: string | null): string {
  if (!value) {
    return "never";
  }
  const elapsedMs = Date.now() - new Date(value).getTime();
  if (!Number.isFinite(elapsedMs) || elapsedMs < 0) {
    return "just now";
  }
  const seconds = Math.round(elapsedMs / 1000);
  if (seconds < 60) {
    return `${seconds}s ago`;
  }
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) {
    return `${minutes}m ago`;
  }
  const hours = Math.round(minutes / 60);
  return `${hours}h ago`;
}

function isActivelyReceiving(value: string | null): boolean {
  if (!value) {
    return false;
  }
  return Date.now() - new Date(value).getTime() < 15_000;
}

function dateForDeviceMs(samples: SessionSample[], deviceMs: number): Date | null {
  if (samples.length === 0) {
    return null;
  }
  let nearest = samples[0];
  let nearestDistance = Math.abs(nearest.device_ms - deviceMs);
  for (const sample of samples) {
    const distance = Math.abs(sample.device_ms - deviceMs);
    if (distance < nearestDistance) {
      nearest = sample;
      nearestDistance = distance;
    }
  }
  return new Date(nearest.server_received_at);
}

function deviceMsForDate(samples: SessionSample[], targetDate: Date): number | null {
  if (samples.length === 0) {
    return null;
  }
  let nearest = samples[0];
  let nearestDistance = Math.abs(new Date(nearest.server_received_at).getTime() - targetDate.getTime());
  for (const sample of samples) {
    const distance = Math.abs(new Date(sample.server_received_at).getTime() - targetDate.getTime());
    if (distance < nearestDistance) {
      nearest = sample;
      nearestDistance = distance;
    }
  }
  return nearest.device_ms;
}

function rangeAroundLabel(label: EventLabel): ViewRange {
  const labelSpan = label.end_device_ms - label.start_device_ms;
  const viewSpan = Math.max(10_000, labelSpan * 5);
  const midpoint = (label.start_device_ms + label.end_device_ms) / 2;
  return {
    startDeviceMs: Math.max(0, Math.round(midpoint - viewSpan / 2)),
    endDeviceMs: Math.round(midpoint + viewSpan / 2),
  };
}

function timePart(value: Date | null, part: "hours" | "minutes" | "seconds"): string {
  if (!value) {
    return "";
  }
  const number = part === "hours" ? value.getHours() : part === "minutes" ? value.getMinutes() : value.getSeconds();
  return String(number).padStart(2, "0");
}

function App() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [samples, setSamples] = useState<SessionSample[]>([]);
  const [labels, setLabels] = useState<EventLabel[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [timelineError, setTimelineError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isTimelineLoading, setIsTimelineLoading] = useState(false);
  const [isSelectionMode, setIsSelectionMode] = useState(false);
  const [apiControlStatus, setApiControlStatus] = useState<ApiControlStatus | null>(null);
  const [apiRuntimeStatus, setApiRuntimeStatus] = useState<ApiRuntimeStatus | null>(null);
  const [apiStatusMessage, setApiStatusMessage] = useState<string | null>(null);
  const [isApiStatusLoading, setIsApiStatusLoading] = useState(false);
  const [isApiActionRunning, setIsApiActionRunning] = useState(false);
  const [isApiControlAvailable, setIsApiControlAvailable] = useState(true);
  const [selectedRange, setSelectedRange] = useState<SelectionRange | null>(null);
  const [focusRange, setFocusRange] = useState<ViewRange | null>(null);
  const [editingLabel, setEditingLabel] = useState<EventLabel | null>(null);
  const [form, setForm] = useState<LabelFormState>(DEFAULT_FORM);
  const [sessionForm, setSessionForm] = useState<SessionFormState>(DEFAULT_SESSION_FORM);
  const lastRuntimeSampleCountRef = useRef<number | null>(null);
  const selectedSessionIdRef = useRef<string | null>(null);

  async function loadSessions(showLoading = true) {
    try {
      if (showLoading) {
        setIsLoading(true);
      }
      const result = await listSessions();
      setSessions(result);
      setSelectedSessionId((current) => current ?? result[0]?.session_id ?? null);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to load sessions");
    } finally {
      if (showLoading) {
        setIsLoading(false);
      }
    }
  }

  async function loadTimeline(sessionId: string, showLoading = true) {
    try {
      if (showLoading) {
        setIsTimelineLoading(true);
      }
      const [nextSamples, nextLabels] = await Promise.all([
        listSessionSamples(sessionId, 20000),
        listEvents(sessionId),
      ]);
      setSamples(nextSamples);
      setLabels(nextLabels);
      setTimelineError(null);
    } catch (caught) {
      setTimelineError(caught instanceof Error ? caught.message : "Failed to load timeline");
    } finally {
      if (showLoading) {
        setIsTimelineLoading(false);
      }
    }
  }

  async function refreshApiStatus() {
    try {
      setIsApiStatusLoading(true);
      const controlStatus = await getApiControlStatus();
      setApiControlStatus(controlStatus);
      setIsApiControlAvailable(true);
      setApiStatusMessage(controlStatus.message);

      if (controlStatus.apiReachable) {
        const runtimeStatus = await getApiRuntimeStatus();
        setApiRuntimeStatus(runtimeStatus);
        if (runtimeStatus.sample_count !== lastRuntimeSampleCountRef.current) {
          lastRuntimeSampleCountRef.current = runtimeStatus.sample_count;
          await loadSessions(false);
          if (selectedSessionIdRef.current) {
            await loadTimeline(selectedSessionIdRef.current, false);
          }
        }
      } else {
        setApiRuntimeStatus(null);
      }
    } catch (caught) {
      setIsApiControlAvailable(false);
      setApiControlStatus(null);
      try {
        setApiRuntimeStatus(await getApiRuntimeStatus());
        setApiStatusMessage("FastAPI is reachable. Dashboard start/stop controls are unavailable in this build.");
      } catch {
        setApiRuntimeStatus(null);
        setApiStatusMessage(caught instanceof Error ? caught.message : "Failed to check API status");
      }
    } finally {
      setIsApiStatusLoading(false);
    }
  }

  useEffect(() => {
    void loadSessions();
  }, []);

  useEffect(() => {
    selectedSessionIdRef.current = selectedSessionId;
  }, [selectedSessionId]);

  useEffect(() => {
    void refreshApiStatus();
    const interval = window.setInterval(() => {
      void refreshApiStatus();
    }, 5000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    const sessionId: string = selectedSessionId ?? "";
    if (!sessionId) {
      setSamples([]);
      setLabels([]);
      return;
    }

    void loadTimeline(sessionId);
  }, [selectedSessionId]);

  const selectedSession = sessions.find((session) => session.session_id === selectedSessionId) ?? null;
  const selectedLabelId = editingLabel?.id ?? null;
  const selectedStartDate = selectedRange ? dateForDeviceMs(samples, selectedRange.startDeviceMs) : null;
  const selectedEndDate = selectedRange ? dateForDeviceMs(samples, selectedRange.endDeviceMs) : null;
  const latestSampleReceivedAt = apiRuntimeStatus?.latest_sample_received_at ?? null;
  const isApiReachable = apiControlStatus?.apiReachable ?? apiRuntimeStatus?.status === "ok";
  const isRecording = isActivelyReceiving(latestSampleReceivedAt);
  const apiStatusClass = isRecording ? "recording" : isApiReachable ? "online" : "offline";

  async function refreshLabels(sessionId: string) {
    setLabels(await listEvents(sessionId));
  }

  function clearForm() {
    setEditingLabel(null);
    setSelectedRange(null);
    setFocusRange(null);
    setForm(DEFAULT_FORM);
    setActionMessage(null);
  }

  function editLabel(label: EventLabel) {
    setEditingLabel(label);
    setSelectedRange({ startDeviceMs: label.start_device_ms, endDeviceMs: label.end_device_ms });
    setFocusRange(rangeAroundLabel(label));
    setForm({
      eventType: label.event_type,
      severity: label.severity === null ? "" : String(label.severity),
      notes: label.notes ?? "",
    });
    setActionMessage(null);
  }

  function hasOverlap(range: SelectionRange, excludeEventId: number | null): boolean {
    return labels.some((label) => {
      if (excludeEventId !== null && label.id === excludeEventId) {
        return false;
      }
      return label.start_device_ms < range.endDeviceMs && label.end_device_ms > range.startDeviceMs;
    });
  }

  function buildPayload(sessionId: string): EventPayload | null {
    if (!selectedRange || selectedRange.endDeviceMs <= selectedRange.startDeviceMs) {
      setActionMessage("Select a non-empty range on the timeline before saving.");
      return null;
    }
    if (hasOverlap(selectedRange, editingLabel?.id ?? null)) {
      setActionMessage("Selected range overlaps an existing label. Adjust the start or end before saving.");
      return null;
    }

    return {
      session_id: sessionId,
      event_type: form.eventType,
      severity: form.severity === "" ? null : Number(form.severity),
      start_device_ms: selectedRange.startDeviceMs,
      end_device_ms: selectedRange.endDeviceMs,
      source: "manual",
      notes: form.notes.trim() === "" ? null : form.notes.trim(),
    };
  }

  async function saveLabel() {
    if (!selectedSessionId) {
      return;
    }
    const payload = buildPayload(selectedSessionId);
    if (!payload) {
      return;
    }

    try {
      if (editingLabel) {
        await updateEvent(editingLabel.id, payload);
        setActionMessage("Label updated.");
      } else {
        await createEvent(payload);
        setActionMessage("Label created.");
      }
      await refreshLabels(selectedSessionId);
      setEditingLabel(null);
    } catch (caught) {
      setActionMessage(caught instanceof Error ? caught.message : "Failed to save label");
    }
  }

  async function removeLabel(label: EventLabel) {
    if (!selectedSessionId) {
      return;
    }
    try {
      await deleteEvent(label.id);
      await refreshLabels(selectedSessionId);
      if (editingLabel?.id === label.id) {
        clearForm();
      }
      setActionMessage("Label deleted.");
    } catch (caught) {
      setActionMessage(caught instanceof Error ? caught.message : "Failed to delete label");
    }
  }

  function updateRangeTime(boundary: "start" | "end", part: "hours" | "minutes" | "seconds", rawValue: string) {
    if (!selectedRange) {
      return;
    }
    const numericValue = Number(rawValue);
    if (!Number.isFinite(numericValue)) {
      return;
    }
    const currentDate = dateForDeviceMs(samples, boundary === "start" ? selectedRange.startDeviceMs : selectedRange.endDeviceMs);
    if (!currentDate) {
      return;
    }
    const nextDate = new Date(currentDate);
    if (part === "hours") {
      nextDate.setHours(Math.min(23, Math.max(0, numericValue)));
    } else if (part === "minutes") {
      nextDate.setMinutes(Math.min(59, Math.max(0, numericValue)));
    } else {
      nextDate.setSeconds(Math.min(59, Math.max(0, numericValue)));
    }
    const nextDeviceMs = deviceMsForDate(samples, nextDate);
    if (nextDeviceMs === null) {
      return;
    }
    setSelectedRange((current) => {
      if (!current) {
        return current;
      }
      if (boundary === "start") {
        return { ...current, startDeviceMs: Math.min(nextDeviceMs, current.endDeviceMs - 1) };
      }
      return { ...current, endDeviceMs: Math.max(nextDeviceMs, current.startDeviceMs + 1) };
    });
  }

  async function saveSession() {
    const payload: SessionCreatePayload = {
      session_id: sessionForm.sessionId.trim(),
      device_id: sessionForm.deviceId.trim(),
      mount_location: sessionForm.mountLocation.trim() || null,
      notes: sessionForm.notes.trim() || null,
    };
    if (!payload.session_id || !payload.device_id) {
      setError("Session ID and device ID are required.");
      return;
    }

    try {
      const created = await createSession(payload);
      const nextSessions = await listSessions();
      setSessions(nextSessions);
      setSelectedSessionId(created.session_id);
      setSessionForm(DEFAULT_SESSION_FORM);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to create session");
    }
  }

  async function startApi() {
    try {
      setIsApiActionRunning(true);
      const status = await startApiService();
      setApiControlStatus(status);
      setApiStatusMessage(status.message);
      await refreshApiStatus();
      if (status.apiReachable) {
        await loadSessions();
      }
    } catch (caught) {
      setApiStatusMessage(caught instanceof Error ? caught.message : "Failed to start FastAPI");
    } finally {
      setIsApiActionRunning(false);
    }
  }

  async function stopApi() {
    try {
      setIsApiActionRunning(true);
      const status = await stopApiService();
      setApiControlStatus(status);
      setApiStatusMessage(status.message);
      await refreshApiStatus();
    } catch (caught) {
      setApiStatusMessage(caught instanceof Error ? caught.message : "Failed to stop FastAPI");
    } finally {
      setIsApiActionRunning(false);
    }
  }

  return (
    <main className="app-shell">
      <section className="hero-panel">
        <div>
          <p className="section-label">Local labeling workbench</p>
          <h1>Turn raw collar motion into training labels.</h1>
          <p className="hero-copy">
            Select a real ESP session, inspect the IMU timeline, and mark device-relative event windows for the
            future activity model.
          </p>
        </div>
        <div className={`status-card api-status-card ${apiStatusClass}`}>
          <div className="status-card-heading">
            <span>API</span>
            <span className="status-pill">
              {isRecording ? "Recording" : isApiReachable ? "Online" : isApiStatusLoading ? "Checking" : "Offline"}
            </span>
          </div>
          <strong>{API_BASE_URL}</strong>
          <p>{apiStatusMessage ?? "Checking FastAPI status."}</p>
          <dl>
            <div>
              <dt>Latest Sample</dt>
              <dd>{formatAge(latestSampleReceivedAt)}</dd>
            </div>
            <div>
              <dt>Samples</dt>
              <dd>{apiRuntimeStatus ? apiRuntimeStatus.sample_count.toLocaleString() : "n/a"}</dd>
            </div>
          </dl>
          <div className="api-control-actions">
            <button disabled={!isApiControlAvailable || isApiActionRunning || isApiReachable} onClick={() => void startApi()} type="button">
              Start API
            </button>
            <button
              disabled={!isApiControlAvailable || isApiActionRunning || !apiControlStatus?.managed}
              onClick={() => void stopApi()}
              type="button"
            >
              Stop API
            </button>
            <button disabled={isApiStatusLoading || isApiActionRunning} onClick={() => void refreshApiStatus()} type="button">
              Refresh
            </button>
          </div>
        </div>
      </section>

      <section className="workspace-grid">
        <aside className="session-panel">
          <div className="panel-heading">
            <h2>Sessions</h2>
            <span>{isLoading ? "Loading" : `${sessions.length} found`}</span>
          </div>

          {error ? <p className="error-message">{error}</p> : null}

          <div className="session-list">
            {sessions.map((session) => (
              <button
                className={session.session_id === selectedSessionId ? "session-row selected" : "session-row"}
                key={session.session_id}
                onClick={() => setSelectedSessionId(session.session_id)}
                type="button"
              >
                <span className="session-id">{session.session_id}</span>
                <span className="session-meta">
                  {session.sample_count.toLocaleString()} samples · {formatDuration(session)}
                </span>
              </button>
            ))}
          </div>

          <div className="new-session-panel">
            <h2>New Session</h2>
            <label>
              Session ID
              <input
                placeholder="2026-05-30-beanie-test"
                value={sessionForm.sessionId}
                onChange={(event) => setSessionForm((current) => ({ ...current, sessionId: event.target.value }))}
              />
            </label>
            <label>
              Device ID
              <input
                value={sessionForm.deviceId}
                onChange={(event) => setSessionForm((current) => ({ ...current, deviceId: event.target.value }))}
              />
            </label>
            <label>
              Mount
              <input
                placeholder="collar"
                value={sessionForm.mountLocation}
                onChange={(event) => setSessionForm((current) => ({ ...current, mountLocation: event.target.value }))}
              />
            </label>
            <label>
              Notes
              <input
                placeholder="optional"
                value={sessionForm.notes}
                onChange={(event) => setSessionForm((current) => ({ ...current, notes: event.target.value }))}
              />
            </label>
            <button className="primary-button" onClick={saveSession} type="button">
              Create session
            </button>
          </div>
        </aside>

        <section className="detail-panel">
          {selectedSession ? (
            <>
              <div className="panel-heading">
                <h2>Selected Session</h2>
                <span>{selectedSession.device_id}</span>
              </div>
              <dl className="metrics-grid">
                <div>
                  <dt>Samples</dt>
                  <dd>{selectedSession.sample_count.toLocaleString()}</dd>
                </div>
                <div>
                  <dt>Batches</dt>
                  <dd>{selectedSession.batch_count.toLocaleString()}</dd>
                </div>
                <div>
                  <dt>Duration</dt>
                  <dd>{formatDuration(selectedSession)}</dd>
                </div>
                <div>
                  <dt>Last Received</dt>
                  <dd>{formatTimestamp(selectedSession.last_server_received_at)}</dd>
                </div>
              </dl>
              {timelineError ? <p className="error-message">{timelineError}</p> : null}
              {isTimelineLoading ? (
                <div className="empty-timeline">
                  <strong>Loading timeline.</strong>
                  <span>Fetching range-ready samples and current labels from FastAPI.</span>
                </div>
              ) : (
                <Timeline
                  focusRange={focusRange}
                  isSelectionMode={isSelectionMode}
                  labels={labels}
                  onRangeSelected={(range) => {
                    setSelectedRange(range);
                    setIsSelectionMode(false);
                    setActionMessage(null);
                  }}
                  onSelectedRangeChange={setSelectedRange}
                  samples={samples}
                  selectedLabelId={selectedLabelId}
                  selectedRange={selectedRange}
                />
              )}
              <section className="label-workflow">
                <div className="label-form-panel">
                  <div className="panel-heading compact">
                    <h2>{editingLabel ? `Editing label #${editingLabel.id}` : "Create Label"}</h2>
                    <button
                      className={isSelectionMode ? "secondary-button active" : "secondary-button"}
                      onClick={() => setIsSelectionMode((current) => !current)}
                      type="button"
                    >
                      {isSelectionMode ? "Drag on timeline" : "Select range"}
                    </button>
                  </div>
                  <div className="range-readout">
                    {selectedRange
                      ? `${selectedRange.startDeviceMs} ms to ${selectedRange.endDeviceMs} ms`
                      : "No range selected"}
                  </div>
                  <div className="time-entry-grid">
                    <fieldset disabled={!selectedRange || samples.length === 0}>
                      <legend>Start time</legend>
                      <input
                        aria-label="Start hour"
                        max={23}
                        min={0}
                        onChange={(event) => updateRangeTime("start", "hours", event.target.value)}
                        type="number"
                        value={timePart(selectedStartDate, "hours")}
                      />
                      <input
                        aria-label="Start minute"
                        max={59}
                        min={0}
                        onChange={(event) => updateRangeTime("start", "minutes", event.target.value)}
                        type="number"
                        value={timePart(selectedStartDate, "minutes")}
                      />
                      <input
                        aria-label="Start second"
                        max={59}
                        min={0}
                        onChange={(event) => updateRangeTime("start", "seconds", event.target.value)}
                        type="number"
                        value={timePart(selectedStartDate, "seconds")}
                      />
                    </fieldset>
                    <fieldset disabled={!selectedRange || samples.length === 0}>
                      <legend>End time</legend>
                      <input
                        aria-label="End hour"
                        max={23}
                        min={0}
                        onChange={(event) => updateRangeTime("end", "hours", event.target.value)}
                        type="number"
                        value={timePart(selectedEndDate, "hours")}
                      />
                      <input
                        aria-label="End minute"
                        max={59}
                        min={0}
                        onChange={(event) => updateRangeTime("end", "minutes", event.target.value)}
                        type="number"
                        value={timePart(selectedEndDate, "minutes")}
                      />
                      <input
                        aria-label="End second"
                        max={59}
                        min={0}
                        onChange={(event) => updateRangeTime("end", "seconds", event.target.value)}
                        type="number"
                        value={timePart(selectedEndDate, "seconds")}
                      />
                    </fieldset>
                  </div>
                  <div className="label-form-grid">
                    <label>
                      Event type
                      <select
                        value={form.eventType}
                        onChange={(event) => setForm((current) => ({ ...current, eventType: event.target.value as EventType }))}
                      >
                        {EVENT_TYPES.map((eventType) => (
                          <option key={eventType} value={eventType}>
                            {eventType}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Severity
                      <select
                        value={form.severity}
                        onChange={(event) => setForm((current) => ({ ...current, severity: event.target.value }))}
                      >
                        <option value="">None</option>
                        {[1, 2, 3, 4, 5].map((severity) => (
                          <option key={severity} value={severity}>
                            {severity}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Notes
                      <input
                        value={form.notes}
                        onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
                        placeholder="Optional context"
                      />
                    </label>
                  </div>
                  <div className="form-actions">
                    <button className="primary-button" onClick={saveLabel} type="button">
                      {editingLabel ? "Save changes" : "Create label"}
                    </button>
                    <button className="secondary-button" onClick={clearForm} type="button">
                      Clear
                    </button>
                  </div>
                  {actionMessage ? <p className="action-message">{actionMessage}</p> : null}
                </div>

                <div className="label-list-panel">
                  <div className="panel-heading compact">
                    <h2>Labels</h2>
                    <span>{labels.length} total</span>
                  </div>
                  <div className="label-list">
                    {labels.map((label) => (
                      <div className="label-row" key={label.id}>
                        <div>
                          <strong>{label.event_type}</strong>
                          <span>
                            {label.start_device_ms} to {label.end_device_ms} ms
                          </span>
                        </div>
                        <div className="row-actions">
                          <button className="secondary-button" onClick={() => editLabel(label)} type="button">
                            Select
                          </button>
                          <button className="danger-button" onClick={() => void removeLabel(label)} type="button">
                            Delete
                          </button>
                        </div>
                      </div>
                    ))}
                    {labels.length === 0 ? <p className="empty-labels">No labels for this session yet.</p> : null}
                  </div>
                </div>
              </section>
            </>
          ) : (
            <div className="empty-timeline">
              <strong>No session selected.</strong>
              <span>Start the FastAPI server and upload IMU batches to populate this workbench.</span>
            </div>
          )}
        </section>
      </section>
    </main>
  );
}

export default App;
