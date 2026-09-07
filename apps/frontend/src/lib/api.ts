export type FieldContext = {
  field_id: string;
  club_name: string;
  venue_name: string;
  field_name: string;
  sport_code: string;
  status: 'active' | 'inactive' | 'maintenance';
  camera_status: 'live' | 'ready' | 'offline';
  active_session_id: string | null;
  recording_status: 'idle' | 'starting' | 'recording' | 'stopping';
};

export type SessionResponse = {
  session_id: string;
  session_token: string;
  field_name: string;
  sport_code: string;
  status: 'pending' | 'active';
  player_id?: string;
  access_token?: string;
};

export type PlayerMediaHighlight = {
  id: string;
  title: string;
  occurred_at: string;
  duration_seconds: number;
  status: 'processing' | 'available' | 'failed';
  media_path: string | null;
};

export type PlayerMediaPage = {
  session_id: string;
  player_name: string;
  club_name: string;
  field_name: string;
  sport_code: string;
  started_at: string;
  recording_status: 'in_progress' | 'processing' | 'available' | 'expired';
  recording_path: string | null;
  recording_expires_at: string | null;
  highlights: PlayerMediaHighlight[];
};

export type OwnerUser = { id: string; email: string; display_name: string; role: string };
export type OwnerSession = { access_token: string; user: OwnerUser };
export type AdminCourt = {
  id: string;
  name: string;
  sport_code: string;
  status: 'active' | 'inactive' | 'maintenance';
  recording: boolean;
  camera: null | {
    id: string;
    name: string;
    status: 'online' | 'offline';
    detector_status: string;
    last_seen_at: string | null;
  };
};
export type AdminCustomer = {
  id: string;
  display_name: string;
  email: string;
  active: boolean;
  created_at: string | null;
  club: null | { id: string; name: string; city: string; logo_data_url: string };
  status: 'operational' | 'attention' | 'setup';
  last_seen_at: string | null;
  metrics: {
    courts: number;
    cameras: number;
    cameras_online: number;
    cameras_offline: number;
    active_recordings: number;
    highlights: number;
    highlights_pending: number;
    highlights_failed: number;
  };
  courts: AdminCourt[];
};
export type AdminOverview = {
  generated_at: string;
  summary: {
    customers: number;
    clubs: number;
    courts: number;
    cameras: number;
    cameras_online: number;
    active_recordings: number;
    attention: number;
  };
  customers: AdminCustomer[];
};
export type OwnerClub = { id: string; name: string; city: string; logo_data_url: string; fields_count: number };
export type OwnerDashboard = {
  owner: OwnerUser;
  club: OwnerClub;
  cameras: Array<{ id: string; field_name: string; status: 'live' | 'ready' | 'offline'; last_seen: string }>;
  metrics: { highlights: string; players: string; delivery_rate: string; active_sessions: string; capacity: string };
  recent_highlights: Array<{ id: string; title: string; field_name: string; status: string; occurred_at: string }>;
};
export type OwnerHighlight = {
  id: string;
  display_id: string;
  title: string;
  field_id: string;
  field_name: string;
  session_id: string;
  session_code: string;
  session_started_at: string;
  players: string[];
  occurred_at: string;
  duration_seconds: number;
  confidence: number | null;
  status: 'processing' | 'available' | 'failed';
  media_path: string | null;
  download_path: string | null;
};
export type OwnerLibraryRecording = {
  id: string;
  display_id: string;
  title: string;
  field_id: string;
  field_name: string;
  session_id: string;
  session_code: string;
  session_started_at: string;
  players: string[];
  occurred_at: string;
  ended_at: string | null;
  expires_at: string | null;
  duration_seconds: number;
  status: 'processing' | 'available';
  media_path: string | null;
  download_path: string | null;
};
export type OwnerButton = { device_id: string; label: string; status: 'ready' | 'offline'; last_seen: string };
export type OwnerRecordingState = {
  status: 'idle' | 'starting' | 'recording' | 'stopping';
  session_id: string | null;
  started_at: string | null;
  started_by: 'player' | 'owner' | null;
};
export type OwnerField = {
  id: string;
  name: string;
  field_token: string;
  sport_code: string;
  status: 'active' | 'inactive' | 'maintenance';
  camera_status: 'live' | 'ready' | 'offline';
  recording_enabled: boolean;
  detection_mode: 'arms_up' | 'manual';
  qr_url: string;
  last_seen: string;
  camera: OwnerCamera | null;
  button: OwnerButton | null;
  active_session_id: string | null;
  recording: OwnerRecordingState;
};
export type OwnerCamera = { id: string; field_id: string; name: string; serial_number: string; host: string; rtsp_port: number; username: string; password_configured: boolean; agent_linked: boolean; agent_last_seen_at?: string | null; stream_path: string; stream_url: string; status: 'live' | 'ready' | 'offline'; last_seen: string; detector_status: string; detector_fps: number; detector_last_frame_at: string | null };
export type OwnerProfile = OwnerUser & { phone: string; timezone: string };
export type WhatsAppConnection = {
  status: 'unavailable' | 'disconnected' | 'connecting' | 'connected';
  instance_name: string;
  phone: string | null;
  profile_name: string | null;
  qr_base64: string | null;
  pairing_code: string | null;
};
export type OwnerNotification = { id: string; kind: 'camera' | 'highlight' | 'session'; title: string; detail: string; time: string; read: boolean; severity: 'warning' | 'success' | 'info' };
export type OwnerActivity = {
  id: string;
  kind: 'recording' | 'highlight' | 'delivery' | 'camera' | 'player';
  status: 'success' | 'info' | 'warning' | 'error';
  title: string;
  detail: string;
  occurred_at: string;
  field_id: string | null;
  session_id: string | null;
  highlight_id: string | null;
  href: string | null;
};
export type AgentPairingToken = { camera_id: string; token: string; expires_in: number };
export type CreatedCamera = OwnerCamera & { agent_token: string };
export type CreatedField = OwnerField & { agent_token?: string };

