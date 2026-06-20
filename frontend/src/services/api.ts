/**
 * API service layer — typed Axios client with auth interceptors,
 * token refresh, and correlation ID injection.
 */

import axios, { AxiosInstance, AxiosRequestConfig } from "axios";
import type {
  TokenResponse,
  CurrentUser,
  FleetStatus,
  DeviceState,
  ComplianceScore,
  TrendPoint,
  DriftEvent,
  FrameworkSummary,
  CopilotResponse,
  ChatMessage,
  Incident,
  IncidentStatus,
  NotificationItem,
} from "../types";

const BASE_URL = import.meta.env.VITE_API_URL ?? (import.meta.env.PROD ? "" : "http://localhost:8000");
let logoutRedirectInProgress = false;

// ── Axios instance ─────────────────────────────────────────────────────────────

const http: AxiosInstance = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
});

// Inject auth token and correlation ID on every request
http.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  config.headers = config.headers ?? {};
  if (token) config.headers.Authorization = `Bearer ${token}`;
  config.headers["X-Correlation-ID"] = crypto.randomUUID();
  return config;
});

function redirectToLogin() {
  if (logoutRedirectInProgress) {
    return;
  }

  logoutRedirectInProgress = true;
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  window.location.assign("/login");
}

// Auto-refresh on 401
http.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config as AxiosRequestConfig & { _retry?: boolean };
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      const refreshToken = localStorage.getItem("refresh_token");
      if (refreshToken) {
        try {
          const { data } = await axios.post<TokenResponse>(
            `${BASE_URL}/api/v1/auth/refresh`,
            { refresh_token: refreshToken }
          );
          localStorage.setItem("access_token", data.access_token);
          localStorage.setItem("refresh_token", data.refresh_token);
          http.defaults.headers.common.Authorization = `Bearer ${data.access_token}`;
          return http(original);
        } catch {
          redirectToLogin();
        }
      }
      redirectToLogin();
    }
    return Promise.reject(error);
  }
);

// ── Auth ───────────────────────────────────────────────────────────────────────

export const authApi = {
  login: (username: string, password: string) =>
    http.post<TokenResponse>("/auth/login", { username, password }).then((r) => r.data),

  me: () => http.get<CurrentUser>("/auth/me").then((r) => r.data),

  logout: () => http.post("/auth/logout"),
};

// ── Monitoring ─────────────────────────────────────────────────────────────────

export const monitoringApi = {
  fleetStatus: () =>
    http.get<FleetStatus>("/monitoring/fleet").then((r) => r.data),

  listDevices: (params?: { monitoring_state?: string; limit?: number; offset?: number }) =>
    http.get<DeviceState[]>("/monitoring/devices", { params }).then((r) => r.data),

  getDevice: (deviceId: string) =>
    http.get<DeviceState>(`/monitoring/devices/${deviceId}`).then((r) => r.data),

  forcePoll: (deviceId: string) =>
    http.post(`/monitoring/devices/${deviceId}/poll`).then((r) => r.data),

  deviceTrend: (deviceId: string, framework = "cis", hours = 24) =>
    http
      .get<{ trend: TrendPoint[]; statistics: Record<string, number> }>(
        `/monitoring/devices/${deviceId}/trend`,
        { params: { framework, hours } }
      )
      .then((r) => r.data),

  driftEvents: (params?: { severity?: string; acknowledged?: boolean; limit?: number }) =>
    http
      .get<{ total: number; events: DriftEvent[] }>("/monitoring/drift/events", { params })
      .then((r) => r.data),
};

// ── Compliance ─────────────────────────────────────────────────────────────────

export const complianceApi = {
  deviceScore: (deviceId: string, framework = "cis") =>
    http
      .get<ComplianceScore>(`/compliance/devices/${deviceId}/score`, { params: { framework } })
      .then((r) => r.data),

  fleetSummary: () =>
    http.get("/compliance/fleet/summary").then((r) => r.data),

  frameworkSummary: (framework: string) =>
    http.get<FrameworkSummary>(`/compliance/frameworks/${framework}/summary`).then((r) => r.data),

  activeDrift: (params?: { severity?: string; framework?: string; limit?: number }) =>
    http
      .get<{ total: number; drifts: DriftEvent[] }>("/compliance/drift/active", { params })
      .then((r) => r.data),

  acknowledgeDrift: (driftId: string) =>
    http.post(`/compliance/drift/${driftId}/acknowledge`).then((r) => r.data),

  listRules: (params?: { framework?: string; severity?: string }) =>
    http.get("/compliance/rules", { params }).then((r) => r.data),
};

// ── AI Copilot ─────────────────────────────────────────────────────────────────

export const copilotApi = {
  chat: (message: string, history: ChatMessage[] = [], sessionId?: string) =>
    http
      .post<CopilotResponse>("/ai/chat", { message, history, session_id: sessionId })
      .then((r) => r.data),

  explainCompliance: (ruleId: string, ruleName: string, findings: string[], framework = "cis") =>
    http
      .post<CopilotResponse>("/ai/explain/compliance", { rule_id: ruleId, rule_name: ruleName, findings, framework })
      .then((r) => r.data),

  securitySummary: (hours = 24) =>
    http.get<CopilotResponse>("/ai/summary/security", { params: { hours } }).then((r) => r.data),

  providersHealth: () =>
    http.get("/ai/providers/health").then((r) => r.data),
};

