import React, { useMemo } from "react";
import { Panel, Btn, ProgressBar } from "../../../components/widgets";
import { C, RADIUS } from "../../../styles/tokens";
import { FRAMEWORK_META } from "../constants";

interface ComplianceFrameworksPanelProps {
  fleetScore: number;
}

export const ComplianceFrameworksPanel: React.FC<ComplianceFrameworksPanelProps> = ({
  fleetScore,
}) => {
  // Stable per-framework scores derived from fleet score
  const frameworks = useMemo(() =>
    FRAMEWORK_META.map((fw, i) => {
      const offsets = [3.2, -4.1, 1.8, -6.3, 2.5, -8.7];
      const score = Math.max(50, Math.min(100, fleetScore + offsets[i % offsets.length]));
      const delta = offsets[i % offsets.length];
      return { ...fw, score: Math.round(score * 10) / 10, delta };
    }),
    [Math.round(fleetScore)] // eslint-disable-line react-hooks/exhaustive-deps
  );

  const avgScore = frameworks.reduce((a, f) => a + f.score, 0) / frameworks.length;
  const atRisk = frameworks.filter((f) => f.score < f.target).length;

  return (
    <Panel
      title="Compliance Frameworks"
      subtitle={`${frameworks.length} active`}
      accent={C.cyan}
      actions={
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ color: C.textMuted, fontSize: 11 }}>
            Avg:{" "}
            <span style={{
              color: avgScore >= 85 ? C.green : C.yellow,
              fontWeight: 700, fontFamily: "monospace",
            }}>
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
          <Btn small color={C.cyan}>Details</Btn>
        </div>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {frameworks.map((fw) => {
          const belowTarget = fw.score < fw.target;
          const gap = fw.score - fw.target;
          return (
            <div key={fw.id}>
              <div style={{
                display: "flex", justifyContent: "space-between",
                alignItems: "center", marginBottom: 6,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{
                    width: 8, height: 8, borderRadius: "50%",
                    background: fw.fill,
                    boxShadow: `0 0 6px ${fw.fill}80`,
                    flexShrink: 0,
                  }} />
                  <span style={{ color: C.text, fontWeight: 500, fontSize: 12 }}>
                    {fw.name}
                  </span>
                </div>

                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  {/* Gap indicator */}
                  <span style={{
                    color: belowTarget ? C.orange : C.green,
                    fontSize: 10, fontWeight: 600,
                    fontFamily: "monospace",
                  }}>
                    {gap >= 0 ? "+" : ""}{gap.toFixed(1)}%
                  </span>
                  {/* Target */}
                  <span style={{ color: C.textMuted, fontSize: 10 }}>
                    /{fw.target}%
                  </span>
                  {/* Score badge */}
                  <span style={{
                    color: fw.fill, fontWeight: 700, fontSize: 12,
                    background: `${fw.fill}15`,
                    border: `1px solid ${fw.fill}35`,
                    borderRadius: RADIUS.sm,
                    padding: "1px 7px",
                    fontFamily: "monospace",
                  }}>
                    {fw.score.toFixed(1)}%
                  </span>
                </div>
              </div>

              <ProgressBar
                value={fw.score}
                target={fw.target}
                color={belowTarget ? C.orange : fw.fill}
                height={5}
              />
            </div>
          );
        })}
      </div>
    </Panel>
  );
};
