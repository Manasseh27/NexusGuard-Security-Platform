# =============================================================================
# Cisco Security Platform — OPA Rego Compliance Policies
# Package: cisco.security.compliance.ios
# =============================================================================

package cisco.security.compliance.ios

import rego.v1

# ── Helper: config lines ───────────────────────────────────────────────────────

config_lines := split(input.running_config, "\n")

contains_line(pattern) if {
    line := config_lines[_]
    regex.match(pattern, trim_space(line))
}

# ── CIS-IOS-1.1: AAA new-model ────────────────────────────────────────────────

violations["CIS-IOS-1.1"] := {
    "rule_id":   "CIS-IOS-1.1",
    "rule_name": "Enable AAA",
    "severity":  "high",
    "finding":   "aaa new-model is not configured",
    "control":   "1.1",
} if {
    not contains_line("^aaa new-model$")
}

violations["CIS-IOS-1.1-auth"] := {
    "rule_id":   "CIS-IOS-1.1",
    "rule_name": "AAA Authentication",
    "severity":  "high",
    "finding":   "AAA authentication login policy is missing",
    "control":   "1.1",
} if {
    not contains_line("^aaa authentication login")
}

# ── CIS-IOS-1.2: Enable secret encryption ─────────────────────────────────────

violations["CIS-IOS-1.2"] := {
    "rule_id":   "CIS-IOS-1.2",
    "rule_name": "Enable Secret Encryption",
    "severity":  "critical",
    "finding":   "Cleartext enable password detected instead of enable secret",
    "control":   "1.2",
} if {
    contains_line("^enable password")
}

violations["CIS-IOS-1.2-weak"] := {
    "rule_id":   "CIS-IOS-1.2",
    "rule_name": "Enable Secret Strength",
    "severity":  "critical",
    "finding":   "Enable secret uses weak encryption (type 5 MD5); upgrade to type 8 or 9",
    "control":   "1.2",
} if {
    contains_line("^enable secret 5")
    not contains_line("^enable secret [89]")
}

# ── CIS-IOS-2.1: SSH version 2 ────────────────────────────────────────────────

violations["CIS-IOS-2.1-version"] := {
    "rule_id":   "CIS-IOS-2.1",
    "rule_name": "SSH Version 2",
    "severity":  "critical",
    "finding":   "SSH version 2 is not explicitly configured",
    "control":   "2.1",
} if {
    not contains_line("^ip ssh version 2$")
}

violations["CIS-IOS-2.1-telnet"] := {
    "rule_id":   "CIS-IOS-2.1",
    "rule_name": "Disable Telnet",
    "severity":  "critical",
    "finding":   "Telnet is permitted on VTY lines",
    "control":   "2.1",
} if {
    contains_line("transport input.*(telnet|all)")
}

violations["CIS-IOS-2.1-timeout"] := {
    "rule_id":   "CIS-IOS-2.1",
    "rule_name": "SSH Timeout",
    "severity":  "medium",
    "finding":   "SSH session timeout is not configured",
    "control":   "2.1",
} if {
    not contains_line("^ip ssh time-out")
}

# ── CIS-IOS-3.1: SNMPv3 only ─────────────────────────────────────────────────

violations["CIS-IOS-3.1"] := {
    "rule_id":   "CIS-IOS-3.1",
    "rule_name": "SNMP Version",
    "severity":  "high",
    "finding":   "SNMPv1 or SNMPv2c community string detected; use SNMPv3 only",
    "control":   "3.1",
} if {
    contains_line("^snmp-server community")
}

# ── CIS-IOS-4.1: NTP authentication ─────────────────────────────────────────

violations["CIS-IOS-4.1"] := {
    "rule_id":   "CIS-IOS-4.1",
    "rule_name": "NTP Authentication",
    "severity":  "medium",
    "finding":   "NTP authentication is not configured",
    "control":   "4.1",
} if {
    contains_line("^ntp server")
    not contains_line("^ntp authenticate")
}

# ── CIS-IOS-5.1: Logging ─────────────────────────────────────────────────────

violations["CIS-IOS-5.1"] := {
    "rule_id":   "CIS-IOS-5.1",
    "rule_name": "Logging Configuration",
    "severity":  "high",
    "finding":   "Remote syslog server is not configured",
    "control":   "5.1",
} if {
    not contains_line("^logging [0-9]")
}

violations["CIS-IOS-5.2"] := {
    "rule_id":   "CIS-IOS-5.2",
    "rule_name": "Logging Timestamps",
    "severity":  "low",
    "finding":   "Log timestamps are not configured with msec precision",
    "control":   "5.2",
} if {
    not contains_line("^service timestamps log datetime msec")
}

# ── CIS-IOS-6.1: Unused services ─────────────────────────────────────────────

violations["CIS-IOS-6.1-http"] := {
    "rule_id":   "CIS-IOS-6.1",
    "rule_name": "HTTP Server",
    "severity":  "medium",
    "finding":   "HTTP server is enabled (use HTTPS or disable)",
    "control":   "6.1",
} if {
    contains_line("^ip http server$")
    not contains_line("^no ip http server$")
}

violations["CIS-IOS-6.2-finger"] := {
    "rule_id":   "CIS-IOS-6.2",
    "rule_name": "Finger Service",
    "severity":  "low",
    "finding":   "Finger service is enabled; disable with 'no service finger'",
    "control":   "6.2",
} if {
    not contains_line("^no service finger$")
}

violations["CIS-IOS-6.3-cdp"] := {
    "rule_id":   "CIS-IOS-6.3",
    "rule_name": "CDP on External Interfaces",
    "severity":  "medium",
    "finding":   "CDP is globally enabled; disable on external/untrusted interfaces",
    "control":   "6.3",
} if {
    not contains_line("^no cdp run$")
}

# ── Result aggregation ─────────────────────────────────────────────────────────

result := {
    "compliant":        count(violations) == 0,
    "violation_count":  count(violations),
    "violations":       [v | v := violations[_]],
    "critical_count":   count([v | v := violations[_]; v.severity == "critical"]),
    "high_count":       count([v | v := violations[_]; v.severity == "high"]),
    "medium_count":     count([v | v := violations[_]; v.severity == "medium"]),
    "low_count":        count([v | v := violations[_]; v.severity == "low"]),
}
