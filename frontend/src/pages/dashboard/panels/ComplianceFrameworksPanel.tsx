import React from "react";
import { Panel, ProgressBar } from "../../../components/widgets";
import { C, RADIUS } from "../../../styles/tokens";
import { FRAMEWORK_META } from "../constants";
import type { FrameworkScore } from "../../../types";

interface ComplianceFrameworksPanelProps {
  frameworks: FrameworkScore[];
  isLoading:  boolean;
}

export const ComplianceFrameworksPanel: React.FC<ComplianceFrameworksPanelProps> = ({
  frameworks, isLoading,
}) => {
  // Merge API data with display metadata
  const enriched = FRAMEWORK_META.map((meta) => {
    const live = frameworks.find((f) => f.id === meta.id);
    return {
      ...meta,
      score:        live?.avg_score ?? null,
      deviceCount:  live?.device_count ?? 0,
      hasData:      live !== undefined,
    };
  });

  const withData = enriched.filter((f) => f.hasData);
  const avgScore = withData.length
    ? withData.reduce((a, f) => a + (f.score ?? 0), 0) / withData.length
    : null;
  const atRisk = withData.filter((f) => f.score !== null && f.score < f.target).length;

  return (
    <Panel
      title="Compliance Frameworks"
      subtitle={withData.length ? `${withData.length} active` : "no data"}
      accent={C.cyan}
      actions={
        avgScore !== null ? (
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{ color: C.textMuted, fontSize: 11 }}>
              Avg:{" "}
              <span style={{ color: avgScore >= 85 ? C.green : C.yellow, fontWeight: 700, fontFamily: "monospace" }}>
                {avgScore.toFixed(1)}%
              </span>
            </span>
            {atRisk > 0 && (
              <span style={{
                color: C.orange, fontSize: 10, fontWeight: 600,
                background: `${C.orange}15`, border: `1px solid ${C.orange}30`,
                padding: "1px 7px", borderRadius: RADIUS.full,
              }}>
                {atRisk} below target
              </span>
            )}
          </div>
        ) : undefined
      }
    >
      {isLoading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {FRAMEWORK_META.map((fw) => (
            <div key={fw.id}>
              <div style={{ height: 14, background: C.surface3, borderRadius: RADIUS.sm, marginBottom: 6, width: "60%" }} />
              <div style={{ height: 5, background: C.surface3, borderRadius: RADIUS.full }} />
            </div>
          ))}
        </div>
      ) : withData.length === 0 ? (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "32px 0", gap: 8 }}>
          <div style={{ fontSize: 28, opacity: 0.3 }}>◈</div>
          <div style={{ color: C.textMuted, fontSize: 12 }}>No compliance evaluations yet</div>
          <div style={{ color: C.textFaint, fontSize: 11 }}>Evaluate devices to see framework scores</div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {enriched.map((fw) => {
            if (!fw.hasData) return null;
            const score = fw.score!;
            const belowTarget = score < fw.target;
            const gap = score - fw.target;
            return (
              <div key={fw.id}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div style={{
                      width: 8, height: 8, borderRadius: "50%",
                      background: fw.fill, boxShadow: `0 0 6px ${fw.fill}80`, flexShrink: 0,
                    }} />
                    <span style={{ color: C.text, fontWeight: 500, fontSize: 12 }}>{fw.name}</span>
                    <span style={{ color: C.textFaint, fontSize: 10 }}>({fw.deviceCount}d)</span>
                  </div>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <span style={{ color: belowTarget ? C.orange : C.green, fontSize: 10, fontWeight: 600, fontFamily: "monospace" }}>
                      {gap >= 0 ? "+" : ""}{gap.toFixed(1)}%
                    </span>
                    <span style={{ color: C.textMuted, fontSize: 10 }}>/{fw.target}%</span>
                    <span style={{
                      color: fw.fill, fontWeight: 700, fontSize: 12,
                      background: `${fw.fill}15`, border: `1px solid ${fw.fill}35`,
                      borderRadius: RADIUS.sm, padding: "1px 7px", fontFamily: "monospace",
                    }}>
                      {score.toFixed(1)}%
                    </span>
                  </div>
                </div>
                <ProgressBar value={score} target={fw.target} color={belowTarget ? C.orange : fw.fill} height={5} />
              </div>
            );
          })}
        </div>
      )}
    </Panel>
  );
};