// Same-origin `/api` is the production-safe default. The Vite development
// server proxies it to the local backend, so a build can never accidentally
// point every customer's browser at its own localhost.
export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api';

type ApiValidationIssue = { loc?: Array<string | number>; msg?: string };

export class ApiRequestError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = 'ApiRequestError';
  }
}

export function isInvalidSessionError(error: unknown): boolean {
  return error instanceof ApiRequestError && (error.status === 401 || error.status === 403);
}

export function formatApiError(detail: unknown, fallback: string): string {
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((issue: ApiValidationIssue) => typeof issue?.msg === 'string' ? issue.msg.trim() : '')
      .filter(Boolean);
    if (messages.length > 0) return messages.join('. ');
  }
  return fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    });
  } catch {
    // Un fallo de red llega como "Failed to fetch": no le dice nada al operador.
    throw new Error('No pudimos conectarnos con el servidor. Revisá la conexión.');
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: unknown } | null;
    throw new ApiRequestError(
      formatApiError(body?.detail, 'No pudimos completar la operación. Intentá nuevamente.'),
      response.status,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function loginOwner(email: string, password: string) {
  try {
    return await request<OwnerSession>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
  } catch (error) {
    if (error instanceof ApiRequestError && (error.status === 401 || error.status === 422)) {
      throw new Error('El email o la contraseña no son correctos.');
    }
    throw error;
  }
}

export function getCurrentOwner(token: string) {
  return request<OwnerUser>('/auth/me', { headers: { Authorization: `Bearer ${token}` } });
}

export function refreshOwnerSession(token: string) {
  return request<OwnerSession>('/auth/refresh', { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
}

export function logoutOwner(token: string) {
  return request<void>('/auth/logout', { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
}

export async function loginAdmin(email: string, password: string) {
  try {
    return await request<OwnerSession>('/admin/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
  } catch (error) {
    if (error instanceof ApiRequestError && (error.status === 401 || error.status === 422)) {
      throw new Error('El email o la contraseña no son correctos.');
    }
    throw error;
  }
}

export function refreshAdminSession(token: string) {
  return request<OwnerSession>('/admin/auth/refresh', { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
}

export function logoutAdmin(token: string) {
  return request<void>('/admin/auth/logout', { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
}

export function getAdminOverview(token: string) {
  return request<AdminOverview>('/admin/overview', { headers: { Authorization: `Bearer ${token}` } });
}

export function createAdminCustomer(token: string, payload: {
  display_name: string;
  email: string;
  password: string;
  club_name: string;
  city: string;
}) {
  return request<AdminCustomer>('/admin/customers', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
}

export function getOwnerDashboard(token: string) {
  return request<OwnerDashboard>('/owner/dashboard', { headers: { Authorization: `Bearer ${token}` } });
}

export function getOwnerHighlights(token: string) {
  return request<{ items: OwnerHighlight[] }>('/owner/highlights', { headers: { Authorization: `Bearer ${token}` } });
}

export function getOwnerRecordings(token: string) {
  return request<{ items: OwnerLibraryRecording[] }>('/owner/recordings', { headers: { Authorization: `Bearer ${token}` } });
}

export function deleteOwnerHighlight(token: string, highlightId: string) {
  return request<void>(`/owner/highlights/${highlightId}`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } });
}

export function deleteOwnerHighlights(token: string, highlightIds: string[]) {
  return request<{ deleted: number; highlight_ids: string[] }>('/owner/highlights/delete-batch', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ highlight_ids: highlightIds }),
  });
}

export function deleteOwnerRecording(token: string, recordingId: string) {
  return request<void>(`/owner/recordings/${recordingId}`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } });
}

export function deleteOwnerRecordings(token: string, recordingIds: string[]) {
  return request<{ deleted: number; recording_ids: string[] }>('/owner/recordings/delete-batch', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ recording_ids: recordingIds }),
  });
}

export function getOwnerFields(token: string) {
  return request<{ items: OwnerField[] }>('/owner/fields', { headers: { Authorization: `Bearer ${token}` } });
}

export function createOwnerField(token: string, payload: { name: string; sport_code: 'padel' | 'football'; detection_mode: 'arms_up' | 'manual'; camera_name?: string; camera_host?: string; camera_rtsp_port?: number; camera_username?: string; camera_password?: string; camera_stream_path?: string; camera_serial_number?: string }) {
  return request<CreatedField>('/owner/fields', { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify(payload) });
}

export function updateOwnerField(token: string, fieldId: string, payload: Partial<Pick<OwnerField, 'name' | 'status' | 'detection_mode'>>) {
  return request<OwnerField>(`/owner/fields/${fieldId}`, { method: 'PATCH', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify(payload) });
}

export function startOwnerFieldRecording(token: string, fieldId: string) {
  return request<OwnerField>(`/owner/fields/${fieldId}/recording/start`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
}

export function stopOwnerFieldRecording(token: string, fieldId: string) {
  return request<OwnerField>(`/owner/fields/${fieldId}/recording/stop`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
}

export function deleteOwnerField(token: string, fieldId: string) {
  return request<void>(`/owner/fields/${fieldId}`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } });
}

export function updateOwnerButton(token: string, fieldId: string, payload: { device_id: string; secret: string }) {
  return request<OwnerField>(`/owner/fields/${fieldId}/button`, { method: 'PUT', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify(payload) });
}

export function getOwnerCameras(token: string) {
  return request<{ items: OwnerCamera[] }>('/owner/cameras', { headers: { Authorization: `Bearer ${token}` } });
}

export function createOwnerCamera(token: string, payload: { field_id: string; name: string; serial_number?: string; host?: string; rtsp_port?: number; username?: string; password?: string; stream_path?: string; stream_url?: string }) {
  return request<CreatedCamera>('/owner/cameras', { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify(payload) });
}

export function updateOwnerCamera(token: string, cameraId: string, payload: Partial<Pick<OwnerCamera, 'name' | 'serial_number' | 'host' | 'rtsp_port' | 'username' | 'stream_path' | 'stream_url' | 'status'>> & { password?: string }) {
  return request<OwnerCamera>(`/owner/cameras/${cameraId}`, { method: 'PATCH', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify(payload) });
}

export function deleteOwnerCamera(token: string, cameraId: string) {
  return request<void>(`/owner/cameras/${cameraId}`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } });
}

