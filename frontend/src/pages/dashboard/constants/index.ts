/**
 * Dashboard configuration constants — frameworks, severity levels, display metadata.
 */

import { C } from "../../../styles/tokens";

export const FRAMEWORK_META = [
  { id: "cis", name: "CIS IOS", target: 95, fill: C.cyan },
  { id: "nist_csf", name: "NIST CSF", target: 90, fill: C.green },
  { id: "pci_dss", name: "PCI-DSS", target: 95, fill: C.yellow },
  { id: "hipaa", name: "HIPAA", target: 85, fill: C.purple },
  { id: "iso_27001", name: "ISO 27001", target: 90, fill: C.orange },
  { id: "mitre_attack", name: "MITRE", target: 80, fill: C.red },
];

export const SEVERITY_DISPLAY = [
  { name: "Critical", key: "critical", fill: C.red },
  { name: "High", key: "high", fill: C.orange },
  { name: "Medium", key: "medium", fill: C.yellow },
  { name: "Low", key: "low", fill: C.green },
];

export const SERVICE_STATUS = ["API", "Workers", "DB", "Cache"];
