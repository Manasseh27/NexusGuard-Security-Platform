// ── Auth ───────────────────────────────────────────────────────────────────────

export interface TokenResponse {
  access_token:  string;
  refresh_token: string;
  token_type:    string;
  expires_in:    number;
}

export interface CurrentUser {
  id:          string;
  username:    string;
  email:       string;
  role:        string;
  permissions: string[];
  tenant_id:   string;
}

// ── Fleet / Monitoring ─────────────────────────────────────────────────────────

export type MonitoringState = "healthy" | "drifting" | "degraded" | "unreachable" | "remediating";

export interface FleetStatus {
  total_devices:             number;
  healthy:                   number;
  drifting:                  number;
  unreachable:               number;
  degraded:                  number;
  average_compliance_score:  number;
  fleet_health_pct:          number;
  active_drift_events:       number;
  monitoring_enabled:        boolean;
  updated_at:                string;
}

export interface DeviceState {
  device_id:           string;
  device_ip:           string;
  device_type:         string;
  monitoring_state:    MonitoringState;
  current_score:       number;
  baseline_score:      number | null;
  last_polled:         string | null;
  last_successful:     string | null;
  active_drift_count:  number;
  consecutive_failures: number;
  poll_interval:       number;
  next_poll_at:        string;
  frameworks:          string[];
}

// ── Compliance ─────────────────────────────────────────────────────────────────

export type Severity = "critical" | "high" | "medium" | "low" | "informational";
export type ComplianceFramework = "cis" | "nist_csf" | "nist_800_53" | "iso_27001" | "pci_dss" | "hipaa" | "mitre_attack" | "soc2" | "custom";

export interface ComplianceScore {
  device_id:            string;
  framework:            string;
  overall_score:        number;
  weighted_score:       number;
  compliance_percentage: number;
  pass_count:           number;
  fail_count:           number;
  error_count:          number;
  critical_failures:    number;
  generated_at:         string;
  baseline_delta:       number | null;
}

export interface TrendPoint {
  timestamp:  string;
  score:      number;
  pass_count: number;
  fail_count: number;
}

export interface DriftEvent {
  drift_id:        string;
  device_id:       string;
  device_ip:       string;
  framework:       string;
  rule_id:         string;
  rule_name:       string;
  severity:        Severity;
  previous_result: string;
  current_result:  string;
  score_delta:     number;
  detected_at:     string;
  acknowledged:    boolean;
  remediated:      boolean;
  remediation_job_id: string | null;
  [key: string]: unknown;
}

export interface FrameworkSummary {
  framework:               string;
  total_devices:           number;
  avg_score:               number;
  devices_compliant:       number;
  devices_at_risk:         number;
  devices_critical:        number;
  total_critical_findings: number;
}

// ── Incidents ─────────────────────────────────────────────────────────────────-

export type IncidentStatus = "new" | "assigned" | "investigating" | "contained" | "resolved" | "closed";

export interface Incident {
  id: string;
  incident_key: string;
  title: string;
  description: string;
  severity: Severity;
  status: IncidentStatus;
  source: string;
  device_id: string | null;
  finding_id: string | null;
  created_by: string | null;
  assigned_to: string | null;
  owner_id: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  closed_at: string | null;
}

// ── Notifications ─────────────────────────────────────────────────────────────-

export type NotificationType = "incident" | "finding" | "compliance" | "alert" | "system";

export interface NotificationItem {
  id: string;
  event_type: string;
  title: string;
  message: string;
  notification_type: NotificationType;
  channel: "in_app" | "email" | "webhook";
  status: "pending" | "sent" | "failed" | "read";
  is_read: boolean;
  read_at: string | null;
  user_id: string | null;
  incident_id: string | null;
  created_at: string;
}

// ── SIEM ───────────────────────────────────────────────────────────────────────

export interface SIEMHealth {
  [platform: string]: boolean;
}

// ── AI Copilot ─────────────────────────────────────────────────────────────────

export interface CopilotResponse {
  content:      string;
  provider:     string;
  model:        string;
  operation:    string;
  tokens_used:  number;
  latency_ms:   number;
  cached:       boolean;
  session_id:   string | null;
  generated_at: string;
}

export interface ChatMessage {
  role:    "user" | "assistant" | "system";
  content: string;
}

// ── API pagination ─────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  total:    number;
  returned: number;
  items:    T[];
}
