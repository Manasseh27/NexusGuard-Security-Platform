import React, { useState, useEffect } from "react";
import { C, SEVERITY_COLOR, RADIUS } from "../../styles/tokens";
import { GlowDot, SeverityBadge } from "../widgets";
import type { DriftEvent } from "../../types";

interface LiveTickerProps {
  events: DriftEvent[];
}

export const LiveTicker: React.FC<LiveTickerProps> = ({ events }) => {
  const [currentIdx, setCurrentIdx] = useState(0);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    if (!events.length) return;
    const interval = setInterval(() => {
      setVisible(false);
      setTimeout(() => {
        setCurrentIdx((i) => (i + 1) % events.length);
        setVisible(true);
      }, 200);
    }, 4000);
    return () => clearInterval(interval);
  }, [events.length]);

  if (!events.length) {
    return (
      <div style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: RADIUS.md,
        padding: "9px 16px",
        display: "flex", alignItems: "center", gap: 10,
        fontSize: 12,
      }}>
        <GlowDot color={C.green} size={6} pulse={false} />
        <span style={{ color: C.textMuted }}>No active drift events — fleet is compliant</span>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6 }}>
          <GlowDot color={C.green} size={5} />
          <span style={{ color: C.green, fontSize: 10, fontWeight: 600, letterSpacing: "0.08em" }}>
            ALL CLEAR
          </span>
        </div>
      </div>
    );
  }

  const e = events[currentIdx];
  const color = SEVERITY_COLOR[e.severity] ?? C.cyan;
  const timeAgo = (() => {
    const diff = Date.now() - new Date(e.detected_at).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    return `${Math.floor(mins / 60)}h ago`;
  })();

  return (
    <div style={{
      background: C.surface,
      border: `1px solid ${C.border}`,
      borderLeft: `3px solid ${color}`,
      borderRadius: RADIUS.md,
      padding: "9px 16px",
      display: "flex", alignItems: "center", gap: 12,
      fontSize: 12,
      overflow: "hidden",
      position: "relative",
    }}>
      {/* Ambient glow */}
      <div style={{
        position: "absolute", left: 0, top: 0, bottom: 0, width: 80,
        background: `linear-gradient(90deg, ${color}08, transparent)`,
        pointerEvents: "none",
      }} />

      <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
        <GlowDot color={C.red} size={6} />
        <span style={{
          color: C.red, fontSize: 9, fontWeight: 700,
          letterSpacing: "0.12em", textTransform: "uppercase",
        }}>
          LIVE
        </span>
      </div>

      <div style={{ width: 1, height: 14, background: C.border, flexShrink: 0 }} />

      <div style={{
        display: "flex", alignItems: "center", gap: 10, flex: 1, minWidth: 0,
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(-4px)",
        transition: "opacity 0.2s ease, transform 0.2s ease",
      }}>
        <SeverityBadge severity={e.severity} />
        <span style={{
          color: C.textDim, fontSize: 11, fontFamily: "monospace",
          background: `${C.surface2}`, border: `1px solid ${C.border}`,
          padding: "1px 7px", borderRadius: RADIUS.sm, flexShrink: 0,
        }}>
          {e.device_ip}
        </span>
        <span style={{ color: C.border, flexShrink: 0 }}>›</span>
        <span style={{
          color: C.textSub, fontSize: 12, fontWeight: 500,
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
          {e.rule_name}
        </span>
        {e.score_delta !== 0 && (
          <span style={{
            color: C.red, fontFamily: "monospace", fontSize: 11,
            fontWeight: 700, flexShrink: 0,
          }}>
            {e.score_delta > 0 ? "+" : ""}{e.score_delta.toFixed(1)}%
          </span>
        )}
      </div>

      <div style={{
        display: "flex", alignItems: "center", gap: 10,
        flexShrink: 0, marginLeft: "auto",
      }}>
        <span style={{ color: C.textMuted, fontSize: 10 }}>{timeAgo}</span>
        <div style={{
          display: "flex", gap: 3,
        }}>
          {events.slice(0, Math.min(events.length, 8)).map((_, i) => (
            <div key={i} style={{
              width: i === currentIdx ? 14 : 4,
              height: 4,
              borderRadius: 2,
              background: i === currentIdx ? color : C.border,
              transition: "all 0.3s ease",
            }} />
          ))}
        </div>
      </div>
    </div>
  );
};
