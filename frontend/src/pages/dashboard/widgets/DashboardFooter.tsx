import React from "react";
import { GlowDot } from "../../../components/widgets";
import { C, RADIUS } from "../../../styles/tokens";
import { SERVICE_STATUS } from "../constants";

interface DashboardFooterProps {
  now: Date;
}

export const DashboardFooter: React.FC<DashboardFooterProps> = ({ now }) => (
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
    {/* Left: version */}
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <span style={{ color: C.textMuted, fontSize: 10, letterSpacing: "0.04em" }}>
        Cisco Security Platform
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

    {/* Right: service health */}
    <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
      <span style={{ color: C.textMuted, fontSize: 10, letterSpacing: "0.06em" }}>
        SERVICES
      </span>
      {SERVICE_STATUS.map((svc) => (
        <div key={svc} style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <GlowDot color={C.green} size={5} pulse={false} />
          <span style={{ color: C.textDim, fontSize: 10 }}>{svc}</span>
        </div>
      ))}
    </div>
  </div>
);
