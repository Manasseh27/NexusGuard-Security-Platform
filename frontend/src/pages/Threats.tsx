/**
 * Threats Page
 * Threat intelligence, vulnerability management, and threat detection.
 */

import { useState, useEffect } from "react";
import { C } from "../styles/tokens";
import { threatsApi } from "../services/api";

interface Threat {
  id: string;
  indicator: string;
  severity: string;
  type: string;
  last_seen: string;
  description?: string;
}

export default function ThreatsPage() {
  const [threats, setThreats] = useState<Threat[]>([]);
  const [cves, setCVEs] = useState<Threat[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"indicators" | "cves">("indicators");
  const [filterSeverity, setFilterSeverity] = useState<string>("");

  useEffect(() => {
    fetchThreats();
  }, [activeTab, filterSeverity]);

  const fetchThreats = async () => {
    try {
      setLoading(true);
      const params = filterSeverity ? { severity: filterSeverity, limit: 100 } : { limit: 100 };

      if (activeTab === "indicators") {
        const result = await threatsApi.listIndicators(params);
        setThreats(Array.isArray(result) ? result : result?.indicators || []);
      } else {
        const result = await threatsApi.listCVEs(params);
        setCVEs(Array.isArray(result) ? result : result?.cves || []);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load threat data");
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
      default: return C.textMuted;
    }
  };

  const displayData = activeTab === "indicators" ? threats : cves;

  return (
    <div style={{ background: C.bg, minHeight: "100vh", color: C.text, padding: 24 }}>
      <h1 style={{ marginBottom: 24, fontSize: 28, fontWeight: 600 }}>Threat Intelligence</h1>

      <div style={{ display: "flex", gap: 16, marginBottom: 24 }}>
        <button
          onClick={() => setActiveTab("indicators")}
          style={{
            padding: "8px 16px",
            background: activeTab === "indicators" ? C.cyan : "transparent",
            color: C.text,
            border: `1px solid ${activeTab === "indicators" ? C.cyan : C.border}`,
            borderRadius: 4,
            cursor: "pointer",
            fontSize: 14,
          }}
        >
          Threat Indicators
        </button>
        <button
          onClick={() => setActiveTab("cves")}
          style={{
            padding: "8px 16px",
            background: activeTab === "cves" ? C.cyan : "transparent",
            color: C.text,
            border: `1px solid ${activeTab === "cves" ? C.cyan : C.border}`,
            borderRadius: 4,
            cursor: "pointer",
            fontSize: 14,
          }}
        >
          CVEs
        </button>
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
          <div style={{ textAlign: "center", padding: 40 }}>Loading threat data...</div>
        ) : displayData.length === 0 ? (
          <div style={{ textAlign: "center", padding: 40, color: C.textMuted }}>
            No threat data available
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
                  <th style={{ textAlign: "left", padding: 12, fontWeight: 600 }}>
                    {activeTab === "indicators" ? "Indicator" : "CVE ID"}
                  </th>
                  <th style={{ textAlign: "left", padding: 12, fontWeight: 600 }}>
                    {activeTab === "indicators" ? "Type" : "Title"}
                  </th>
                  <th style={{ textAlign: "left", padding: 12, fontWeight: 600 }}>Severity</th>
                  <th style={{ textAlign: "left", padding: 12, fontWeight: 600 }}>Last Seen</th>
                </tr>
              </thead>
              <tbody>
                {displayData.map((item) => (
                  <tr key={item.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                    <td style={{ padding: 12 }}>{item.indicator}</td>
                    <td style={{ padding: 12, fontSize: 12, color: C.textMuted }}>
                      {item.type || item.description || "N/A"}
                    </td>
                    <td style={{ padding: 12 }}>
                      <span style={{
                        display: "inline-block",
                        padding: "2px 6px",
                        borderRadius: 3,
                        background: getSeverityColor(item.severity),
                        color: "white",
                        fontSize: 11,
                        fontWeight: 500,
                      }}>
                        {item.severity?.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding: 12, fontSize: 12, color: C.textMuted }}>
                      {new Date(item.last_seen).toLocaleString()}
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
