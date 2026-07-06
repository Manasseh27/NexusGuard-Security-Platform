import React from "react";
import { Panel } from "../../../components/widgets";
import { C, RADIUS, SEVERITY_COLOR } from "../../../styles/tokens";
import type { ActivityItem } from "../../../types";

interface RecentActivityPanelProps {
  activity:  ActivityItem[];
  isLoading: boolean;
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

const ACTION_ICONS: Record<string, string> = {
  login:    "🔑",
  logout:   "🚪",
  create:   "✚",
  update:   "✎",
  delete:   "✕",
  evaluate: "◈",
  default:  "◎",
};

export const RecentActivityPanel: React.FC<RecentActivityPanelProps> = ({ activity, isLoading }) => (
  <Panel title="Recent Activity" subtitle="audit + incidents" accent={C.purple}>
    {isLoading ? (
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} style={{
            height: 36, background: C.surface3, borderRadius: RADIUS.sm,
            animation: "pulse 1.5s ease-in-out infinite",
            animationDelay: `${i * 0.1}s`,
          }} />
        ))}
      </div>
    ) : activity.length === 0 ? (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "32px 0", gap: 8 }}>
        <div style={{ fontSize: 28, opacity: 0.3 }}>◎</div>
        <div style={{ color: C.textMuted, fontSize: 12 }}>No recent activity</div>
      </div>
    ) : (
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {activity.map((item) => {
          const isIncident = item.type === "incident";
          const accentColor = isIncident
            ? (SEVERITY_COLOR[item.severity ?? ""] ?? C.yellow)
            : C.purple;
          const icon = isIncident
            ? "⚑"
            : (ACTION_ICONS[item.action?.split(".")[0] ?? ""] ?? ACTION_ICONS.default);

          return (
            <div key={item.id} style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "8px 10px",
              background: C.surface2,
              border: `1px solid ${C.border}`,
              borderLeft: `3px solid ${accentColor}`,
              borderRadius: RADIUS.sm,
            }}>
              <span style={{ fontSize: 13, flexShrink: 0 }}>{icon}</span>

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  color: C.text, fontSize: 12, fontWeight: 500,
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                }}>
                  {isIncident ? item.title : item.action}
                </div>
                <div style={{ display: "flex", gap: 6, alignItems: "center", marginTop: 2 }}>
                  {isIncident ? (
                    <>
                      <span style={{
                        fontSize: 10, padding: "0 5px", borderRadius: RADIUS.sm,
                        background: `${accentColor}18`, color: accentColor,
                        border: `1px solid ${accentColor}30`,
                      }}>
                        {item.severity}
                      </span>
                      <span style={{ color: C.textFaint, fontSize: 10 }}>{item.status}</span>
                    </>
                  ) : (
                    <>
                      <span style={{ color: C.textFaint, fontSize: 10 }}>{item.resource_type}</span>
                      <span style={{
                        fontSize: 10, padding: "0 5px", borderRadius: RADIUS.sm,
                        background: item.outcome === "success" ? `${C.green}15` : `${C.red}15`,
                        color: item.outcome === "success" ? C.green : C.red,
                      }}>
                        {item.outcome}
                      </span>
                    </>
                  )}
                </div>
              </div>

              <span style={{ color: C.textMuted, fontSize: 10, flexShrink: 0 }}>
                {timeAgo(item.timestamp)}
              </span>
            </div>
          );
        })}
      </div>
    )}
  </Panel>
);
