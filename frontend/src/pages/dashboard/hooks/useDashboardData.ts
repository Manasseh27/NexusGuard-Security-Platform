/**
 * Dashboard-specific hooks — all values derived from live API data.
 * No hardcoded offsets, no Math.random(), no fake calculations.
 */

import { useMemo } from "react";
import type { DashboardSummary, FrameworkScore } from "../../../types";
import { FRAMEWORK_META, SEVERITY_DISPLAY } from "../constants";

interface DriftEvent {
  drift_id:     string;
  severity:     string;
  acknowledged: boolean;
  [key: string]: unknown;
}

/** Count drift events by severity from live drift data. */
export function useSeverityCounts(driftEvents: DriftEvent[]) {
  return useMemo(
    () =>
      SEVERITY_DISPLAY.map((s) => ({
        ...s,
        count: driftEvents.filter((d) => d.severity === s.key).length,
      })),
    [driftEvents]
  );
}

/** Build radar chart data from real per-framework scores. */
export function useRadarData(frameworks: FrameworkScore[]) {
  return useMemo(() => {
    if (!frameworks.length) {
      // Empty state — return zeroed structure so chart renders correctly
      return FRAMEWORK_META.map((f) => ({
        subject:  f.name,
        score:    0,
        fullMark: 100,
      }));
    }

    const scoreMap = Object.fromEntries(frameworks.map((f) => [f.id, f.avg_score]));

    return FRAMEWORK_META.map((f) => ({
      subject:  f.name,
      score:    scoreMap[f.id] ?? 0,
      fullMark: 100,
    }));
  }, [frameworks]);
}

/** Count critical unacknowledged alerts from live drift events. */
export function useActiveAlerts(driftEvents: DriftEvent[]) {
  return useMemo(
    () => driftEvents.filter((d) => !d.acknowledged && d.severity === "critical").length,
    [driftEvents]
  );
}

/** Extract KPI values from live fleet data. */
export function useFleetKPIs(summary: DashboardSummary | null) {
  return useMemo(
    () => ({
      score:              summary?.fleet?.average_compliance_score ?? 0,
      totalDevices:       summary?.fleet?.total_devices ?? 0,
      healthyDevices:     summary?.fleet?.healthy ?? 0,
      driftingDevices:    summary?.fleet?.drifting ?? 0,
      unreachableDevices: summary?.fleet?.unreachable ?? 0,
      degradedDevices:    summary?.fleet?.degraded ?? 0,
      fleetHealth:        summary?.fleet?.fleet_health_pct ?? 0,
      activeDrifts:       summary?.fleet?.active_drift_events ?? 0,
      openIncidents:      summary?.incidents?.open ?? 0,
      criticalIncidents:  summary?.incidents?.critical_open ?? 0,
      auditEvents24h:     summary?.audit?.last_24h ?? 0,
    }),
    [summary]
  );
}
