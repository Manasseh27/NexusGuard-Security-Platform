import React, { useMemo } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { Panel, CyberTooltip } from "../../../components/widgets";
import { C } from "../../../styles/tokens";
import type { TrendBucket } from "../../../types";

interface ComplianceTrendPanelProps {
  trend:        TrendBucket[];
  totalDevices: number;
  currentScore: number;
  isLoading:    boolean;
}

export const ComplianceTrendPanel: React.FC<ComplianceTrendPanelProps> = ({
  trend, totalDevices, currentScore, isLoading,
}) => {
  const stats = useMemo(() => {
    const real = trend.map((t) => t.score).filter((s): s is number => s !== null);
    if (!real.length) return null;
    return {
      min: Math.min(...real).toFixed(1),
      max: Math.max(...real).toFixed(1),
      avg: (real.reduce((a, b) => a + b, 0) / real.length).toFixed(1),
    };
  }, [trend]);

  const hasData = trend.some((t) => t.score !== null);

  return (
    <Panel
      title="Compliance Score"
      subtitle="24h trend"
      accent={C.cyan}
      actions={
        stats ? (
          <div style={{ display: "flex", gap: 10, marginRight: 4 }}>
            {[
              { label: "MIN", value: stats.min, color: C.orange },
              { label: "AVG", value: stats.avg, color: C.cyan },
              { label: "MAX", value: stats.max, color: C.green },
            ].map((s) => (
              <div key={s.label} style={{ textAlign: "center" }}>
                <div style={{ color: C.textMuted, fontSize: 9, letterSpacing: "0.08em" }}>{s.label}</div>
                <div style={{ color: s.color, fontSize: 11, fontWeight: 700, fontFamily: "monospace" }}>
                  {s.value}%
                </div>
              </div>
            ))}
          </div>
        ) : undefined
      }
    >
      {isLoading ? (
        <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", color: C.textMuted, fontSize: 12 }}>
          <div style={{ textAlign: "center" }}>
            <div style={{
              width: 24, height: 24, borderRadius: "50%",
              border: `2px solid ${C.border}`, borderTop: `2px solid ${C.cyan}`,
              animation: "spin 0.8s linear infinite", margin: "0 auto 8px",
            }} />
            Loading trend data…
          </div>
        </div>
      ) : !hasData ? (
        <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 8 }}>
          <div style={{ fontSize: 28, opacity: 0.3 }}>◈</div>
          <div style={{ color: C.textMuted, fontSize: 12 }}>No compliance data in the last 24 hours</div>
          <div style={{ color: C.textFaint, fontSize: 11 }}>Run a compliance evaluation to populate this chart</div>
        </div>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={trend} margin={{ top: 8, right: 4, left: -24, bottom: 0 }}>
              <defs>
                <linearGradient id="gradCyan" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={C.cyan} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={C.cyan} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={`${C.border}60`} vertical={false} />
              <XAxis
                dataKey="time"
                tick={{ fill: C.textMuted, fontSize: 9 }}
                axisLine={{ stroke: C.border }}
                tickLine={false}
                interval={5}
              />
              <YAxis
                domain={[60, 100]}
                tick={{ fill: C.textMuted, fontSize: 9 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<CyberTooltip />} />
              <ReferenceLine
                y={90}
                stroke={`${C.green}50`}
                strokeDasharray="4 4"
                label={{ value: "Target", fill: C.green, fontSize: 9, position: "right" }}
              />
              <Area
                type="monotone"
                dataKey="score"
                stroke={C.cyan}
                strokeWidth={2}
                fill="url(#gradCyan)"
                dot={false}
                connectNulls={false}
                activeDot={{ r: 4, fill: C.cyan, stroke: C.bg, strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>

          <div style={{
            display: "flex", justifyContent: "space-between",
            marginTop: 10, paddingTop: 10, borderTop: `1px solid ${C.border}`,
          }}>
            <span style={{ color: C.textMuted, fontSize: 11 }}>
              {totalDevices.toLocaleString()} devices monitored
            </span>
            <span style={{ color: C.cyan, fontSize: 11, fontWeight: 600, fontFamily: "monospace" }}>
              Current: {currentScore.toFixed(1)}%
            </span>
          </div>
        </>
      )}
    </Panel>
  );
};
