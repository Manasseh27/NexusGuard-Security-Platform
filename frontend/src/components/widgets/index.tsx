import React, { useState } from "react";
import { C, SEVERITY_COLOR, ANIM, RADIUS, SHADOW } from "../../styles/tokens";

// ── GlowDot ────────────────────────────────────────────────────────────────────

interface GlowDotProps { color?: string; pulse?: boolean; size?: number; }

export const GlowDot: React.FC<GlowDotProps> = ({ color = C.green, pulse = true, size = 8 }) => (
  <span style={{
    display: "inline-block", width: size, height: size, borderRadius: "50%",
    background: color,
    boxShadow: `0 0 ${size}px ${color}, 0 0 ${size * 2}px ${color}60`,
    animation: pulse ? "pulse-dot 2.4s ease-in-out infinite" : "none",
    flexShrink: 0,
  }} />
);

// ── StatusPill ─────────────────────────────────────────────────────────────────

interface StatusPillProps { status: "online" | "warning" | "offline" | "live"; label?: string; }

const STATUS_MAP = {
  online:  { color: C.green,  label: "ONLINE" },
  live:    { color: C.green,  label: "LIVE" },
  warning: { color: C.yellow, label: "WARN" },
  offline: { color: C.red,    label: "OFFLINE" },
};

export const StatusPill: React.FC<StatusPillProps> = ({ status, label }) => {
  const s = STATUS_MAP[status];
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 6,
      background: `${s.color}12`, border: `1px solid ${s.color}35`,
      borderRadius: RADIUS.full, padding: "3px 10px",
    }}>
      <GlowDot color={s.color} size={6} />
      <span style={{ color: s.color, fontSize: 10, fontWeight: 700, letterSpacing: "0.1em" }}>
        {label ?? s.label}
      </span>
    </div>
  );
};

// ── SeverityBadge ──────────────────────────────────────────────────────────────

interface SeverityBadgeProps { severity: string; size?: "sm" | "md"; }

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({ severity, size = "sm" }) => {
  const color = SEVERITY_COLOR[severity] ?? C.cyan;
  return (
    <span style={{
      color, fontWeight: 700,
      fontSize: size === "sm" ? 10 : 12,
      letterSpacing: "0.06em",
      textTransform: "uppercase",
      borderRadius: RADIUS.sm,
      padding: size === "sm" ? "2px 7px" : "3px 10px",
      background: `${color}15`,
      border: `1px solid ${color}40`,
      whiteSpace: "nowrap",
    }}>
      {severity}
    </span>
  );
};

// ── ScoreBadge ─────────────────────────────────────────────────────────────────

interface ScoreBadgeProps { score: number; }

export const ScoreBadge: React.FC<ScoreBadgeProps> = ({ score }) => {
  const color = score >= 90 ? C.green : score >= 75 ? C.yellow : score >= 60 ? C.orange : C.red;
  return (
    <span style={{
      color, fontWeight: 700, fontSize: 12,
      background: `${color}15`, border: `1px solid ${color}40`,
      borderRadius: RADIUS.sm, padding: "2px 8px",
    }}>
      {score.toFixed(1)}%
    </span>
  );
};

// ── MetricCard ─────────────────────────────────────────────────────────────────

interface MetricCardProps {
  label:   string;
  value:   string | number;
  sub?:    string;
  color?:  string;
  icon?:   React.ReactNode;
  trend?:  number;
  onClick?: () => void;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label, value, sub, color = C.cyan, icon, trend, onClick,
}) => {
  const [hovered, setHovered] = useState(false);
  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: hovered
          ? `linear-gradient(135deg, ${C.surface2} 0%, ${C.surfaceHover} 100%)`
          : `linear-gradient(135deg, ${C.surface} 0%, ${C.surface2} 100%)`,
        border: `1px solid ${hovered ? C.borderMid : C.border}`,
        borderTop: `2px solid ${color}`,
        borderRadius: RADIUS.md,
        padding: "18px 20px",
        position: "relative",
        overflow: "hidden",
        cursor: onClick ? "pointer" : "default",
        transition: `all ${ANIM.normal}`,
        boxShadow: hovered ? SHADOW.panel : SHADOW.card,
      }}
    >
      {/* Ambient glow */}
      <div style={{
        position: "absolute", inset: 0,
        background: `radial-gradient(ellipse at top left, ${color}10 0%, transparent 65%)`,
        pointerEvents: "none",
      }} />
      {/* Corner accent */}
      <div style={{
        position: "absolute", top: 0, right: 0,
        width: 60, height: 60,
        background: `radial-gradient(circle at top right, ${color}08 0%, transparent 70%)`,
        pointerEvents: "none",
      }} />

      <div style={{ position: "relative" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
          <span style={{
            color: C.textMuted, fontSize: 11,
            letterSpacing: "0.07em", textTransform: "uppercase", fontWeight: 500,
          }}>
            {label}
          </span>
          {icon && (
            <div style={{
              width: 32, height: 32, borderRadius: RADIUS.sm,
              background: `${color}15`, border: `1px solid ${color}30`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 15,
            }}>
              {icon}
            </div>
          )}
        </div>
        <div style={{
          color, fontSize: 28, fontWeight: 800,
          fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
          letterSpacing: "-0.03em", lineHeight: 1,
          marginBottom: sub ? 6 : 0,
        }}>
          {value}
        </div>
        {sub && (
          <div style={{ color: C.textDim, fontSize: 11, marginTop: 4 }}>{sub}</div>
        )}
        {trend !== undefined && (
          <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 5 }}>
            <span style={{
              color: trend >= 0 ? C.green : C.red,
              fontSize: 11, fontWeight: 700,
              background: trend >= 0 ? `${C.green}15` : `${C.red}15`,
              padding: "1px 6px", borderRadius: RADIUS.sm,
            }}>
              {trend >= 0 ? "↑" : "↓"} {Math.abs(trend)}%
            </span>
            <span style={{ color: C.textMuted, fontSize: 10 }}>24h</span>
          </div>
        )}
      </div>
    </div>
  );
};

