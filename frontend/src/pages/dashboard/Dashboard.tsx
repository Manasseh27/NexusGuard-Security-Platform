/**
 * Enterprise Security Operations Dashboard
 * Premium SOC/NOC-style layout with live compliance monitoring.
 */

import { useState } from "react";
import { C } from "../../styles/tokens";
import { useFleetPolling } from "../../hooks/useFleetPolling";
import { useLiveClock } from "../../hooks/useLiveClock";
import { useDashboardStore } from "../../stores/dashboardStore";
import { TopNav } from "../../components/layout/TopNav";
import { LiveTicker } from "../../components/widgets/LiveTicker";
import { GlobalStyles } from "../../components/widgets";

import { KPICards } from "./panels/KPICards";
import { ScoreRingPanel } from "./panels/ScoreRingPanel";
import { ComplianceTrendPanel } from "./panels/ComplianceTrendPanel";
import { FrameworkRadarPanel } from "./panels/FrameworkRadarPanel";
import { ComplianceFrameworksPanel } from "./panels/ComplianceFrameworksPanel";
import { DriftEventsPanel } from "./panels/DriftEventsPanel";
import { SeverityDistributionPanel } from "./panels/SeverityDistributionPanel";
import { FleetStatusPanel } from "./panels/FleetStatusPanel";
import { DashboardFooter } from "./widgets/DashboardFooter";

import {
  useSeverityCounts,
  useRadarData,
  useActiveAlerts,
  useFleetKPIs,
} from "./hooks/useDashboardData";

// ── Dashboard ──────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState("overview");
  const now = useLiveClock();

  const { fleet, driftEvents, isLoading, error } = useFleetPolling(15_000);
  const acknowledgeDrift = useDashboardStore((s) => s.acknowledgeDrift);

  // Derived data
  const severityCounts = useSeverityCounts(driftEvents);
  const radarData      = useRadarData(fleet?.average_compliance_score ?? 0);
  const activeAlerts   = useActiveAlerts(driftEvents);
  const kpiData        = useFleetKPIs(fleet);

  const displayScore = kpiData.score;
  const hasRealData = fleet !== null;

  return (
    <div style={{
      background: C.bg,
      minHeight: "100vh",
      color: C.text,
    }}>
      <GlobalStyles />

      {/* Subtle scanline overlay — enterprise aesthetic */}
      <div style={{
        position: "fixed", inset: 0, pointerEvents: "none", zIndex: 9999,
        background: `repeating-linear-gradient(
          0deg,
          transparent,
          transparent 3px,
          rgba(6,182,212,0.008) 3px,
          rgba(6,182,212,0.008) 4px
        )`,
      }} />

      {/* Top navigation */}
      <TopNav
        activeTab={activeTab}
        onTabChange={setActiveTab}
        activeAlerts={activeAlerts}
      />

      {/* Main content */}
      <main style={{
        padding: "16px 24px 24px",
        maxWidth: 1680,
        margin: "0 auto",
      }}>

        {!hasRealData && !isLoading && error && (
          <div style={{
            marginBottom: 14,
            padding: "12px 14px",
            borderRadius: 12,
            border: "1px solid rgba(248, 113, 113, 0.35)",
            background: "rgba(127, 29, 29, 0.22)",
            color: "#fecaca",
            fontSize: 13,
          }}>
            Live dashboard data is unavailable. {error}
          </div>
        )}

        {/* ── Live drift ticker ── */}
        <div style={{ marginBottom: 14 }}>
          <LiveTicker events={driftEvents.slice(0, 12)} />
        </div>

        {/* ── KPI Row ── */}
        <KPICards
          data={{
            score:              displayScore,
            totalDevices:       kpiData.totalDevices,
            healthyDevices:     kpiData.healthyDevices,
            driftingDevices:    kpiData.driftingDevices,
            unreachableDevices: kpiData.unreachableDevices,
            fleetHealth:        kpiData.fleetHealth,
            activeDrifts:       kpiData.activeDrifts,
            criticalAlerts:     activeAlerts,
          }}
        />

        {/* ── Row 2: Score Ring + Trend + Radar ── */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "220px 1fr 300px",
          gap: 12,
          marginBottom: 12,
        }}>
          <ScoreRingPanel
            score={displayScore}
            healthy={kpiData.healthyDevices}
            drifting={kpiData.driftingDevices}
            unreachable={kpiData.unreachableDevices}
            total={kpiData.totalDevices}
          />
          <ComplianceTrendPanel
            score={displayScore}
            totalDevices={kpiData.totalDevices}
            isLoading={isLoading}
          />
          <FrameworkRadarPanel data={radarData} />
        </div>

        {/* ── Row 3: Frameworks + Drift Events ── */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 12,
          marginBottom: 12,
        }}>
          <ComplianceFrameworksPanel fleetScore={displayScore} />
          <DriftEventsPanel
            events={driftEvents}
            onAcknowledge={acknowledgeDrift}
          />
        </div>

        {/* ── Row 4: Severity + Fleet Status ── */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "260px 1fr",
          gap: 12,
          marginBottom: 12,
        }}>
          <SeverityDistributionPanel data={severityCounts} />
          <FleetStatusPanel data={fleet} />
        </div>

        {/* ── Footer ── */}
        <DashboardFooter now={now} />
      </main>
    </div>
  );
}
