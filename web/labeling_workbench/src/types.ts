export type EventType = string;

export const EVENT_TYPES: string[] = [
  "seizure",
  "sleep_twitch",
  "scratching",
  "scooting",
  "shake_off",
  "walking",
  "running",
  "resting",
  "unknown",
];

export type EventPayload = {
  session_id: string;
  event_type: EventType;
  severity: number | null;
  start_device_ms: number;
  end_device_ms: number;
  start_server_received_at?: string | null;
  end_server_received_at?: string | null;
  source: string;
  notes: string | null;
};

export type SessionCreatePayload = {
  session_id: string;
  device_id: string;
  started_at?: string | null;
  ended_at?: string | null;
  mount_location?: string | null;
  notes?: string | null;
};

export type SessionSummary = {
  session_id: string;
  device_id: string;
  started_at: string | null;
  ended_at: string | null;
  mount_location: string | null;
  notes: string | null;
  sample_count: number;
  batch_count: number;
  min_device_ms: number | null;
  max_device_ms: number | null;
  first_server_received_at: string | null;
  last_server_received_at: string | null;
};

export type SessionSample = {
  device_id: string;
  session_id: string;
  boot_id: string;
  batch_sequence: number;
  sample_index: number;
  device_ms: number;
  server_received_at: string;
  ax: number;
  ay: number;
  az: number;
  gx: number;
  gy: number;
  gz: number;
  accel_mag: number;
  gyro_mag: number;
};

export type EventLabel = {
  id: number;
  session_id: string;
  event_type: EventType;
  severity: number | null;
  start_device_ms: number;
  end_device_ms: number;
  start_server_received_at: string | null;
  end_server_received_at: string | null;
  source: string;
  notes: string | null;
  created_at: string;
};

export type SessionSampleWindow = {
  samples: SessionSample[];
  total_sample_count: number;
  window_start_index: number | null;
  window_end_index: number | null;
  window_start_server_received_at: string | null;
  window_end_server_received_at: string | null;
  window_start_device_ms: number | null;
  window_end_device_ms: number | null;
};

export type SelectionRange = {
  startDeviceMs: number;
  endDeviceMs: number;
  startServerReceivedAt?: string | null;
  endServerReceivedAt?: string | null;
};

export type ViewRange = {
  startDeviceMs: number;
  endDeviceMs: number;
  startServerReceivedAt?: string | null;
  endServerReceivedAt?: string | null;
};

export type ApiRuntimeStatus = {
  status: "ok";
  server_time: string;
  database_path: string;
  session_count: number;
  batch_count: number;
  sample_count: number;
  latest_batch_received_at: string | null;
  latest_sample_received_at: string | null;
  latest_device_ms: number | null;
  latest_boot_id: string | null;
  latest_reset_reason: string | null;
  latest_reset_info: string | null;
  latest_uptime_ms: number | null;
  latest_wifi_rssi: number | null;
  latest_free_heap: number | null;
  latest_min_free_heap: number | null;
  latest_heap_fragmentation: number | null;
  latest_queued_batch_count: number | null;
  latest_dropped_batch_count: number | null;
  latest_max_sample_lateness_ms: number | null;
  latest_upload_skip_count: number | null;
  latest_last_http_duration_ms: number | null;
  latest_last_http_status: number | null;
  latest_consecutive_upload_failures: number | null;
  latest_wifi_disconnect_count: number | null;
  latest_session: {
    session_id: string;
    sample_count: number;
    latest_received_at: string | null;
  } | null;
};

export type BootSummary = {
  device_id: string;
  session_id: string;
  boot_id: string;
  reset_reason: string | null;
  reset_info: string | null;
  first_received_at: string | null;
  last_received_at: string | null;
  min_sequence: number | null;
  max_sequence: number | null;
  batch_count: number;
  sample_count: number;
  min_device_ms_start: number | null;
  max_device_ms_start: number | null;
  latest_uptime_ms: number | null;
  latest_http_status: number | null;
  latest_http_duration_ms: number | null;
  max_consecutive_upload_failures: number | null;
  max_wifi_disconnect_count: number | null;
  max_queued_batch_count: number | null;
  max_dropped_batch_count: number | null;
  max_sample_lateness_ms: number | null;
  max_upload_skip_count: number | null;
  min_wifi_rssi: number | null;
  max_wifi_rssi: number | null;
  min_free_heap: number | null;
  min_reported_free_heap: number | null;
  max_heap_fragmentation: number | null;
};

export type ActiveSessionSummary = {
  device_id: string;
  session_id: string;
  updated_at: string;
  session: SessionSummary;
};

export type ApiControlStatus = {
  apiBaseUrl: string;
  apiReachable: boolean;
  managed: boolean;
  pid: number | null;
  message: string;
  logs: string[];
};
