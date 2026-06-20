import { useEffect, useMemo, useState } from "react";

import { incidentsApi } from "../services/api";
import type { Incident, IncidentStatus } from "../types";
import { C } from "../styles/tokens";

const STATUSES: IncidentStatus[] = ["new", "assigned", "investigating", "contained", "resolved", "closed"];

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState<"critical" | "high" | "medium" | "low" | "informational">("high");
  const [submitting, setSubmitting] = useState(false);

  const criticalOpen = useMemo(
    () => incidents.filter((i) => i.severity === "critical" && i.status !== "closed").length,
    [incidents]
  );

  const fetchIncidents = async () => {
    try {
      setLoading(true);
      const payload = await incidentsApi.list({ status: statusFilter as IncidentStatus | undefined, limit: 200 });
      setIncidents(payload);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load incidents");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidents();
  }, [statusFilter]);

  const createIncident = async () => {
    if (!title.trim() || !description.trim()) return;
    try {
      setSubmitting(true);
      await incidentsApi.create({
        title: title.trim(),
        description: description.trim(),
        severity,
        source: "manual",
      });
      setTitle("");
      setDescription("");
      await fetchIncidents();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create incident");
    } finally {
      setSubmitting(false);
    }
  };

  const updateStatus = async (incidentId: string, nextStatus: IncidentStatus) => {
    try {
      await incidentsApi.updateStatus(incidentId, nextStatus);
      await fetchIncidents();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update incident");
    }
  };

  return (
    <div style={{ background: C.bg, minHeight: "100vh", color: C.text, padding: 24 }}>
      <h1 style={{ marginBottom: 20, fontSize: 28, fontWeight: 600 }}>Incident Management</h1>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16, marginBottom: 20 }}>
        <div style={{ background: C.surface2, border: `1px solid ${C.border}`, borderRadius: 8, padding: 14 }}>
          <div style={{ color: C.textMuted, fontSize: 12 }}>Total Incidents</div>
          <div style={{ fontSize: 30, fontWeight: 700 }}>{incidents.length}</div>
        </div>
        <div style={{ background: C.surface2, border: `1px solid ${C.border}`, borderRadius: 8, padding: 14 }}>
          <div style={{ color: C.textMuted, fontSize: 12 }}>Critical Open</div>
          <div style={{ fontSize: 30, fontWeight: 700, color: "#ef4444" }}>{criticalOpen}</div>
        </div>
      </div>

      <div style={{ background: C.surface2, border: `1px solid ${C.border}`, borderRadius: 8, padding: 14, marginBottom: 18 }}>
        <h2 style={{ marginTop: 0, marginBottom: 12 }}>Create Incident</h2>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 160px", gap: 10, marginBottom: 10 }}>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Incident title"
            style={{ padding: 10, background: C.surface3, border: `1px solid ${C.border}`, color: C.text, borderRadius: 6 }}
          />
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value as typeof severity)}
            style={{ padding: 10, background: C.surface3, border: `1px solid ${C.border}`, color: C.text, borderRadius: 6 }}
          >
            <option value="critical">critical</option>
            <option value="high">high</option>
            <option value="medium">medium</option>
            <option value="low">low</option>
            <option value="informational">informational</option>
          </select>
        </div>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={4}
          placeholder="Describe incident context, impact, and indicators"
          style={{ width: "100%", boxSizing: "border-box", padding: 10, background: C.surface3, border: `1px solid ${C.border}`, color: C.text, borderRadius: 6, marginBottom: 10 }}
        />
        <button
          disabled={submitting}
          onClick={createIncident}
          style={{ padding: "8px 14px", background: C.cyan, border: "none", borderRadius: 6, color: "white", cursor: "pointer", opacity: submitting ? 0.7 : 1 }}
        >
          {submitting ? "Creating..." : "Create Incident"}
        </button>
      </div>

      <div style={{ background: C.surface2, border: `1px solid ${C.border}`, borderRadius: 8, padding: 14 }}>
        <div style={{ marginBottom: 12 }}>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ padding: 8, background: C.surface3, border: `1px solid ${C.border}`, color: C.text, borderRadius: 4 }}
          >
            <option value="">All statuses</option>
            {STATUSES.map((status) => (
              <option key={status} value={status}>{status}</option>
            ))}
          </select>
        </div>

        {error && <div style={{ color: "#fecaca", background: "#7f1d1d", padding: 10, borderRadius: 4, marginBottom: 10 }}>{error}</div>}

        {loading ? <div style={{ textAlign: "center", padding: 30 }}>Loading incidents...</div> : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  <th style={{ textAlign: "left", padding: 10 }}>Incident</th>
                  <th style={{ textAlign: "left", padding: 10 }}>Severity</th>
                  <th style={{ textAlign: "left", padding: 10 }}>Status</th>
                  <th style={{ textAlign: "left", padding: 10 }}>Created</th>
                  <th style={{ textAlign: "left", padding: 10 }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((incident) => (
                  <tr key={incident.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                    <td style={{ padding: 10 }}>
                      <div style={{ fontWeight: 600 }}>{incident.incident_key}</div>
                      <div>{incident.title}</div>
                    </td>
                    <td style={{ padding: 10 }}>{incident.severity}</td>
                    <td style={{ padding: 10 }}>{incident.status}</td>
                    <td style={{ padding: 10 }}>{new Date(incident.created_at).toLocaleString()}</td>
                    <td style={{ padding: 10 }}>
                      <select
                        value={incident.status}
                        onChange={(e) => updateStatus(incident.id, e.target.value as IncidentStatus)}
                        style={{ padding: 6, background: C.surface3, border: `1px solid ${C.border}`, color: C.text, borderRadius: 4 }}
                      >
                        {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
