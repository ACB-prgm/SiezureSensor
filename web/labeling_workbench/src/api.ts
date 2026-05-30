import type { EventLabel, EventPayload, SessionSample, SessionSummary } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

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

export function listSessionSamples(sessionId: string, maxPoints = 2000): Promise<SessionSample[]> {
  const params = new URLSearchParams({ max_points: String(maxPoints) });
  return requestJson<SessionSample[]>(`/api/v1/sessions/${encodeURIComponent(sessionId)}/samples?${params}`);
}

export function listEvents(sessionId: string): Promise<EventLabel[]> {
  const params = new URLSearchParams({ session_id: sessionId });
  return requestJson<EventLabel[]>(`/api/v1/events?${params}`);
}

export function createEvent(payload: EventPayload): Promise<EventLabel> {
  return requestJson<EventLabel>("/api/v1/events", {
    body: JSON.stringify(payload),
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
