import React from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import { Panel, CyberTooltip } from "../../../components/widgets";
import { C, RADIUS } from "../../../styles/tokens";

interface FleetStatusData {
  healthy:     number;
  drifting:    number;
  degraded:    number;
  unreachable: number;
}

interface FleetStatusPanelProps {
  data: FleetStatusData | null;
}

export const FleetStatusPanel: React.FC<FleetStatusPanelProps> = ({ data }) => {
  if (!data) {
    return (
      <Panel title="Fleet Status" accent={C.cyan}>
        <div style={{
          height: 200, display: "flex", alignItems: "center",
          justifyContent: "center", color: C.textMuted, fontSize: 12,
        }}>
          Loading fleet data…
        </div>
      </Panel>
    );
  }

  const total = data.healthy + data.drifting + data.degraded + data.unreachable;
  const healthPct = total ? Math.round((data.healthy / total) * 100) : 0;

  const chartData = [
    { name: "Healthy",     value: data.healthy,     color: C.green  },
    { name: "Drifting",    value: data.drifting,     color: C.yellow },
    { name: "Degraded",    value: data.degraded,     color: C.orange },
    { name: "Unreachable", value: data.unreachable,  color: C.red    },
  ];

  return (
    <Panel
      title="Fleet Status"
      subtitle={`${total.toLocaleString()} total`}
      accent={C.cyan}
      actions={
        <div style={{
          display: "flex", alignItems: "center", gap: 6,
          background: healthPct >= 90 ? `${C.green}12` : `${C.yellow}12`,
          border: `1px solid ${healthPct >= 90 ? C.green : C.yellow}30`,
          borderRadius: RADIUS.full,
          padding: "2px 10px",
        }}>
          <span style={{
            color: healthPct >= 90 ? C.green : C.yellow,
            fontSize: 12, fontWeight: 700, fontFamily: "monospace",
          }}>
            {healthPct}%
          </span>
          <span style={{ color: C.textMuted, fontSize: 10 }}>healthy</span>
        </div>
      }
    >
      <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
        {/* Bar chart */}
        <div style={{ flex: 1 }}>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={chartData} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={`${C.border}50`} vertical={false} />
              <XAxis
                dataKey="name"
                tick={{ fill: C.textMuted, fontSize: 9 }}
                axisLine={{ stroke: C.border }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: C.textMuted, fontSize: 9 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<CyberTooltip />} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]} barSize={32}>
                {chartData.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={entry.color}
                    style={{ filter: `drop-shadow(0 0 6px ${entry.color}50)` }}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Right: stat list */}
        <div style={{
          display: "flex", flexDirection: "column", gap: 10,
          minWidth: 110,
        }}>
          {chartData.map((item) => (
            <div key={item.name} style={{
              display: "flex", alignItems: "center",
              justifyContent: "space-between", gap: 8,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <div style={{
                  width: 8, height: 8, borderRadius: "50%",
                  background: item.color,
                  boxShadow: `0 0 5px ${item.color}`,
                  flexShrink: 0,
                }} />
                <span style={{ color: C.textDim, fontSize: 11 }}>{item.name}</span>
              </div>
              <span style={{
                color: item.color, fontWeight: 700,
                fontSize: 13, fontFamily: "monospace",
              }}>
                {item.value}
              </span>
            </div>
          ))}
          <div style={{
            borderTop: `1px solid ${C.border}`,
            paddingTop: 8, marginTop: 2,
            display: "flex", justifyContent: "space-between",
          }}>
            <span style={{ color: C.textMuted, fontSize: 11 }}>Total</span>
            <span style={{
              color: C.cyan, fontWeight: 700,
              fontSize: 13, fontFamily: "monospace",
            }}>
              {total}
            </span>
          </div>
        </div>
      </div>
    </Panel>
  );
};