// ── StatCard (alias for backward compat) ───────────────────────────────────────
export const StatCard = MetricCard;

// ── Panel ──────────────────────────────────────────────────────────────────────

interface PanelProps {
  title:     string;
  children:  React.ReactNode;
  actions?:  React.ReactNode;
  accent?:   string;
  style?:    React.CSSProperties;
  noPad?:    boolean;
  subtitle?: string;
}

export const Panel: React.FC<PanelProps> = ({
  title, children, actions, accent = C.cyan, style = {}, noPad, subtitle,
}) => (
  <div style={{
    background: C.surface,
    border: `1px solid ${C.border}`,
    borderRadius: RADIUS.md,
    overflow: "hidden",
    boxShadow: SHADOW.card,
    ...style,
  }}>
    <div style={{
      padding: "13px 18px",
      borderBottom: `1px solid ${C.border}`,
      display: "flex", alignItems: "center", justifyContent: "space-between",
      background: `linear-gradient(90deg, ${accent}08 0%, transparent 50%)`,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{
          width: 3, height: 18, borderRadius: 2,
          background: `linear-gradient(180deg, ${accent}, ${accent}60)`,
          boxShadow: `0 0 8px ${accent}80`,
        }} />
        <div>
          <span style={{ color: C.text, fontWeight: 600, fontSize: 13 }}>{title}</span>
          {subtitle && (
            <span style={{ color: C.textMuted, fontSize: 11, marginLeft: 8 }}>{subtitle}</span>
          )}
        </div>
      </div>
      {actions && <div style={{ display: "flex", gap: 6, alignItems: "center" }}>{actions}</div>}
    </div>
    <div style={noPad ? undefined : { padding: 18 }}>{children}</div>
  </div>
);

// ── Btn ────────────────────────────────────────────────────────────────────────

interface BtnProps {
  children:  React.ReactNode;
  color?:    string;
  onClick?:  () => void;
  small?:    boolean;
  disabled?: boolean;
  variant?:  "ghost" | "solid" | "outline";
}

export const Btn: React.FC<BtnProps> = ({
  children, color = C.cyan, onClick, small, disabled, variant = "ghost",
}) => {
  const [hovered, setHovered] = useState(false);
  const bg = variant === "solid"
    ? (hovered ? color : `${color}dd`)
    : (hovered ? `${color}25` : `${color}12`);

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: bg,
        border: `1px solid ${hovered ? color : `${color}45`}`,
        color: variant === "solid" ? "#000" : color,
        borderRadius: RADIUS.sm,
        padding: small ? "3px 10px" : "6px 14px",
        fontSize: small ? 11 : 12,
        fontWeight: 600, cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.45 : 1,
        transition: `all ${ANIM.fast}`,
        letterSpacing: "0.02em",
        boxShadow: hovered && !disabled ? `0 0 12px ${color}35` : "none",
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </button>
  );
};

// ── CyberTooltip ───────────────────────────────────────────────────────────────

interface TooltipPayload { color?: string; value: number | string; unit?: string; name?: string; }
interface CyberTooltipProps { active?: boolean; payload?: TooltipPayload[]; label?: string; }

