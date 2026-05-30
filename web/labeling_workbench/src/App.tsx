import { useEffect, useState } from "react";

import { listEvents, listSessionSamples, listSessions } from "./api";
import Timeline from "./Timeline";
import type { EventLabel, SessionSample, SessionSummary } from "./types";

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
  const [isLoading, setIsLoading] = useState(true);
  const [isTimelineLoading, setIsTimelineLoading] = useState(false);

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
                <Timeline labels={labels} samples={samples} />
              )}
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
