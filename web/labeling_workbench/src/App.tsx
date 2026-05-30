import { useEffect, useState } from "react";

import { createEvent, deleteEvent, listEvents, listSessionSamples, listSessions, updateEvent } from "./api";
import Timeline from "./Timeline";
import { EVENT_TYPES, type EventLabel, type EventPayload, type EventType, type SelectionRange, type SessionSample, type SessionSummary } from "./types";

type LabelFormState = {
  eventType: EventType;
  severity: string;
  source: string;
  notes: string;
};

const DEFAULT_FORM: LabelFormState = {
  eventType: "scratching",
  severity: "",
  source: "manual",
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
  const [selectedRange, setSelectedRange] = useState<SelectionRange | null>(null);
  const [editingLabel, setEditingLabel] = useState<EventLabel | null>(null);
  const [form, setForm] = useState<LabelFormState>(DEFAULT_FORM);

  useEffect(() => {
    let isActive = true;

    async function loadSessions() {
      try {
        setIsLoading(true);
        const result = await listSessions();
        if (!isActive) {
          return;
        }
        setSessions(result);
        setSelectedSessionId((current) => current ?? result[0]?.session_id ?? null);
        setError(null);
      } catch (caught) {
        if (isActive) {
          setError(caught instanceof Error ? caught.message : "Failed to load sessions");
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    }

    void loadSessions();
    return () => {
      isActive = false;
    };
  }, []);

  useEffect(() => {
    const sessionId: string = selectedSessionId ?? "";
    if (!sessionId) {
      setSamples([]);
      setLabels([]);
      return;
    }

    let isActive = true;

    async function loadTimeline() {
      try {
        setIsTimelineLoading(true);
        const [nextSamples, nextLabels] = await Promise.all([
          listSessionSamples(sessionId, 4000),
          listEvents(sessionId),
        ]);
        if (!isActive) {
          return;
        }
        setSamples(nextSamples);
        setLabels(nextLabels);
        setTimelineError(null);
      } catch (caught) {
        if (isActive) {
          setTimelineError(caught instanceof Error ? caught.message : "Failed to load timeline");
        }
      } finally {
        if (isActive) {
          setIsTimelineLoading(false);
        }
      }
    }

    void loadTimeline();
    return () => {
      isActive = false;
    };
  }, [selectedSessionId]);

  const selectedSession = sessions.find((session) => session.session_id === selectedSessionId) ?? null;

  async function refreshLabels(sessionId: string) {
    setLabels(await listEvents(sessionId));
  }

  function clearForm() {
    setEditingLabel(null);
    setSelectedRange(null);
    setForm(DEFAULT_FORM);
    setActionMessage(null);
  }

  function editLabel(label: EventLabel) {
    setEditingLabel(label);
    setSelectedRange({ startDeviceMs: label.start_device_ms, endDeviceMs: label.end_device_ms });
    setForm({
      eventType: label.event_type,
      severity: label.severity === null ? "" : String(label.severity),
      source: label.source,
      notes: label.notes ?? "",
    });
    setActionMessage(null);
  }

  function buildPayload(sessionId: string): EventPayload | null {
    if (!selectedRange || selectedRange.endDeviceMs <= selectedRange.startDeviceMs) {
      setActionMessage("Select a non-empty range on the timeline before saving.");
      return null;
    }

    return {
      session_id: sessionId,
      event_type: form.eventType,
      severity: form.severity === "" ? null : Number(form.severity),
      start_device_ms: selectedRange.startDeviceMs,
      end_device_ms: selectedRange.endDeviceMs,
      source: form.source.trim() || "manual",
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
        <div className="status-card">
          <span>API</span>
          <strong>{import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000"}</strong>
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
                  isSelectionMode={isSelectionMode}
                  labels={labels}
                  onRangeSelected={(range) => {
                    setSelectedRange(range);
                    setIsSelectionMode(false);
                    setActionMessage(null);
                  }}
                  samples={samples}
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
                      ? `${selectedRange.startDeviceMs} ms -> ${selectedRange.endDeviceMs} ms`
                      : "No range selected"}
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
                      Source
                      <input
                        value={form.source}
                        onChange={(event) => setForm((current) => ({ ...current, source: event.target.value }))}
                      />
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
                            Edit
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
