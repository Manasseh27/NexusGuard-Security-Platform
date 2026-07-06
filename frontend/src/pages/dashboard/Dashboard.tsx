/**
 * Enterprise Security Operations Dashboard
 * All metrics sourced from live backend APIs — no placeholder data.
 */

import { useState } from "react";
import { C } from "../../styles/tokens";
import { useFleetPolling } from "../../hooks/useFleetPolling";
import { useLiveClock } from "../../hooks/useLiveClock";
import { useDashboardStore } from "../../stores/dashboardStore";
import { useTrendData } from "../../hooks/useTrendData";
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
import { RecentActivityPanel } from "./panels/RecentActivityPanel";
import { DashboardFooter } from "./widgets/DashboardFooter";

import {
  useSeverityCounts,
  useRadarData,
  useActiveAlerts,
  useFleetKPIs,
} from "./hooks/useDashboardData";

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState("overview");
  const now = useLiveClock();

  const { fleet, driftEvents, isLoading, error, summary } = useFleetPolling(30_000);
  const acknowledgeDrift = useDashboardStore((s) => s.acknowledgeDrift);

  // All derived values from real data — no fake offsets
  const severityCounts  = useSeverityCounts(driftEvents);
  const radarData       = useRadarData(summary?.frameworks ?? []);
  const activeAlerts    = useActiveAlerts(driftEvents);
  const kpiData         = useFleetKPIs(summary);
  const trendPoints     = useTrendData(summary?.trend ?? []);

  return (
    <div style={{ background: C.bg, minHeight: "100vh", color: C.text }}>
      <GlobalStyles />

      {/* Scanline overlay */}
      <div style={{
        position: "fixed", inset: 0, pointerEvents: "none", zIndex: 9999,
        background: `repeating-linear-gradient(
          0deg, transparent, transparent 3px,
          rgba(6,182,212,0.008) 3px, rgba(6,182,212,0.008) 4px
        )`,
      }} />

      <TopNav activeTab={activeTab} onTabChange={setActiveTab} activeAlerts={activeAlerts} />

      <main style={{ padding: "16px 24px 24px", maxWidth: 1680, margin: "0 auto" }}>

        {/* Error banner */}
        {error && !isLoading && (
          <div style={{
            marginBottom: 14, padding: "12px 14px", borderRadius: 12,
            border: "1px solid rgba(248,113,113,0.35)",
            background: "rgba(127,29,29,0.22)", color: "#fecaca", fontSize: 13,
          }}>
            Dashboard data unavailable — {error}
          </div>
        )}

        {/* Live drift ticker */}
        <div style={{ marginBottom: 14 }}>
          <LiveTicker events={driftEvents.slice(0, 12)} />
        </div>

        {/* ── KPI Row — 6 live metrics ── */}
        <KPICards
          data={{
            score:              kpiData.score,
            totalDevices:       kpiData.totalDevices,
            healthyDevices:     kpiData.healthyDevices,
            driftingDevices:    kpiData.driftingDevices,
            unreachableDevices: kpiData.unreachableDevices,
            fleetHealth:        kpiData.fleetHealth,
            activeDrifts:       kpiData.activeDrifts,
            criticalAlerts:     activeAlerts,
            openIncidents:      kpiData.openIncidents,
            criticalIncidents:  kpiData.criticalIncidents,
            auditEvents24h:     kpiData.auditEvents24h,
            isLoading,
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
            score={kpiData.score}
            healthy={kpiData.healthyDevices}
            drifting={kpiData.driftingDevices}
            unreachable={kpiData.unreachableDevices}
            total={kpiData.totalDevices}
          />
          <ComplianceTrendPanel
            trend={trendPoints}
            totalDevices={kpiData.totalDevices}
            currentScore={kpiData.score}
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
          <ComplianceFrameworksPanel
            frameworks={summary?.frameworks ?? []}
            isLoading={isLoading}
          />
          <DriftEventsPanel
            events={driftEvents}
            onAcknowledge={acknowledgeDrift}
          />
        </div>

        {/* ── Row 4: Severity + Fleet Status + Recent Activity ── */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "260px 1fr 340px",
          gap: 12,
          marginBottom: 12,
        }}>
          <SeverityDistributionPanel data={severityCounts} />
          <FleetStatusPanel data={fleet} />
          <RecentActivityPanel
            activity={summary?.recent_activity ?? []}
            isLoading={isLoading}
          />
        </div>

        <DashboardFooter now={now} services={summary?.services ?? null} />
      </main>
    </div>
  );
}
