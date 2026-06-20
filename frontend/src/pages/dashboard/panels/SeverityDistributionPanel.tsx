import React from "react";
import { Panel } from "../../../components/widgets";
import { C, RADIUS } from "../../../styles/tokens";

interface SeverityCount {
  name:  string;
  key:   string;
  fill:  string;
  count: number;
}

interface SeverityDistributionPanelProps {
  data: SeverityCount[];
}

export const SeverityDistributionPanel: React.FC<SeverityDistributionPanelProps> = ({ data }) => {
  const total = data.reduce((a, d) => a + d.count, 0);

  return (
    <Panel title="Finding Severity" accent={C.orange}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {data.map((item) => {
          const pct = total > 0 ? (item.count / total) * 100 : 0;
          return (
            <div key={item.key}>
              <div style={{
                display: "flex", justifyContent: "space-between",
                alignItems: "center", marginBottom: 5,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                  <div style={{
                    width: 8, height: 8, borderRadius: "50%",
                    background: item.fill,
                    boxShadow: `0 0 6px ${item.fill}`,
                  }} />
                  <span style={{ color: C.textDim, fontSize: 12 }}>{item.name}</span>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <span style={{ color: C.textMuted, fontSize: 10 }}>
                    {pct.toFixed(0)}%
                  </span>
                  <span style={{
                    color: item.fill, fontWeight: 700,
                    fontSize: 14, fontFamily: "monospace",
                    minWidth: 28, textAlign: "right",
                  }}>
                    {item.count}
                  </span>
                </div>
              </div>

              {/* Progress bar */}
              <div style={{
                height: 6, background: C.surface2,
                borderRadius: RADIUS.full, overflow: "hidden",
              }}>
                <div style={{
                  height: "100%",
                  width: `${pct}%`,
                  background: `linear-gradient(90deg, ${item.fill}70, ${item.fill})`,
                  boxShadow: `0 0 8px ${item.fill}50`,
                  borderRadius: RADIUS.full,
                  transition: "width 1.2s cubic-bezier(0.4,0,0.2,1)",
                }} />
              </div>
            </div>
          );
        })}

        {/* Total */}
        <div style={{
          borderTop: `1px solid ${C.border}`,
          paddingTop: 10, marginTop: 2,
          display: "flex", justifyContent: "space-between",
          alignItems: "center",
        }}>
          <span style={{ color: C.textMuted, fontSize: 11 }}>Total findings</span>
          <span style={{
            color: C.text, fontWeight: 700,
            fontSize: 16, fontFamily: "monospace",
          }}>
            {total}
          </span>
        </div>
      </div>
    </Panel>
  );
};
