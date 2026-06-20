import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { C, ANIM, RADIUS } from "../../styles/tokens";
import { StatusPill } from "../widgets";
import { useLiveClock } from "../../hooks/useLiveClock";
import { useAuthStore } from "../../stores/authStore";

interface TopNavProps {
  activeTab:    string;
  onTabChange:  (tab: string) => void;
  activeAlerts: number;
}

const TABS = [
  { id: "overview",    label: "Overview",    icon: "⬡" },
  { id: "compliance",  label: "Compliance",  icon: "◈" },
  { id: "devices",     label: "Devices",     icon: "◫" },
  { id: "siem",        label: "SIEM",        icon: "◉" },
  { id: "ai copilot",  label: "AI Copilot",  icon: "◎" },
] as const;

export const TopNav: React.FC<TopNavProps> = ({ activeTab, onTabChange, activeAlerts }) => {
  const now  = useLiveClock();
  const user = useAuthStore((s) => s.user);
  const navigate = useNavigate();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const routeByTab: Record<string, string> = {
    overview: "/",
    compliance: "/compliance",
    devices: "/devices",
    siem: "/siem",
    "ai copilot": "/copilot",
  };

  const timeStr = now.toUTCString().slice(17, 25);
  const dateStr = now.toLocaleDateString("en-US", { month: "short", day: "numeric" });

  return (
    <header style={{
      background: `${C.surface}f0`,
      borderBottom: `1px solid ${C.border}`,
      backdropFilter: "blur(20px) saturate(180%)",
      WebkitBackdropFilter: "blur(20px) saturate(180%)",
      position: "sticky", top: 0, zIndex: 200,
      padding: "0 24px",
      display: "flex", alignItems: "center", gap: 0,
      height: 54,
    }}>

      {/* ── Logo ── */}
      <div style={{
        display: "flex", alignItems: "center", gap: 10,
        minWidth: 210, paddingRight: 24,
        borderRight: `1px solid ${C.border}`,
        height: "100%",
      }}>
        <div style={{
          width: 30, height: 30, borderRadius: RADIUS.sm,
          background: `linear-gradient(135deg, ${C.cyan} 0%, ${C.blue} 100%)`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 14, flexShrink: 0,
          boxShadow: `0 0 16px ${C.cyan}50, 0 2px 8px rgba(0,0,0,0.4)`,
        }}>
          🛡
        </div>
        <div>
          <div style={{
            color: C.text, fontWeight: 700, fontSize: 13,
            letterSpacing: "-0.01em", lineHeight: 1.2,
          }}>
            Cisco Security
          </div>
          <div style={{
            color: C.cyan, fontSize: 9, letterSpacing: "0.15em",
            fontWeight: 600, textTransform: "uppercase", opacity: 0.8,
          }}>
            Platform v2.0
          </div>
        </div>
      </div>

      {/* ── Tabs ── */}
      <nav style={{
        display: "flex", gap: 2, paddingLeft: 16, flex: 1,
      }}>
        {TABS.map((tab) => {
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => {
                onTabChange(tab.id);
                navigate(routeByTab[tab.id] ?? "/");
              }}
              style={{
                background: active ? `${C.cyan}12` : "transparent",
                border: "none",
                borderBottom: active ? `2px solid ${C.cyan}` : "2px solid transparent",
                borderRadius: 0,
                padding: "0 16px",
                height: 54,
                color: active ? C.cyanBright : C.textMuted,
                fontWeight: active ? 600 : 400,
                fontSize: 12,
                cursor: "pointer",
                display: "flex", alignItems: "center", gap: 6,
                transition: `all ${ANIM.fast}`,
                letterSpacing: "0.01em",
                whiteSpace: "nowrap",
              }}
              onMouseEnter={(e) => {
                if (!active) {
                  e.currentTarget.style.color = C.textSub;
                  e.currentTarget.style.background = `${C.cyan}06`;
                }
              }}
              onMouseLeave={(e) => {
                if (!active) {
                  e.currentTarget.style.color = C.textMuted;
                  e.currentTarget.style.background = "transparent";
                }
              }}
            >
              <span style={{ fontSize: 11, opacity: 0.7 }}>{tab.icon}</span>
              {tab.label}
            </button>
          );
        })}
      </nav>

      {/* ── Right side ── */}
      <div style={{
        display: "flex", alignItems: "center", gap: 12,
        paddingLeft: 16, borderLeft: `1px solid ${C.border}`,
        height: "100%",
      }}>

        {/* Live status */}
        <StatusPill status="live" />

        {/* Clock */}
        <div style={{
          display: "flex", flexDirection: "column", alignItems: "flex-end",
        }}>
          <span style={{
            color: C.text, fontSize: 12,
            fontFamily: "'JetBrains Mono', monospace",
            fontWeight: 500, letterSpacing: "0.05em",
          }}>
            {timeStr}
          </span>
          <span style={{ color: C.textMuted, fontSize: 9, letterSpacing: "0.08em" }}>
            {dateStr} UTC
          </span>
        </div>

        {/* Alert badge */}
        {activeAlerts > 0 && (
          <div style={{
            background: `${C.red}18`,
            border: `1px solid ${C.red}50`,
            color: C.redBright,
            borderRadius: RADIUS.full,
            padding: "3px 10px",
            fontSize: 11, fontWeight: 700,
            display: "flex", alignItems: "center", gap: 5,
            animation: "border-glow 2s ease-in-out infinite",
            cursor: "pointer",
          }}>
            <span style={{ fontSize: 10 }}>⚠</span>
            {activeAlerts} critical
          </div>
        )}

        {/* User avatar */}
        <div
          onClick={() => setUserMenuOpen(!userMenuOpen)}
          style={{
            width: 30, height: 30, borderRadius: "50%",
            background: `linear-gradient(135deg, ${C.purple}, ${C.blue})`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 12, cursor: "pointer",
            border: `2px solid ${C.borderMid}`,
            boxShadow: `0 0 12px ${C.purple}40`,
            color: C.text, fontWeight: 700,
            flexShrink: 0,
          }}
          title={user?.username ?? "User"}
        >
          {user?.username?.[0]?.toUpperCase() ?? "U"}
        </div>
      </div>
    </header>
  );
};
