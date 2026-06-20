import React from "react";
import { Panel } from "../../../components/widgets";
import { ScoreRing } from "../../../components/charts/ScoreRing";
import { C } from "../../../styles/tokens";

interface ScoreRingPanelProps {
  score:       number;
  healthy:     number;
  drifting:    number;
  unreachable: number;
  total:       number;
}

export const ScoreRingPanel: React.FC<ScoreRingPanelProps> = ({
  score, healthy, drifting, unreachable, total,
}) => {
  const degraded = Math.max(0, total - healthy - drifting - unreachable);
  const items = [
    { label: "Healthy",     value: healthy,     color: C.green,  pct: total ? (healthy / total) * 100 : 0 },
    { label: "Drifting",    value: drifting,    color: C.yellow, pct: total ? (drifting / total) * 100 : 0 },
    { label: "Degraded",    value: degraded,    color: C.orange, pct: total ? (degraded / total) * 100 : 0 },
    { label: "Unreachable", value: unreachable, color: C.red,    pct: total ? (unreachable / total) * 100 : 0 },
  ];

  return (
    <Panel title="Overall Score" accent={C.green}>
      <div style={{
        display: "flex", flexDirection: "column",
        alignItems: "center", gap: 16,
      }}>
        {/* Ring */}
        <div style={{ position: "relative" }}>
          <ScoreRing score={score} size={148} />
          {/* Total devices label below ring */}
          <div style={{
            textAlign: "center", marginTop: 4,
            color: C.textMuted, fontSize: 10,
            letterSpacing: "0.06em",
          }}>
            {total.toLocaleString()} DEVICES
          </div>
        </div>

        {/* Device breakdown */}
        <div style={{ width: "100%", display: "flex", flexDirection: "column", gap: 8 }}>
          {items.map((item) => (
            <div key={item.label}>
              <div style={{
                display: "flex", justifyContent: "space-between",
                marginBottom: 4,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <div style={{
                    width: 6, height: 6, borderRadius: "50%",
                    background: item.color,
                    boxShadow: `0 0 6px ${item.color}`,
                  }} />
                  <span style={{ color: C.textDim, fontSize: 11 }}>{item.label}</span>
                </div>
                <span style={{
                  color: item.color, fontSize: 11,
                  fontWeight: 700, fontFamily: "monospace",
                }}>
                  {item.value}
                </span>
              </div>
              {/* Mini progress bar */}
              <div style={{
                height: 3, background: C.surface2,
                borderRadius: 2, overflow: "hidden",
              }}>
                <div style={{
                  height: "100%",
                  width: `${item.pct}%`,
                  background: item.color,
                  boxShadow: `0 0 6px ${item.color}60`,
                  borderRadius: 2,
                  transition: "width 1.2s cubic-bezier(0.4,0,0.2,1)",
                }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
};
