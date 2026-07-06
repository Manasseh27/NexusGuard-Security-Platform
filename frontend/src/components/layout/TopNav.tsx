import React, { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { C, ANIM, RADIUS } from "../../styles/tokens";
import { StatusPill } from "../widgets";
import { useLiveClock } from "../../hooks/useLiveClock";
import { useAuthStore } from "../../stores/authStore";
import { useAnyPermission } from "../../hooks/usePermission";

interface TopNavProps {
  activeTab:    string;
  onTabChange:  (tab: string) => void;
  activeAlerts: number;
}

interface TabDef {
  id:         string;
  label:      string;
  icon:       string;
  route:      string;
  permission: string;  // any one of these grants access
}

const ALL_TABS: TabDef[] = [
  { id: "overview",   label: "Overview",   icon: "⬡", route: "/",          permission: "monitoring:read" },
  { id: "compliance", label: "Compliance", icon: "◈", route: "/compliance", permission: "compliance:read" },
  { id: "devices",    label: "Devices",    icon: "◫", route: "/devices",    permission: "devices:read"    },
  { id: "siem",       label: "SIEM",       icon: "◉", route: "/siem",       permission: "siem:read"       },
  { id: "incidents",  label: "Incidents",  icon: "⚑", route: "/incidents",  permission: "incidents:read"  },
  { id: "threats",    label: "Threats",    icon: "◬", route: "/threats",    permission: "threats:read"    },
  { id: "ai copilot", label: "AI Copilot", icon: "◎", route: "/copilot",    permission: "ai:chat"         },
  { id: "users",      label: "Users",      icon: "◑", route: "/users",      permission: "users:read"      },
];

const ROLE_LABELS: Record<string, string> = {
  admin:            "Administrator",
  super_admin:      "Super Admin",
  soc_analyst:      "SOC Analyst",
  security_analyst: "Security Analyst",
  auditor:          "Auditor",
  viewer:           "Viewer",
  engineer:         "Engineer",
  analyst:          "Analyst",
};

const ROLE_COLORS: Record<string, string> = {
  admin:            C.red,
  super_admin:      C.red,
  soc_analyst:      C.yellow,
  security_analyst: C.cyan,
  auditor:          C.purple,
  engineer:         C.yellow,
  analyst:          C.cyan,
  viewer:           C.textMuted,
};

function UserMenu({ onClose }: { onClose: () => void }) {
  const user    = useAuthStore((s) => s.user);
  const logout  = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  const roleLabel = ROLE_LABELS[user?.role ?? ""] ?? user?.role ?? "Unknown";
  const roleColor = ROLE_COLORS[user?.role ?? ""] ?? C.textMuted;

  return (
    <div ref={ref} style={{
      position: "absolute", top: 46, right: 0, zIndex: 300,
      background: C.surface2, border: `1px solid ${C.border}`,
      borderRadius: 12, padding: "8px 0", minWidth: 200,
      boxShadow: "0 8px 32px rgba(0,0,0,0.6)",
    }}>
      {/* User info */}
      <div style={{ padding: "10px 16px 10px", borderBottom: `1px solid ${C.border}` }}>
        <div style={{ fontWeight: 600, fontSize: 14, color: C.text }}>
          {user?.username}
        </div>
        <div style={{ fontSize: 11, color: C.textMuted, marginTop: 2 }}>
          {user?.email}
        </div>
        <div style={{
          marginTop: 6, display: "inline-block",
          padding: "2px 8px", borderRadius: RADIUS.full,
          background: `${roleColor}18`, color: roleColor,
          border: `1px solid ${roleColor}40`, fontSize: 11, fontWeight: 600,
        }}>
          {roleLabel}
        </div>
      </div>

      {/* Actions */}
      <button
        onClick={handleLogout}
        style={{
          display: "block", width: "100%", textAlign: "left",
          padding: "10px 16px", background: "none", border: "none",
          color: C.red, fontSize: 13, cursor: "pointer",
          transition: `background ${ANIM.fast}`,
        }}
        onMouseEnter={(e) => { e.currentTarget.style.background = `${C.red}12`; }}
        onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}
      >
        Sign out
      </button>
    </div>
  );
}

export const TopNav: React.FC<TopNavProps> = ({ activeTab, onTabChange, activeAlerts }) => {
  const now      = useLiveClock();
  const user     = useAuthStore((s) => s.user);
  const navigate = useNavigate();
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  // Filter tabs to only those the current user has permission for.
  // Wildcard ["*"] grants all; otherwise check exact permission string.
  const hasWildcard = user?.permissions.includes("*") ?? false;
  const visibleTabs = ALL_TABS.filter((tab) =>
    hasWildcard || (user?.permissions.includes(tab.permission) ?? false)
  );

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
            NexusGuard
          </div>
          <div style={{
            color: C.cyan, fontSize: 9, letterSpacing: "0.15em",
            fontWeight: 600, textTransform: "uppercase", opacity: 0.8,
          }}>
            Platform v2.0
          </div>
        </div>
      </div>

      {/* ── Tabs (permission-filtered) ── */}
      <nav style={{ display: "flex", gap: 2, paddingLeft: 16, flex: 1, overflowX: "auto" }}>
        {visibleTabs.map((tab) => {
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => {
                onTabChange(tab.id);
                navigate(tab.route);
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
        height: "100%", position: "relative",
      }}>

        {/* Live status */}
        <StatusPill status="live" />

        {/* Clock */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
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
            cursor: "pointer",
          }}>
            <span style={{ fontSize: 10 }}>⚠</span>
            {activeAlerts} critical
          </div>
        )}

        {/* User avatar + dropdown */}
        <div style={{ position: "relative" }}>
          <div
            onClick={() => setUserMenuOpen((o) => !o)}
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

          {userMenuOpen && (
            <UserMenu onClose={() => setUserMenuOpen(false)} />
          )}
        </div>
      </div>
    </header>
  );
};
