/**
 * Devices Management Page
 * Lists all managed devices with filtering, search, and device details.
 */

import { useState, useEffect } from "react";
import { C } from "../styles/tokens";
import { monitoringApi } from "../services/api";
import type { DeviceState } from "../types";

export default function DevicesPage() {
  const [devices, setDevices] = useState<DeviceState[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [filterState, setFilterState] = useState<string>("");

  useEffect(() => {
    fetchDevices();
  }, [filterState]);

  const fetchDevices = async () => {
    try {
      setLoading(true);
      const params = filterState ? { monitoring_state: filterState } : undefined;
      const result = await monitoringApi.listDevices(params);
      setDevices(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load devices");
    } finally {
      setLoading(false);
    }
  };

  const filteredDevices = devices.filter((d) =>
    searchTerm === "" ||
    d.device_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
    d.device_ip.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getStateColor = (state: string) => {
    switch (state) {
      case "healthy":
        return "#10b981";
      case "drifting":
        return "#f59e0b";
      case "degraded":
        return "#ef4444";
      case "unreachable":
        return "#6b7280";
      default:
        return C.textMuted;
    }
  };

  return (
    <div style={{ background: C.bg, minHeight: "100vh", color: C.text, padding: 24 }}>
      <h1 style={{ marginBottom: 24, fontSize: 28, fontWeight: 600 }}>Managed Devices</h1>

      <div style={{
        background: C.surface2,
        border: `1px solid ${C.border}`,
        borderRadius: 8,
        padding: 16,
        marginBottom: 24,
      }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
          <input
            type="text"
            placeholder="Search by device ID or IP address..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              padding: 12,
              background: C.surface3,
              border: `1px solid ${C.border}`,
              color: C.text,
              borderRadius: 4,
              fontSize: 14,
            }}
          />

          <select
            value={filterState}
            onChange={(e) => setFilterState(e.target.value)}
            style={{
              padding: 12,
              background: C.surface3,
              border: `1px solid ${C.border}`,
              color: C.text,
              borderRadius: 4,
              fontSize: 14,
            }}
          >
            <option value="">All States</option>
            <option value="healthy">Healthy</option>
            <option value="drifting">Drifting</option>
            <option value="degraded">Degraded</option>
            <option value="unreachable">Unreachable</option>
          </select>
        </div>

        {error && (
          <div style={{
            background: "#7f1d1d",
            color: "#fecaca",
            padding: 12,
            borderRadius: 4,
            marginBottom: 16,
          }}>
            {error}
          </div>
        )}

        {loading ? (
          <div style={{ textAlign: "center", padding: 40 }}>Loading devices...</div>
        ) : (
          <div style={{
            overflowX: "auto",
          }}>
            <table style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: 14,
            }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  <th style={{ textAlign: "left", padding: 12, fontWeight: 600 }}>Device ID</th>
                  <th style={{ textAlign: "left", padding: 12, fontWeight: 600 }}>IP Address</th>
                  <th style={{ textAlign: "left", padding: 12, fontWeight: 600 }}>Type</th>
                  <th style={{ textAlign: "left", padding: 12, fontWeight: 600 }}>State</th>
                  <th style={{ textAlign: "right", padding: 12, fontWeight: 600 }}>Score</th>
                </tr>
              </thead>
              <tbody>
                {filteredDevices.map((device) => (
                  <tr key={device.device_id} style={{ borderBottom: `1px solid ${C.border}` }}>
                    <td style={{ padding: 12 }}>{device.device_id}</td>
                    <td style={{ padding: 12 }}>{device.device_ip}</td>
                    <td style={{ padding: 12 }}>{device.device_type}</td>
                    <td style={{ padding: 12 }}>
                      <span style={{
                        display: "inline-block",
                        padding: "4px 8px",
                        borderRadius: 4,
                        background: getStateColor(device.monitoring_state),
                        color: "white",
                        fontSize: 12,
                        fontWeight: 500,
                      }}>
                        {device.monitoring_state}
                      </span>
                    </td>
                    <td style={{ padding: 12, textAlign: "right" }}>
                      {device.current_score ? `${Math.round(device.current_score)}%` : "N/A"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filteredDevices.length === 0 && (
              <div style={{ textAlign: "center", padding: 40, color: C.textMuted }}>
                No devices found
              </div>
            )}
          </div>
        )}
      </div>

      <div style={{ fontSize: 12, color: C.textMuted }}>
        Showing {filteredDevices.length} device{filteredDevices.length !== 1 ? "s" : ""}
      </div>
    </div>
  );
}
