import React, { useEffect, useRef, useState } from "react";
import { C, RADIUS, ANIM, SHADOW } from "../../../styles/tokens";

interface KPIRow {
  score:              number;
  totalDevices:       number;
  healthyDevices:     number;
  driftingDevices:    number;
  unreachableDevices: number;
  fleetHealth:        number;
  activeDrifts:       number;
  criticalAlerts:     number;
}

interface KPICardsProps { data: KPIRow; }

// Animated counter
function useCountUp(target: number, duration = 900): number {
  const [val, setVal] = useState(0);
  const raf = useRef<number>();
  useEffect(() => {
    const start = performance.now();
    const from = 0;
    const animate = (now: number) => {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setVal(from + (target - from) * eased);
      if (p < 1) raf.current = requestAnimationFrame(animate);
    };
    raf.current = requestAnimationFrame(animate);
    return () => { if (raf.current) cancelAnimationFrame(raf.current); };
  }, [target]); // eslint-disable-line react-hooks/exhaustive-deps
  return val;
}

interface KPICardProps {
  label:    string;
  value:    number;
  format?:  (v: number) => string;
  sub?:     string;
  color:    string;
  icon:     string;
  trend?:   number;
  alert?:   boolean;
}

const KPICard: React.FC<KPICardProps> = ({
  label, value, format, sub, color, icon, trend, alert,
}) => {
  const [hovered, setHovered] = useState(false);
  const animated = useCountUp(value);
  const display = format ? format(animated) : Math.round(animated).toLocaleString();

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: hovered
          ? `linear-gradient(145deg, ${C.surface2}, ${C.surfaceHover})`
          : `linear-gradient(145deg, ${C.surface}, ${C.surface2})`,
        border: `1px solid ${hovered ? C.borderMid : C.border}`,
        borderTop: `2px solid ${color}`,
        borderRadius: RADIUS.md,
        padding: "16px 18px",
        position: "relative",
        overflow: "hidden",
        transition: `all ${ANIM.normal}`,
        boxShadow: hovered
          ? `${SHADOW.panel}, 0 0 0 1px ${color}20`
          : SHADOW.card,
        animation: alert ? "border-glow 2s ease-in-out infinite" : "none",
        cursor: "default",
      }}
    >
      {/* Background glow */}
      <div style={{
        position: "absolute", inset: 0,
        background: `radial-gradient(ellipse at top left, ${color}0c 0%, transparent 60%)`,
        pointerEvents: "none",
      }} />
      {/* Top-right corner decoration */}
      <div style={{
        position: "absolute", top: -20, right: -20,
        width: 80, height: 80, borderRadius: "50%",
        background: `radial-gradient(circle, ${color}10 0%, transparent 70%)`,
        pointerEvents: "none",
      }} />

      <div style={{ position: "relative" }}>
        {/* Header */}
        <div style={{
          display: "flex", alignItems: "center",
          justifyContent: "space-between", marginBottom: 12,
        }}>
          <span style={{
            color: C.textMuted, fontSize: 10,
            letterSpacing: "0.08em", textTransform: "uppercase",
            fontWeight: 500,
          }}>
            {label}
          </span>
          <div style={{
            width: 30, height: 30, borderRadius: RADIUS.sm,
            background: `${color}15`,
            border: `1px solid ${color}25`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 14,
          }}>
            {icon}
          </div>
        </div>

        {/* Value */}
        <div style={{
          color, fontSize: 30, fontWeight: 800,
          fontFamily: "'JetBrains Mono', monospace",
          letterSpacing: "-0.03em", lineHeight: 1,
          marginBottom: 8,
        }}>
          {display}
        </div>

        {/* Sub text */}
        {sub && (
          <div style={{ color: C.textDim, fontSize: 11, marginBottom: 6 }}>{sub}</div>
        )}

        {/* Trend */}
        {trend !== undefined && (
          <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <span style={{
              color: trend >= 0 ? C.green : C.red,
              fontSize: 10, fontWeight: 700,
              background: trend >= 0 ? `${C.green}15` : `${C.red}15`,
              border: `1px solid ${trend >= 0 ? C.green : C.red}30`,
              padding: "1px 6px", borderRadius: RADIUS.sm,
            }}>
              {trend >= 0 ? "↑" : "↓"} {Math.abs(trend)}%
            </span>
            <span style={{ color: C.textMuted, fontSize: 10 }}>vs 24h</span>
          </div>
        )}
      </div>
    </div>
  );
};

export const KPICards: React.FC<KPICardsProps> = ({ data }) => (
  <div style={{
    display: "grid",
    gridTemplateColumns: "repeat(4, 1fr)",
    gap: 12,
    marginBottom: 16,
  }}>
    <KPICard
      label="Fleet Compliance Score"
      value={data.score}
      format={(v) => `${v.toFixed(1)}%`}
      color={data.score >= 85 ? C.green : data.score >= 70 ? C.yellow : C.red}
      icon="◈"
      trend={+1.2}
      sub={`${data.healthyDevices} devices compliant`}
    />
    <KPICard
      label="Monitored Devices"
      value={data.totalDevices}
      color={C.cyan}
      icon="◫"
      trend={+3}
      sub={`${data.healthyDevices} healthy · ${data.driftingDevices} drifting`}
    />
    <KPICard
      label="Active Drift Events"
      value={data.activeDrifts}
      color={data.activeDrifts > 0 ? C.orange : C.green}
      icon="⚡"
      trend={-2}
      sub={`${data.criticalAlerts} critical · ${data.unreachableDevices} unreachable`}
      alert={data.criticalAlerts > 0}
    />
    <KPICard
      label="Fleet Health"
      value={data.fleetHealth}
      format={(v) => `${v.toFixed(1)}%`}
      color={data.fleetHealth >= 90 ? C.green : data.fleetHealth >= 75 ? C.yellow : C.red}
      icon="◉"
      sub={`${data.unreachableDevices} unreachable devices`}
    />
  </div>
);
