/**
 * Compliance Page
 * Framework compliance scores, detailed results, and exception management.
 */

import { useState, useEffect } from "react";
import { C } from "../styles/tokens";
import { complianceApi } from "../services/api";
import type { ComplianceScore, DriftEvent } from "../types";

export default function CompliancePage() {
  const [scores, setScores] = useState<ComplianceScore[]>([]);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [drifts, setDrifts] = useState<DriftEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"scores" | "drifts">("scores");
  const [filterFramework, setFilterFramework] = useState<string>("");

  useEffect(() => {
    fetchData();
  }, [filterFramework]);

  const fetchData = async () => {
    try {
      setLoading(true);
      
      if (activeTab === "scores") {
        const summary = await complianceApi.fleetSummary();
        setScores(Array.isArray(summary) ? summary : []);
      } else {
        const params = filterFramework ? { framework: filterFramework } : undefined;
        const driftData = await complianceApi.activeDrift(params);
        setDrifts(driftData?.drifts || []);
      }
      
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  const handleAcknowledgeDrift = async (driftId: string) => {
    try {
      await complianceApi.acknowledgeDrift(driftId);
      setDrifts(drifts.filter((d) => d.drift_id !== driftId));
    } catch (err) {
      console.error("Failed to acknowledge drift:", err);
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "critical":
        return "#dc2626";
      case "high":
        return "#ea580c";
      case "medium":
        return "#f59e0b";
      case "low":
        return "#eab308";
      case "informational":
        return "#06b6d4";
      default:
        return C.textMuted;
    }
  };

  return (
    <div style={{ background: C.bg, minHeight: "100vh", color: C.text, padding: 24 }}>
      <h1 style={{ marginBottom: 24, fontSize: 28, fontWeight: 600 }}>Compliance Management</h1>

      <div style={{ display: "flex", gap: 16, marginBottom: 24 }}>
        <button
          onClick={() => setActiveTab("scores")}
          style={{
            padding: "8px 16px",
            background: activeTab === "scores" ? C.cyan : "transparent",
            color: C.text,
            border: `1px solid ${activeTab === "scores" ? C.cyan : C.border}`,
            borderRadius: 4,
            cursor: "pointer",
            fontSize: 14,
          }}
        >
          Framework Scores
        </button>
        <button
          onClick={() => setActiveTab("drifts")}
          style={{
            padding: "8px 16px",
            background: activeTab === "drifts" ? C.cyan : "transparent",
            color: C.text,
            border: `1px solid ${activeTab === "drifts" ? C.cyan : C.border}`,
            borderRadius: 4,
            cursor: "pointer",
            fontSize: 14,
          }}
        >
          Active Drifts
        </button>
      </div>

      <div style={{
        background: C.surface2,
        border: `1px solid ${C.border}`,
        borderRadius: 8,
        padding: 16,
      }}>
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
          <div style={{ textAlign: "center", padding: 40 }}>Loading compliance data...</div>
        ) : activeTab === "scores" ? (
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Framework Scores</h2>
            {scores.length === 0 ? (
              <div style={{ textAlign: "center", padding: 40, color: C.textMuted }}>
                No compliance scores available
              </div>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 16 }}>
                {scores.map((score) => (
                  <div key={`${score.device_id}-${score.framework}`} style={{
                    background: C.surface3,
                    border: `1px solid ${C.border}`,
                    borderRadius: 6,
                    padding: 16,
                  }}>
                    <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>
                      {score.framework.toUpperCase()}
                    </h3>
                    <div style={{ fontSize: 24, fontWeight: 700, color: C.cyan, marginBottom: 8 }}>
                      {Math.round(score.overall_score)}%
                    </div>
                    <div style={{ fontSize: 12, color: C.textMuted, marginBottom: 12 }}>
                      <div>Weighted: {Math.round(score.weighted_score)}%</div>
                      <div>Pass: {score.pass_count} | Fail: {score.fail_count} | Error: {score.error_count}</div>
                    </div>
                    <div style={{
                      background: `rgba(6, 182, 212, 0.1)`,
                      borderRadius: 4,
                      height: 6,
                      overflow: "hidden",
                    }}>
                      <div style={{
                        background: C.cyan,
                        height: "100%",
                        width: `${score.overall_score}%`,
                      }} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div>
            <div style={{ marginBottom: 16 }}>
              <select
                value={filterFramework}
                onChange={(e) => setFilterFramework(e.target.value)}
                style={{
                  padding: 8,
                  background: C.surface3,
                  border: `1px solid ${C.border}`,
                  color: C.text,
                  borderRadius: 4,
                  fontSize: 14,
                }}
              >
                <option value="">All Frameworks</option>
                <option value="cis">CIS</option>
                <option value="nist_csf">NIST CSF</option>
                <option value="pci_dss">PCI DSS</option>
              </select>
            </div>

            <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Active Drift Events</h2>
            {drifts.length === 0 ? (
              <div style={{ textAlign: "center", padding: 40, color: C.textMuted }}>
                No active drift events
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
                      <th style={{ textAlign: "right", padding: 12, fontWeight: 600 }}>Score Delta</th>
                      <th style={{ textAlign: "center", padding: 12, fontWeight: 600 }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {drifts.map((drift) => (
                      <tr key={drift.drift_id} style={{ borderBottom: `1px solid ${C.border}` }}>
                        <td style={{ padding: 12 }}>{drift.rule_name}</td>
                        <td style={{ padding: 12 }}>{drift.framework}</td>
                        <td style={{ padding: 12 }}>
                          <span style={{
                            display: "inline-block",
                            padding: "2px 6px",
                            borderRadius: 3,
                            background: getSeverityColor(drift.severity),
                            color: "white",
                            fontSize: 11,
                            fontWeight: 500,
                          }}>
                            {drift.severity.toUpperCase()}
                          </span>
                        </td>
                        <td style={{ padding: 12, textAlign: "right" }}>
                          {drift.score_delta > 0 ? "+" : ""}{drift.score_delta.toFixed(1)}
                        </td>
                        <td style={{ padding: 12, textAlign: "center" }}>
                          <button
                            onClick={() => handleAcknowledgeDrift(drift.drift_id)}
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
        )}
      </div>
    </div>
  );
}
