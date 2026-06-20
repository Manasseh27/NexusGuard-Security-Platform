/**
 * SIEM Events Page
 * Security information and event management, event correlation and analysis.
 */

import { useState, useEffect } from "react";
import { C } from "../styles/tokens";
import { siemApi } from "../services/api";
import type { DriftEvent } from "../types";

export default function SIEMPage() {
  const [events, setEvents] = useState<DriftEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterSeverity, setFilterSeverity] = useState<string>("");

  useEffect(() => {
    fetchEvents();
  }, [filterSeverity]);

  const fetchEvents = async () => {
    try {
      setLoading(true);
      const params = filterSeverity ? { severity: filterSeverity, limit: 100 } : { limit: 100 };
      const result = await siemApi.list(params);
      setEvents(Array.isArray(result) ? result : result?.events || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load SIEM events");
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
      case "info": return "#06b6d4";
      default: return C.textMuted;
    }
  };

  const handleCorrelate = async (eventId: string) => {
    try {
      await siemApi.correlate(eventId);
      fetchEvents();
    } catch (err) {
      console.error("Failed to correlate event:", err);
    }
  };

  return (
    <div style={{ background: C.bg, minHeight: "100vh", color: C.text, padding: 24 }}>
      <h1 style={{ marginBottom: 24, fontSize: 28, fontWeight: 600 }}>SIEM Events</h1>

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
            <option value="info">Info</option>
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
          <div style={{ textAlign: "center", padding: 40 }}>Loading SIEM events...</div>
        ) : events.length === 0 ? (
          <div style={{ textAlign: "center", padding: 40, color: C.textMuted }}>
            No SIEM events found
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
                  <th style={{ textAlign: "left", padding: 12, fontWeight: 600 }}>Rule</th>
                  <th style={{ textAlign: "left", padding: 12, fontWeight: 600 }}>Framework</th>
                  <th style={{ textAlign: "left", padding: 12, fontWeight: 600 }}>Severity</th>
                  <th style={{ textAlign: "right", padding: 12, fontWeight: 600 }}>Score Impact</th>
                  <th style={{ textAlign: "center", padding: 12, fontWeight: 600 }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.drift_id} style={{ borderBottom: `1px solid ${C.border}` }}>
                    <td style={{ padding: 12 }}>{event.rule_name}</td>
                    <td style={{ padding: 12 }}>{event.framework}</td>
                    <td style={{ padding: 12 }}>
                      <span style={{
                        display: "inline-block",
                        padding: "2px 6px",
                        borderRadius: 3,
                        background: getSeverityColor(event.severity),
                        color: "white",
                        fontSize: 11,
                        fontWeight: 500,
                      }}>
                        {event.severity?.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding: 12, textAlign: "right" }}>
                      {event.score_delta > 0 ? "+" : ""}{event.score_delta.toFixed(1)}
                    </td>
                    <td style={{ padding: 12, textAlign: "center" }}>
                      <button
                        onClick={() => handleCorrelate(event.drift_id)}
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
                        Review
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