export function createOwnerCameraAgentToken(token: string, cameraId: string) {
  return request<AgentPairingToken>(`/owner/cameras/${cameraId}/agent-token`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
}

export function unlinkOwnerCameraAgent(token: string, cameraId: string) {
  return request<void>(`/owner/cameras/${cameraId}/agent-link`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } });
}

export const LOCAL_AGENT_BASE = import.meta.env.VITE_LOCAL_AGENT_URL ?? 'http://127.0.0.1:8781/v1';

export function localAgentStatusUrl(cameraId?: string) {
  return `${LOCAL_AGENT_BASE}/status${cameraId ? `?camera_id=${encodeURIComponent(cameraId)}` : ''}`;
}

export function localAgentPreviewUrl(mode: 'preview' | 'live' = 'preview', cameraId?: string) {
  return `${LOCAL_AGENT_BASE}/preview.mjpeg?mode=${mode}${cameraId ? `&camera_id=${encodeURIComponent(cameraId)}` : ''}&t=${Date.now()}`;
}

export function localAgentConfigUrl(cameraId?: string) {
  return `${LOCAL_AGENT_BASE}/config${cameraId ? `?camera_id=${encodeURIComponent(cameraId)}` : ''}`;
}

export function localAgentCheckUrl(cameraId?: string) {
  return `${LOCAL_AGENT_BASE}/check${cameraId ? `?camera_id=${encodeURIComponent(cameraId)}` : ''}`;
}

export function localAgentRemoveUrl(cameraId: string) {
  return `${LOCAL_AGENT_BASE}/cameras?camera_id=${encodeURIComponent(cameraId)}`;
}

export type DesktopRuntime = { cloud_api_url: string; public_app_url: string };

let desktopRuntimePromise: Promise<DesktopRuntime | null> | null = null;

