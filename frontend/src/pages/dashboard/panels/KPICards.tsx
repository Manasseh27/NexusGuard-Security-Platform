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
  openIncidents:      number;
  criticalIncidents:  number;
  auditEvents24h:     number;
  isLoading:          boolean;
}

interface KPICardsProps { data: KPIRow; }

function useCountUp(target: number, duration = 900): number {
  const [val, setVal] = useState(0);
  const raf = useRef<number>();
  useEffect(() => {
    const start = performance.now();
    const animate = (now: number) => {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setVal(target * eased);
      if (p < 1) raf.current = requestAnimationFrame(animate);
    };
    raf.current = requestAnimationFrame(animate);
    return () => { if (raf.current) cancelAnimationFrame(raf.current); };
  }, [target]); // eslint-disable-line react-hooks/exhaustive-deps
  return val;
}

interface KPICardProps {
  label:   string;
  value:   number;
  format?: (v: number) => string;
  sub?:    string;
  color:   string;
  icon:    string;
  alert?:  boolean;
  loading: boolean;
}

const KPICard: React.FC<KPICardProps> = ({ label, value, format, sub, color, icon, alert, loading }) => {
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
        boxShadow: hovered ? `${SHADOW.panel}, 0 0 0 1px ${color}20` : SHADOW.card,
        animation: alert ? "border-glow 2s ease-in-out infinite" : "none",
        cursor: "default",
      }}
    >
      <div style={{
        position: "absolute", inset: 0,
        background: `radial-gradient(ellipse at top left, ${color}0c 0%, transparent 60%)`,
        pointerEvents: "none",
      }} />

      <div style={{ position: "relative" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <span style={{ color: C.textMuted, fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase", fontWeight: 500 }}>
            {label}
          </span>
          <div style={{
            width: 30, height: 30, borderRadius: RADIUS.sm,
            background: `${color}15`, border: `1px solid ${color}25`,
            display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14,
          }}>
            {icon}
          </div>
        </div>

        {loading ? (
          <div style={{
            height: 36, background: `${C.surface3}`,
            borderRadius: RADIUS.sm, marginBottom: 8,
            animation: "pulse 1.5s ease-in-out infinite",
          }} />
        ) : (
          <div style={{
            color, fontSize: 30, fontWeight: 800,
            fontFamily: "'JetBrains Mono', monospace",
            letterSpacing: "-0.03em", lineHeight: 1, marginBottom: 8,
          }}>
            {display}
          </div>
        )}

        {sub && !loading && (
          <div style={{ color: C.textDim, fontSize: 11 }}>{sub}</div>
        )}
      </div>
    </div>
  );
};

export const KPICards: React.FC<KPICardsProps> = ({ data }) => (
  <div style={{
    display: "grid",
    gridTemplateColumns: "repeat(6, 1fr)",
    gap: 12,
    marginBottom: 16,
  }}>
    <KPICard
      label="Compliance Score"
      value={data.score}
      format={(v) => `${v.toFixed(1)}%`}
      color={data.score >= 85 ? C.green : data.score >= 70 ? C.yellow : C.red}
      icon="◈"
      sub={`${data.healthyDevices} devices compliant`}
      loading={data.isLoading}
    />
    <KPICard
      label="Active Devices"
      value={data.totalDevices}
      color={C.cyan}
      icon="◫"
      sub={`${data.healthyDevices} healthy · ${data.driftingDevices} drifting`}
      loading={data.isLoading}
    />
    <KPICard
      label="Drift Events"
      value={data.activeDrifts}
      color={data.activeDrifts > 0 ? C.orange : C.green}
      icon="⚡"
      sub={`${data.criticalAlerts} critical unacked`}
      alert={data.criticalAlerts > 0}
      loading={data.isLoading}
    />
    <KPICard
      label="Open Incidents"
      value={data.openIncidents}
      color={data.openIncidents > 0 ? C.yellow : C.green}
      icon="⚑"
      sub={`${data.criticalIncidents} critical open`}
      alert={data.criticalIncidents > 0}
      loading={data.isLoading}
    />
    <KPICard
      label="Critical Incidents"
      value={data.criticalIncidents}
      color={data.criticalIncidents > 0 ? C.red : C.green}
      icon="🔴"
      sub="open critical severity"
      alert={data.criticalIncidents > 0}
      loading={data.isLoading}
    />
    <KPICard
      label="Audit Events (24h)"
      value={data.auditEvents24h}
      color={C.purple}
      icon="◎"
      sub="platform activity"
      loading={data.isLoading}
    />
  </div>
);