// ── Users ──────────────────────────────────────────────────────────────────────

export const usersApi = {
  list: (params?: { limit?: number; offset?: number }) =>
    http.get("/users", { params }).then((r) => r.data),

  get: (userId: string) =>
    http.get(`/users/${userId}`).then((r) => r.data),

  create: (username: string, email: string, password: string, role: string) =>
    http.post("/users", { username, email, password, role }).then((r) => r.data),

  update: (userId: string, updates: Record<string, unknown>) =>
    http.patch(`/users/${userId}`, updates).then((r) => r.data),

  delete: (userId: string) =>
    http.delete(`/users/${userId}`).then((r) => r.data),
};

// ── Audit ──────────────────────────────────────────────────────────────────────

export const auditApi = {
  list: (params?: { action?: string; user_id?: string; limit?: number; offset?: number }) =>
    http.get("/audit", { params }).then((r) => r.data),

  get: (auditId: string) =>
    http.get(`/audit/${auditId}`).then((r) => r.data),

  countByAction: (action: string) =>
    http.get(`/audit/actions/${action}/count`).then((r) => r.data),
};

// ── SIEM ───────────────────────────────────────────────────────────────────────

export const siemApi = {
  submitEvent: (eventType: string, severity: string, rawData: Record<string, unknown>) =>
    http.post("/siem/events", { event_type: eventType, severity, raw_data: rawData }).then((r) => r.data),

  list: (params?: { severity?: string; limit?: number; offset?: number }) =>
    http.get("/siem/events", { params }).then((r) => r.data),

  get: (eventId: string) =>
    http.get(`/siem/events/${eventId}`).then((r) => r.data),

  correlate: (eventId: string) =>
    http.post(`/siem/events/${eventId}/correlate`).then((r) => r.data),

  health: () =>
    http.get("/siem/health").then((r) => r.data),
};

// ── Reports ────────────────────────────────────────────────────────────────────

export const reportsApi = {
  list: (params?: { limit?: number; offset?: number }) =>
    http.get("/reports", { params }).then((r) => r.data),

  get: (reportId: string) =>
    http.get(`/reports/${reportId}`).then((r) => r.data),

  generate: (reportType: string, framework?: string, hours?: number) =>
    http.post("/reports/generate", { report_type: reportType, framework, hours }).then((r) => r.data),

  download: (reportId: string) =>
    http.post(`/reports/${reportId}/download`).then((r) => r.data),
};

// ── Threats ────────────────────────────────────────────────────────────────────

export const threatsApi = {
  listIndicators: (params?: { severity?: string; limit?: number }) =>
    http.get("/threats/indicators", { params }).then((r) => r.data),

  listCVEs: (params?: { severity?: string; limit?: number }) =>
    http.get("/threats/cves", { params }).then((r) => r.data),

  summary: () =>
    http.get("/threats/summary").then((r) => r.data),
};

// ── Incidents ─────────────────────────────────────────────────────────────────-

export const incidentsApi = {
  list: (params?: { status?: IncidentStatus; assigned_to?: string; limit?: number; offset?: number }) =>
    http.get<Incident[]>("/incidents", { params }).then((r) => r.data),

  get: (incidentId: string) =>
    http.get<Incident>(`/incidents/${incidentId}`).then((r) => r.data),

  create: (payload: {
    title: string;
    description: string;
    severity: "critical" | "high" | "medium" | "low" | "informational";
    source?: string;
    device_id?: string;
    finding_id?: string;
    owner_id?: string;
    assigned_to?: string;
  }) => http.post<Incident>("/incidents", payload).then((r) => r.data),

  assign: (incidentId: string, assignedTo: string) =>
    http.patch<Incident>(`/incidents/${incidentId}/assign`, { assigned_to: assignedTo }).then((r) => r.data),

  updateStatus: (incidentId: string, status: IncidentStatus) =>
    http.patch<Incident>(`/incidents/${incidentId}/status`, { status }).then((r) => r.data),

  addComment: (incidentId: string, comment: string, isInternal = false) =>
    http.post(`/incidents/${incidentId}/comments`, { comment, is_internal: isInternal }).then((r) => r.data),

  timeline: (incidentId: string) =>
    http.get(`/incidents/${incidentId}/timeline`).then((r) => r.data),
};

// ── Notifications ─────────────────────────────────────────────────────────────-

export const notificationsApi = {
  listMine: (params?: { unread_only?: boolean; limit?: number; offset?: number }) =>
    http.get<NotificationItem[]>("/notifications", { params }).then((r) => r.data),

  markRead: (notificationId: string) =>
    http.patch<NotificationItem>(`/notifications/${notificationId}/read`).then((r) => r.data),
};

export default http;
