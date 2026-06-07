import type {
  ApiControlStatus,
  ApiRuntimeStatus,
  ActiveSessionSummary,
  BootSummary,
  EventLabel,
  EventPayload,
  SessionCreatePayload,
  SessionSample,
  SessionSampleWindow,
  SessionSummary,
} from "./types";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? `${window.location.protocol}//${window.location.hostname}:8000`;
export const API_CONTROL_BASE_URL = `${window.location.origin}/__dev/api`;

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    throw new Error(`Request failed with ${response.status}: ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export function listSessions(): Promise<SessionSummary[]> {
  return requestJson<SessionSummary[]>("/api/v1/sessions");
}

export function getApiRuntimeStatus(): Promise<ApiRuntimeStatus> {
  return requestJson<ApiRuntimeStatus>("/api/v1/status");
}

async function requestControl(path: string, init?: RequestInit): Promise<ApiControlStatus> {
  const response = await fetch(`${API_CONTROL_BASE_URL}${path}`, init);
  if (!response.ok) {
    let message = `Request failed with ${response.status}: ${response.statusText}`;
    try {
      const body = (await response.json()) as Partial<ApiControlStatus>;
      message = body.message ?? message;
    } catch {
      // Keep the HTTP fallback if the dev control endpoint did not return JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<ApiControlStatus>;
}

export function getApiControlStatus(): Promise<ApiControlStatus> {
  return requestControl("/status");
}

export function startApiService(): Promise<ApiControlStatus> {
  return requestControl("/start", { method: "POST" });
}

export function stopApiService(): Promise<ApiControlStatus> {
  return requestControl("/stop", { method: "POST" });
}

export function createSession(payload: SessionCreatePayload): Promise<SessionSummary> {
  return requestJson<SessionSummary>("/api/v1/sessions", {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
}

export async function deleteSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
  if (!response.ok) {
    let message = `Request failed with ${response.status}: ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: string };
      message = body.detail ?? message;
    } catch {
      // Keep the HTTP fallback if the API did not return JSON.
    }
    throw new Error(message);
  }
}

export function getActiveSession(deviceId: string): Promise<ActiveSessionSummary | null> {
  return requestJson<ActiveSessionSummary | null>(`/api/v1/devices/${encodeURIComponent(deviceId)}/active-session`);
}

export function setActiveSession(deviceId: string, sessionId: string): Promise<ActiveSessionSummary> {
  return requestJson<ActiveSessionSummary>(`/api/v1/devices/${encodeURIComponent(deviceId)}/active-session`, {
    body: JSON.stringify({ session_id: sessionId }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
}

export function listDeviceBoots(deviceId: string, sessionId?: string): Promise<BootSummary[]> {
  const params = new URLSearchParams();
  if (sessionId) {
    params.set("session_id", sessionId);
  }
  const suffix = params.size > 0 ? `?${params}` : "";
  return requestJson<BootSummary[]>(`/api/v1/devices/${encodeURIComponent(deviceId)}/boots${suffix}`);
}

export function listSessionSamples(
  sessionId: string,
  maxPoints = 2000,
  startDeviceMs?: number,
  endDeviceMs?: number,
): Promise<SessionSample[]> {
  const params = new URLSearchParams({ max_points: String(maxPoints) });
  if (startDeviceMs !== undefined) {
    params.set("start_device_ms", String(Math.round(startDeviceMs)));
  }
  if (endDeviceMs !== undefined) {
    params.set("end_device_ms", String(Math.round(endDeviceMs)));
  }
  return requestJson<SessionSample[]>(`/api/v1/sessions/${encodeURIComponent(sessionId)}/samples?${params}`);
}

export type SampleWindowParams = {
  maxPoints?: number;
  startDeviceMs?: number;
  endDeviceMs?: number;
  startServerReceivedAt?: string;
  endServerReceivedAt?: string;
};

export function getSessionSampleWindow(sessionId: string, params: SampleWindowParams = {}): Promise<SessionSampleWindow> {
  const query = new URLSearchParams({ max_points: String(params.maxPoints ?? 20000) });
  if (params.startDeviceMs !== undefined) {
    query.set("start_device_ms", String(Math.round(params.startDeviceMs)));
  }
  if (params.endDeviceMs !== undefined) {
    query.set("end_device_ms", String(Math.round(params.endDeviceMs)));
  }
  if (params.startServerReceivedAt !== undefined) {
    query.set("start_server_received_at", params.startServerReceivedAt);
  }
  if (params.endServerReceivedAt !== undefined) {
    query.set("end_server_received_at", params.endServerReceivedAt);
  }
  return requestJson<SessionSampleWindow>(`/api/v1/sessions/${encodeURIComponent(sessionId)}/sample-window?${query}`);
}

function eventPayloadBody(payload: EventPayload): string {
  return JSON.stringify(payload);
}

export function listEvents(sessionId: string): Promise<EventLabel[]> {
  const params = new URLSearchParams({ session_id: sessionId });
  return requestJson<EventLabel[]>(`/api/v1/events?${params}`);
}

export function createEvent(payload: EventPayload): Promise<EventLabel> {
  return requestJson<EventLabel>("/api/v1/events", {
    body: eventPayloadBody(payload),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
}

export function updateEvent(eventId: number, payload: Partial<EventPayload>): Promise<EventLabel> {
  return requestJson<EventLabel>(`/api/v1/events/${eventId}`, {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
    method: "PATCH",
  });
}

export async function deleteEvent(eventId: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/events/${eventId}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error(`Request failed with ${response.status}: ${response.statusText}`);
  }
}