export const CyberTooltip: React.FC<CyberTooltipProps> = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: C.surface3,
      border: `1px solid ${C.borderMid}`,
      borderRadius: RADIUS.md,
      padding: "10px 14px",
      boxShadow: `0 12px 32px rgba(0,0,0,0.7), 0 0 0 1px ${C.cyan}18`,
      backdropFilter: "blur(12px)",
    }}>
      {label && (
        <div style={{ color: C.textMuted, fontSize: 10, marginBottom: 6, letterSpacing: "0.05em" }}>
          {label}
        </div>
      )}
      {payload.map((p, i) => (
        <div key={i} style={{
          color: p.color ?? C.cyan, fontSize: 13, fontWeight: 700,
          fontFamily: "monospace",
        }}>
          {p.name && <span style={{ color: C.textDim, fontWeight: 400, marginRight: 6 }}>{p.name}</span>}
          {typeof p.value === "number" ? p.value.toFixed(1) : p.value}{p.unit ?? ""}
        </div>
      ))}
    </div>
  );
};

// ── SkeletonBlock ──────────────────────────────────────────────────────────────

interface SkeletonProps { width?: string | number; height?: number; borderRadius?: number; }

export const Skeleton: React.FC<SkeletonProps> = ({
  width = "100%", height = 16, borderRadius = RADIUS.sm,
}) => (
  <div style={{
    width, height, borderRadius,
    background: `linear-gradient(90deg, ${C.surface2} 25%, ${C.surface3} 50%, ${C.surface2} 75%)`,
    backgroundSize: "200% 100%",
    animation: "skeleton-shimmer 1.6s ease-in-out infinite",
  }} />
);

// ── Divider ────────────────────────────────────────────────────────────────────

export const Divider: React.FC<{ color?: string }> = ({ color = C.border }) => (
  <div style={{ height: 1, background: color, margin: "12px 0" }} />
);

// ── Tag ────────────────────────────────────────────────────────────────────────

interface TagProps { children: React.ReactNode; color?: string; }

export const Tag: React.FC<TagProps> = ({ children, color = C.cyan }) => (
  <span style={{
    color, fontSize: 10, fontWeight: 600, letterSpacing: "0.06em",
    textTransform: "uppercase",
    background: `${color}12`, border: `1px solid ${color}30`,
    borderRadius: RADIUS.sm, padding: "1px 6px",
  }}>
    {children}
  </span>
);

// ── ProgressBar ────────────────────────────────────────────────────────────────

interface ProgressBarProps {
  value: number;       // 0–100
  target?: number;     // optional target marker
  color?: string;
  height?: number;
  animated?: boolean;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  value, target, color = C.cyan, height = 5, animated = true,
}) => (
  <div style={{
    position: "relative", height, background: C.surface2,
    borderRadius: RADIUS.full, overflow: "visible",
  }}>
    <div style={{
      position: "absolute", left: 0, top: 0, bottom: 0,
      width: `${Math.min(value, 100)}%`,
      background: `linear-gradient(90deg, ${color}80, ${color})`,
      boxShadow: `0 0 8px ${color}50`,
      borderRadius: RADIUS.full,
      transition: animated ? `width 1.2s cubic-bezier(0.4,0,0.2,1)` : "none",
    }} />
    {target !== undefined && (
      <div style={{
        position: "absolute", top: -3, bottom: -3,
        left: `${target}%`, width: 2,
        background: `${C.textMuted}70`,
        borderRadius: 1,
      }} />
    )}
  </div>
);

// ── Inline global styles injector ─────────────────────────────────────────────

export const GlobalStyles: React.FC = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background: ${C.bg};
      color: ${C.text};
      font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }

    ::-webkit-scrollbar { width: 4px; height: 4px; }
    ::-webkit-scrollbar-track { background: ${C.surface}; }
    ::-webkit-scrollbar-thumb { background: ${C.borderMid}; border-radius: 2px; }
    ::-webkit-scrollbar-thumb:hover { background: ${C.borderGlow}; }

    @keyframes pulse-dot {
      0%, 100% { opacity: 1; transform: scale(1); }
      50%       { opacity: 0.5; transform: scale(1.4); }
    }
    @keyframes glow-pulse {
      0%, 100% { box-shadow: 0 0 8px var(--glow-color, ${C.cyan})30; }
      50%       { box-shadow: 0 0 20px var(--glow-color, ${C.cyan})60; }
    }
    @keyframes skeleton-shimmer {
      0%   { background-position: 200% 0; }
      100% { background-position: -200% 0; }
    }
    @keyframes ticker-scroll {
      0%   { transform: translateX(0); }
      100% { transform: translateX(-50%); }
    }
    @keyframes fade-in-up {
      from { opacity: 0; transform: translateY(8px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes count-up {
      from { opacity: 0; transform: translateY(4px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes scanline {
      0%   { transform: translateY(-100vh); }
      100% { transform: translateY(100vh); }
    }
    @keyframes border-glow {
      0%, 100% { border-color: ${C.red}40; }
      50%       { border-color: ${C.red}90; }
    }
    @keyframes spin {
      from { transform: rotate(0deg); }
      to   { transform: rotate(360deg); }
    }
  `}</style>
);
