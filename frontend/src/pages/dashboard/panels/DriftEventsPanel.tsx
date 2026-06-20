import React, { useState } from "react";
import { Panel, Btn, SeverityBadge } from "../../../components/widgets";
import { C, SEVERITY_COLOR, RADIUS, ANIM } from "../../../styles/tokens";

interface DriftEvent {
  drift_id:     string;
  device_ip:    string;
  rule_name:    string;
  rule_id:      string;
  framework:    string;
  severity:     string;
  score_delta:  number;
  acknowledged: boolean;
  detected_at:  string;
}

interface DriftEventsPanelProps {
  events:        DriftEvent[];
  onAcknowledge: (driftId: string) => void;
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m`;
  return `${Math.floor(m / 60)}h`;
}

export const DriftEventsPanel: React.FC<DriftEventsPanelProps> = ({
  events, onAcknowledge,
}) => {
  const [filter, setFilter] = useState<string>("all");
  const [hoveredRow, setHoveredRow] = useState<string | null>(null);

  const filtered = events.filter((e) =>
    filter === "all" ? true : e.severity === filter
  );

  const critCount = events.filter((e) => e.severity === "critical" && !e.acknowledged).length;
  const highCount = events.filter((e) => e.severity === "high" && !e.acknowledged).length;

  return (
    <Panel
      title="Drift Events"
      subtitle={`${events.length} active`}
      accent={C.red}
      actions={
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          {/* Filter pills */}
          {["all", "critical", "high", "medium"].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              style={{
                background: filter === f
                  ? `${SEVERITY_COLOR[f] ?? C.cyan}20`
                  : "transparent",
                border: `1px solid ${filter === f
                  ? `${SEVERITY_COLOR[f] ?? C.cyan}50`
                  : C.border}`,
                color: filter === f
                  ? (SEVERITY_COLOR[f] ?? C.cyan)
                  : C.textMuted,
                borderRadius: RADIUS.full,
                padding: "2px 9px",
                fontSize: 10, fontWeight: 600,
                cursor: "pointer",
                textTransform: "capitalize",
                transition: `all ${ANIM.fast}`,
                letterSpacing: "0.04em",
              }}
            >
              {f}
            </button>
          ))}
          <Btn small color={C.orange}>ACK All</Btn>
        </div>
      }
    >
      {/* Summary bar */}
      {(critCount > 0 || highCount > 0) && (
        <div style={{
          display: "flex", gap: 8, marginBottom: 12,
          padding: "8px 12px",
          background: `${C.red}08`,
          border: `1px solid ${C.red}25`,
          borderRadius: RADIUS.sm,
        }}>
          {critCount > 0 && (
            <span style={{ color: C.red, fontSize: 11, fontWeight: 600 }}>
              ⚠ {critCount} critical unacknowledged
            </span>
          )}
          {critCount > 0 && highCount > 0 && (
            <span style={{ color: C.border }}>·</span>
          )}
          {highCount > 0 && (
            <span style={{ color: C.orange, fontSize: 11, fontWeight: 600 }}>
              {highCount} high severity
            </span>
          )}
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {filtered.slice(0, 6).map((d) => {
          const color = SEVERITY_COLOR[d.severity] ?? C.yellow;
          const isHovered = hoveredRow === d.drift_id;
          return (
            <div
              key={d.drift_id}
              onMouseEnter={() => setHoveredRow(d.drift_id)}
              onMouseLeave={() => setHoveredRow(null)}
              style={{
                background: isHovered ? C.surfaceHover : C.surface2,
                border: `1px solid ${isHovered ? C.borderMid : C.border}`,
                borderLeft: `3px solid ${d.acknowledged ? `${color}40` : color}`,
                borderRadius: RADIUS.sm,
                padding: "9px 12px",
                display: "flex", alignItems: "center", gap: 10,
                opacity: d.acknowledged ? 0.5 : 1,
                transition: `all ${ANIM.fast}`,
                cursor: "default",
              }}
            >
              <SeverityBadge severity={d.severity} />

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  color: C.text, fontWeight: 500, fontSize: 12,
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  marginBottom: 2,
                }}>
                  {d.rule_name}
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <span style={{
                    color: C.textMuted, fontSize: 10,
                    fontFamily: "monospace",
                    background: C.surface3,
                    padding: "0 5px", borderRadius: RADIUS.sm,
                    border: `1px solid ${C.border}`,
                  }}>
                    {d.device_ip}
                  </span>
                  <span style={{
                    color: C.textFaint, fontSize: 10,
                    textTransform: "uppercase", letterSpacing: "0.05em",
                  }}>
                    {d.framework}
                  </span>
                </div>
              </div>

              <div style={{
                color: d.score_delta < 0 ? C.red : C.green,
                fontWeight: 700, fontSize: 12,
                fontFamily: "monospace",
                minWidth: 44, textAlign: "right",
              }}>
                {d.score_delta > 0 ? "+" : ""}{d.score_delta.toFixed(1)}%
              </div>

              <div style={{ color: C.textMuted, fontSize: 10, minWidth: 28, textAlign: "right" }}>
                {timeAgo(d.detected_at)}
              </div>

              <Btn
                small
                color={d.acknowledged ? C.textMuted : C.cyan}
                onClick={() => onAcknowledge(d.drift_id)}
                disabled={d.acknowledged}
              >
                {d.acknowledged ? "✓" : "ACK"}
              </Btn>
            </div>
          );
        })}

        {filtered.length === 0 && (
          <div style={{
            color: C.textMuted, textAlign: "center",
            padding: "24px 0", fontSize: 12,
          }}>
            <div style={{ fontSize: 20, marginBottom: 6 }}>✓</div>
            No {filter !== "all" ? filter : ""} drift events
          </div>
        )}

        {filtered.length > 6 && (
          <div style={{
            textAlign: "center", paddingTop: 8,
            borderTop: `1px solid ${C.border}`,
          }}>
            <Btn small color={C.cyan}>
              View all {filtered.length} events →
            </Btn>
          </div>
        )}
      </div>
    </Panel>
  );
};
