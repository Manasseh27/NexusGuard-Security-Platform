import { useEffect, useRef } from "react";
import { useDashboardStore } from "../stores/dashboardStore";

/**
 * Polls the dashboard summary, drift events, and device list on mount
 * and at a configurable interval.
 */
export function useFleetPolling(intervalMs = 30_000) {
  const { summary, driftEvents, devices, isLoading, lastUpdated, error, refreshAll } =
    useDashboardStore();
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    refreshAll();
    timerRef.current = setInterval(refreshAll, intervalMs);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [intervalMs, refreshAll]);

  // Expose fleet from summary for backward compat with Dashboard.tsx
  return { fleet: summary?.fleet ?? null, driftEvents, devices, isLoading, lastUpdated, error, summary };
}
