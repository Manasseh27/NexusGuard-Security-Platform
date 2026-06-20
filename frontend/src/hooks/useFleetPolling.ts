import { useEffect, useRef } from "react";
import { useDashboardStore } from "../stores/dashboardStore";

/**
 * Polls fleet status, drift events, and device list on mount and at a
 * configurable interval. Returns the store slice needed by dashboard widgets.
 */
export function useFleetPolling(intervalMs = 15_000) {
  const { fleet, driftEvents, devices, isLoading, lastUpdated, error, refreshAll } =
    useDashboardStore();
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    refreshAll();
    timerRef.current = setInterval(refreshAll, intervalMs);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [intervalMs, refreshAll]);

  return { fleet, driftEvents, devices, isLoading, lastUpdated, error };
}
