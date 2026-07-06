import { create } from "zustand";
import type { DashboardSummary, DriftEvent, DeviceState } from "../types";
import { dashboardApi, monitoringApi, complianceApi } from "../services/api";

interface DashboardState {
  summary:     DashboardSummary | null;
  driftEvents: DriftEvent[];
  devices:     DeviceState[];
  isLoading:   boolean;
  lastUpdated: Date | null;
  error:       string | null;

  fetchSummary:     () => Promise<void>;
  fetchDriftEvents: () => Promise<void>;
  fetchDevices:     () => Promise<void>;
  refreshAll:       () => Promise<void>;
  acknowledgeDrift: (driftId: string) => void;
}

export const useDashboardStore = create<DashboardState>((set, get) => ({
  summary:     null,
  driftEvents: [],
  devices:     [],
  isLoading:   false,
  lastUpdated: null,
  error:       null,

  fetchSummary: async () => {
    try {
      const summary = await dashboardApi.summary() as DashboardSummary;
      set({ summary, lastUpdated: new Date(), error: null });
    } catch (err: unknown) {
      set({ error: err instanceof Error ? err.message : "Failed to fetch dashboard data" });
    }
  },

  fetchDriftEvents: async () => {
    try {
      const response = await monitoringApi.driftEvents({ limit: 50 });
      const events = Array.isArray(response)
        ? response
        : Array.isArray(response?.events)
          ? response.events
          : [];
      set({ driftEvents: events });
    } catch { /* non-fatal */ }
  },

  fetchDevices: async () => {
    try {
      const devices = await monitoringApi.listDevices({ limit: 100 });
      set({ devices });
    } catch { /* non-fatal */ }
  },

  refreshAll: async () => {
    set({ isLoading: true });
    await Promise.allSettled([
      get().fetchSummary(),
      get().fetchDriftEvents(),
      get().fetchDevices(),
    ]);
    set({ isLoading: false });
  },

  acknowledgeDrift: (driftId) => {
    set((state) => ({
      driftEvents: state.driftEvents.map((d) =>
        d.drift_id === driftId ? { ...d, acknowledged: true } : d
      ),
    }));
    // Also persist to backend
    complianceApi.acknowledgeDrift(driftId).catch(() => undefined);
  },
}));