/** Detecta CourtVision Desktop sin intentar tocar el agente local desde la web pública. */
export function getDesktopRuntime(): Promise<DesktopRuntime | null> {
  if (desktopRuntimePromise) return desktopRuntimePromise;
  desktopRuntimePromise = fetch('/__courtvision/runtime', {
    headers: { Accept: 'application/json' },
    cache: 'no-store',
  })
    .then(async (response) => {
      if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) return null;
      const runtime = await response.json() as Partial<DesktopRuntime>;
      if (
        typeof runtime.cloud_api_url !== 'string'
        || typeof runtime.public_app_url !== 'string'
        || !/^https?:\/\//.test(runtime.cloud_api_url)
        || !/^https?:\/\//.test(runtime.public_app_url)
      ) return null;
      return { cloud_api_url: runtime.cloud_api_url, public_app_url: runtime.public_app_url };
    })
    .catch(() => null);
  return desktopRuntimePromise;
}

export async function cloudApiUrlForAgent() {
  if (!API_BASE.startsWith('/')) return API_BASE;
  const runtime = await getDesktopRuntime();
  if (runtime) return runtime.cloud_api_url.replace(/\/$/, '');
  return `${window.location.origin}${API_BASE}`;
}

export async function publicAppOrigin() {
  const runtime = await getDesktopRuntime();
  if (runtime) return runtime.public_app_url.replace(/\/$/, '');
  return window.location.origin;
}

export type LocalDetectorConfig = {
  detector: {
    model: string;
    device: string;
    image_size: number;
    person_confidence: number;
    keypoint_confidence: number;
    roi: [number, number, number, number];
    min_person_height_ratio: number;
    min_wrist_spread_ratio: number;
    hold_seconds: number;
    cooldown_seconds: number;
    max_gap_seconds: number;
  };
};

export function getLocalDetectorConfig(cameraId: string) {
  return fetch(localAgentConfigUrl(cameraId)).then(async (response) => {
    if (!response.ok) throw new Error('El agente local no responde.');
    return response.json() as Promise<LocalDetectorConfig>;
  });
}

export function updateLocalDetectorConfig(cameraId: string, payload: { pose_roi: [number, number, number, number] }) {
  return fetch(localAgentConfigUrl(cameraId), {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).then(async (response) => {
    if (!response.ok) throw new Error('No pudimos guardar la zona en el agente local.');
    return response.json();
  });
}

export function updateOwnerClub(token: string, payload: Pick<OwnerClub, 'name' | 'city' | 'logo_data_url'>) {
  return request<OwnerClub>('/owner/club', { method: 'PATCH', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify(payload) });
}

export function getOwnerProfile(token: string) {
  return request<OwnerProfile>('/owner/profile', { headers: { Authorization: `Bearer ${token}` } });
}

export function updateOwnerProfile(token: string, payload: Pick<OwnerProfile, 'display_name' | 'phone' | 'timezone'>) {
  return request<OwnerProfile>('/owner/profile', { method: 'PATCH', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify(payload) });
}

export function getOwnerWhatsApp(token: string) {
  return request<WhatsAppConnection>('/owner/whatsapp', { headers: { Authorization: `Bearer ${token}` } });
}

export function connectOwnerWhatsApp(token: string) {
  return request<WhatsAppConnection>('/owner/whatsapp/connect', { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
}

export function disconnectOwnerWhatsApp(token: string) {
  return request<WhatsAppConnection>('/owner/whatsapp', { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } });
}

export function getOwnerNotifications(token: string) {
  return request<{ items: OwnerNotification[] }>('/owner/notifications', { headers: { Authorization: `Bearer ${token}` } });
}

export function getOwnerActivity(token: string) {
  return request<{ items: OwnerActivity[] }>('/owner/activity', { headers: { Authorization: `Bearer ${token}` } });
}

export function markOwnerNotificationRead(token: string, notificationId: string) {
  return request<OwnerNotification>(`/owner/notifications/${notificationId}/read`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
}

export function markAllOwnerNotificationsRead(token: string) {
  return request<{ items: OwnerNotification[] }>('/owner/notifications/read-all', { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
}

export function deleteAllOwnerNotifications(token: string) {
  return request<void>('/owner/notifications', { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } });
}

export function getFieldContext(fieldToken: string) {
  return request<FieldContext>(`/public/fields/${fieldToken}`);
}

export function startSession(fieldToken: string, payload: { display_name: string; phone_e164: string; recording_consent: true; messaging_consent: boolean }, requestId: string) {
  return request<SessionResponse>(`/public/fields/${fieldToken}/sessions`, {
    method: 'POST',
    headers: { 'Idempotency-Key': `qr-${requestId}` },
    body: JSON.stringify(payload),
  });
}

export function getPlayerMediaPage(accessToken: string) {
  return request<PlayerMediaPage>(`/public/access/${encodeURIComponent(accessToken)}`);
}

export function publicMediaUrl(path: string) {
  return `${API_BASE}${path}`;
}
