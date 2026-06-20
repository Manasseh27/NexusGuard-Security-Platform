/**
 * Analytics Page
 * Historical trends, reporting, and security intelligence dashboards.
 */

import { useState, useEffect } from "react";
import { C } from "../styles/tokens";
import { reportsApi, complianceApi } from "../services/api";
import type { ComplianceScore } from "../types";

export default function AnalyticsPage() {
  const [reports, setReports] = useState<any[]>([]);
  const [scores, setScores] = useState<ComplianceScore[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFramework, setSelectedFramework] = useState("cis");

  useEffect(() => {
    fetchData();
  }, [selectedFramework]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [reportsData, summaryData] = await Promise.all([
        reportsApi.list({ limit: 50 }),
        complianceApi.fleetSummary(),
      ]);
      setReports(Array.isArray(reportsData) ? reportsData : reportsData?.reports || []);
      setScores(Array.isArray(summaryData) ? summaryData : summaryData?.scores || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load analytics");
    } finally {
      setLoading(false);
    }
  };

  const frameworks = ["cis", "nist_csf", "pci_dss", "iso_27001", "mitre_attack"];
  const avgScore = scores.length > 0
    ? Math.round(scores.reduce((sum, s) => sum + s.overall_score, 0) / scores.length)
    : 0;

  const handleGenerateReport = async () => {
    try {
      await reportsApi.generate("compliance_summary", selectedFramework, 24);
      fetchData();
    } catch (err) {
      console.error("Failed to generate report:", err);
    }
  };

  return (
    <div style={{ background: C.bg, minHeight: "100vh", color: C.text, padding: 24 }}>
      <h1 style={{ marginBottom: 24, fontSize: 28, fontWeight: 600 }}>Analytics & Reporting</h1>

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
          <div style={{ fontSize: 12, color: C.textMuted, marginBottom: 8 }}>Fleet Average</div>
          <div style={{ fontSize: 32, fontWeight: 700, color: C.cyan }}>{avgScore}%</div>
        </div>
        <div style={{
          background: C.surface2,
          border: `1px solid ${C.border}`,
          borderRadius: 8,
          padding: 16,
        }}>
          <div style={{ fontSize: 12, color: C.textMuted, marginBottom: 8 }}>Devices Evaluated</div>
          <div style={{ fontSize: 32, fontWeight: 700, color: C.cyan }}>{scores.length}</div>
        </div>
        <div style={{
          background: C.surface2,
          border: `1px solid ${C.border}`,
          borderRadius: 8,
          padding: 16,
        }}>
          <div style={{ fontSize: 12, color: C.textMuted, marginBottom: 8 }}>Reports Generated</div>
          <div style={{ fontSize: 32, fontWeight: 700, color: C.cyan }}>{reports.length}</div>
        </div>
      </div>

      <div style={{
        background: C.surface2,
        border: `1px solid ${C.border}`,
        borderRadius: 8,
        padding: 16,
        marginBottom: 24,
      }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Generate Report</h2>
        <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
          <select
            value={selectedFramework}
            onChange={(e) => setSelectedFramework(e.target.value)}
            style={{
              padding: 8,
              background: C.surface3,
              border: `1px solid ${C.border}`,
              color: C.text,
              borderRadius: 4,
              fontSize: 14,
            }}
          >
            {frameworks.map((f) => (
              <option key={f} value={f}>{f.replace(/_/g, " ").toUpperCase()}</option>
            ))}
          </select>
          <button
            onClick={handleGenerateReport}
            style={{
              padding: "8px 16px",
              background: C.cyan,
              color: "white",
              border: "none",
              borderRadius: 4,
              cursor: "pointer",
            }}
          >
            Generate
          </button>
        </div>
      </div>

      <div style={{
        background: C.surface2,
        border: `1px solid ${C.border}`,
        borderRadius: 8,
        padding: 16,
      }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Recent Reports</h2>

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
          <div style={{ textAlign: "center", padding: 40 }}>Loading analytics...</div>
        ) : reports.length === 0 ? (
          <div style={{ textAlign: "center", padding: 40, color: C.textMuted }}>
            No reports generated yet
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
                  <th style={{ textAlign: "left", padding: 12, fontWeight: 600 }}>Report ID</th>
                  <th style={{ textAlign: "left", padding: 12, fontWeight: 600 }}>Framework</th>
                  <th style={{ textAlign: "left", padding: 12, fontWeight: 600 }}>Generated</th>
                  <th style={{ textAlign: "center", padding: 12, fontWeight: 600 }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {reports.map((report: any) => (
                  <tr key={report.report_id} style={{ borderBottom: `1px solid ${C.border}` }}>
                    <td style={{ padding: 12, fontSize: 12 }}>{report.report_id.substring(0, 8)}...</td>
                    <td style={{ padding: 12 }}>{report.framework || "N/A"}</td>
                    <td style={{ padding: 12, fontSize: 12, color: C.textMuted }}>
                      {new Date(report.created_at).toLocaleString()}
                    </td>
                    <td style={{ padding: 12, textAlign: "center" }}>
                      <button
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
                        Download
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
