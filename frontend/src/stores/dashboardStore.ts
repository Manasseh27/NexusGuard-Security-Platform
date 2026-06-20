import { create } from "zustand";
import type { FleetStatus, DriftEvent, DeviceState } from "../types";
import { monitoringApi } from "../services/api";

interface DashboardState {
  fleet:        FleetStatus | null;
  driftEvents:  DriftEvent[];
  devices:      DeviceState[];
  isLoading:    boolean;
  lastUpdated:  Date | null;
  error:        string | null;

  fetchFleet:       () => Promise<void>;
  fetchDriftEvents: () => Promise<void>;
  fetchDevices:     () => Promise<void>;
  refreshAll:       () => Promise<void>;
  acknowledgeDrift: (driftId: string) => void;
}

export const useDashboardStore = create<DashboardState>((set, get) => ({
  fleet:       null,
  driftEvents: [],
  devices:     [],
  isLoading:   false,
  lastUpdated: null,
  error:       null,

  fetchFleet: async () => {
    try {
      const fleet = await monitoringApi.fleetStatus();
      set({ fleet, lastUpdated: new Date() });
    } catch (err: unknown) {
      set({ error: err instanceof Error ? err.message : "Failed to fetch fleet status" });
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
    set({ isLoading: true, error: null });
    await Promise.allSettled([
      get().fetchFleet(),
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
  },
}));
