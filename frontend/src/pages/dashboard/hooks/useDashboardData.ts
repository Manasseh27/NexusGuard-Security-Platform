/**
 * Dashboard-specific hooks for data transformation and calculations.
 */

import { useMemo } from "react";
import { FRAMEWORK_META, SEVERITY_DISPLAY } from "../constants";

interface DriftEvent {
  drift_id:     string;
  severity:     string;
  acknowledged: boolean;
  [key: string]: unknown;
}

interface FleetData {
  average_compliance_score: number;
  total_devices:            number;
  healthy:                  number;
  drifting:                 number;
  unreachable:              number;
  degraded:                 number;
  fleet_health_pct:         number;
  active_drift_events:      number;
}

// Stable per-framework offsets — deterministic, no random
const RADAR_OFFSETS = [3, -5, 2, -7, 4, -9];

/** Calculate severity distribution from drift events. */
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

/** Generate radar chart data from framework metadata and fleet score. */
export function useRadarData(fleetScore: number) {
  return useMemo(
    () =>
      FRAMEWORK_META.map((f, i) => ({
        subject:  f.name,
        score:    Math.max(50, Math.min(100, Math.round(fleetScore + RADAR_OFFSETS[i % RADAR_OFFSETS.length]))),
        fullMark: 100,
      })),
    [Math.round(fleetScore / 2)] // eslint-disable-line react-hooks/exhaustive-deps
  );
}

/** Count critical unacknowledged alerts. */
export function useActiveAlerts(driftEvents: DriftEvent[]) {
  return useMemo(
    () => driftEvents.filter((d) => !d.acknowledged && d.severity === "critical").length,
    [driftEvents]
  );
}

/** Extract KPI values from fleet data. */
export function useFleetKPIs(fleet: FleetData | null) {
  return useMemo(
    () => ({
      score:              fleet?.average_compliance_score ?? 0,
      totalDevices:       fleet?.total_devices ?? 0,
      healthyDevices:     fleet?.healthy ?? 0,
      driftingDevices:    fleet?.drifting ?? 0,
      unreachableDevices: fleet?.unreachable ?? 0,
      degradedDevices:    fleet?.degraded ?? 0,
      fleetHealth:        fleet?.fleet_health_pct ?? 0,
      activeDrifts:       fleet?.active_drift_events ?? 0,
    }),
    [fleet]
  );
}
