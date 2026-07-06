import React from "react";
import { GlowDot } from "../../../components/widgets";
import { C, RADIUS } from "../../../styles/tokens";

interface Services {
  api:      boolean;
  database: boolean;
  cache:    boolean;
}

interface DashboardFooterProps {
  now:      Date;
  services: Services | null;
}

const SERVICE_LABELS: Array<{ key: keyof Services; label: string }> = [
  { key: "api",      label: "API"   },
  { key: "database", label: "DB"    },
  { key: "cache",    label: "Cache" },
];

export const DashboardFooter: React.FC<DashboardFooterProps> = ({ now, services }) => (
  <div style={{
    marginTop: 20,
    paddingTop: 14,
    borderTop: `1px solid ${C.border}`,
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 10,
  }}>
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <span style={{ color: C.textMuted, fontSize: 10, letterSpacing: "0.04em" }}>
        NexusGuard Security Platform
      </span>
      <span style={{
        color: C.cyan, fontSize: 10, fontWeight: 600,
        background: `${C.cyan}12`, border: `1px solid ${C.cyan}25`,
        padding: "1px 6px", borderRadius: RADIUS.sm,
      }}>
        v2.0.0
      </span>
      <span style={{ color: C.textFaint, fontSize: 10 }}>
        {now.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
        {" · "}
        {now.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
      </span>
    </div>

    <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
      <span style={{ color: C.textMuted, fontSize: 10, letterSpacing: "0.06em" }}>SERVICES</span>
      {SERVICE_LABELS.map(({ key, label }) => {
        const ok = services ? services[key] : null;
        const color = ok === null ? C.textMuted : ok ? C.green : C.red;
        return (
          <div key={key} style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <GlowDot color={color} size={5} pulse={ok === false} />
            <span style={{ color: C.textDim, fontSize: 10 }}>{label}</span>
            {ok === false && (
              <span style={{ color: C.red, fontSize: 9, fontWeight: 600 }}>DOWN</span>
            )}
          </div>
        );
      })}
    </div>
  </div>
);
