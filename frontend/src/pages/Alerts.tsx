/**
 * Alerts Page
 * Active alerts and security incidents for rapid response.
 */

import { useState, useEffect } from "react";
import { C } from "../styles/tokens";
import { complianceApi } from "../services/api";
import type { DriftEvent } from "../types";

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<DriftEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterSeverity, setFilterSeverity] = useState<string>("");

  useEffect(() => {
    fetchAlerts();
  }, [filterSeverity]);

  const fetchAlerts = async () => {
    try {
      setLoading(true);
      const params = filterSeverity ? { severity: filterSeverity, limit: 100 } : { limit: 100 };
      const result = await complianceApi.activeDrift(params);
      setAlerts(Array.isArray(result) ? result : result?.drifts || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load alerts");
    } finally {
      setLoading(false);
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity?.toLowerCase()) {
      case "critical": return "#dc2626";
      case "high": return "#ea580c";
      case "medium": return "#f59e0b";
      case "low": return "#eab308";
      case "informational": return "#06b6d4";
      default: return C.textMuted;
    }
  };

  const handleAcknowledge = async (driftId: string) => {
    try {
      await complianceApi.acknowledgeDrift(driftId);
      setAlerts(alerts.filter((a) => a.drift_id !== driftId));
    } catch (err) {
      console.error("Failed to acknowledge alert:", err);
    }
  };

  const criticalCount = alerts.filter((a) => a.severity === "critical").length;
  const totalAlerts = alerts.length;

  return (
    <div style={{ background: C.bg, minHeight: "100vh", color: C.text, padding: 24 }}>
      <h1 style={{ marginBottom: 24, fontSize: 28, fontWeight: 600 }}>Active Alerts</h1>

      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
        gap: 16,
        marginBottom: 24,
      }}>
        <div style={{
          background: C.surface2,
          border: `1px solid ${C.border}`,
          borderRadius: 8,
          padding: 16,
        }}>
          <div style={{ fontSize: 12, color: C.textMuted, marginBottom: 8 }}>Total Alerts</div>
          <div style={{ fontSize: 32, fontWeight: 700, color: C.cyan }}>{totalAlerts}</div>
        </div>
        <div style={{
          background: C.surface2,
          border: `1px solid ${C.border}`,
          borderRadius: 8,
          padding: 16,
        }}>
          <div style={{ fontSize: 12, color: C.textMuted, marginBottom: 8 }}>Critical</div>
          <div style={{ fontSize: 32, fontWeight: 700, color: "#dc2626" }}>{criticalCount}</div>
        </div>
      </div>

      <div style={{
        background: C.surface2,
        border: `1px solid ${C.border}`,
        borderRadius: 8,
        padding: 16,
      }}>
        <div style={{ marginBottom: 16 }}>
          <select
            value={filterSeverity}
            onChange={(e) => setFilterSeverity(e.target.value)}
            style={{
              padding: 8,
              background: C.surface3,
              border: `1px solid ${C.border}`,
              color: C.text,
              borderRadius: 4,
              fontSize: 14,
            }}
          >
            <option value="">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        {error && (
          <div style={{
            background: "#7f1d1d",
            color: "#fecaca",
            padding: 12,
            borderRadius: 4,
            marginBottom: 16,
          }}>
            {error}
          </div>
        )}

        {loading ? (
          <div style={{ textAlign: "center", padding: 40 }}>Loading alerts...</div>
        ) : alerts.length === 0 ? (
          <div style={{ textAlign: "center", padding: 40, color: C.textMuted }}>
            No active alerts
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: 13,
            }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  <th style={{ textAlign: "left", padding: 12, fontWeight: 600 }}>Alert</th>
                  <th style={{ textAlign: "left", padding: 12, fontWeight: 600 }}>Framework</th>
                  <th style={{ textAlign: "left", padding: 12, fontWeight: 600 }}>Severity</th>
                  <th style={{ textAlign: "left", padding: 12, fontWeight: 600 }}>Device</th>
                  <th style={{ textAlign: "left", padding: 12, fontWeight: 600 }}>Detected</th>
                  <th style={{ textAlign: "center", padding: 12, fontWeight: 600 }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((alert) => (
                  <tr key={alert.drift_id} style={{ borderBottom: `1px solid ${C.border}` }}>
                    <td style={{ padding: 12 }}>{alert.rule_name}</td>
                    <td style={{ padding: 12 }}>{alert.framework}</td>
                    <td style={{ padding: 12 }}>
                      <span style={{
                        display: "inline-block",
                        padding: "2px 6px",
                        borderRadius: 3,
                        background: getSeverityColor(alert.severity),
                        color: "white",
                        fontSize: 11,
                        fontWeight: 500,
                      }}>
                        {alert.severity?.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding: 12, fontSize: 12, color: C.textMuted }}>
                      {alert.device_ip}
                    </td>
                    <td style={{ padding: 12, fontSize: 12, color: C.textMuted }}>
                      {new Date(alert.detected_at).toLocaleString()}
                    </td>
                    <td style={{ padding: 12, textAlign: "center" }}>
                      <button
                        onClick={() => handleAcknowledge(alert.drift_id)}
                        style={{
                          padding: "4px 8px",
                          background: C.cyan,
                          color: "white",
                          border: "none",
                          borderRadius: 3,
                          cursor: "pointer",
                          fontSize: 12,
                        }}
                      >
                        Acknowledge
                      </button>
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
