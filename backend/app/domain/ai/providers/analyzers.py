"""
Analyzers — specialized analysis operations (ACLs, security configs, etc.).
Each analyzer focuses on a specific domain of network security analysis.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.domain.ai.providers.models import CopilotOperation, CopilotRequest

log = structlog.get_logger(__name__)


class ACLAnalyzer:
    """Analyzes Cisco ACL configurations for security issues."""

    @staticmethod
    async def analyze(
        acl_config: str,
        device_metadata: dict[str, Any],
        process_fn,  # Injected process function
    ) -> str:
        """Analyze ACL configuration for overly permissive rules, shadowing, etc."""
        request = CopilotRequest(
            operation=CopilotOperation.ACL_ANALYZE,
            user_message=f"Analyze this ACL configuration:\n```\n{acl_config}\n```",
            context={"device": device_metadata},
        )
        response = await process_fn(request)
        log.info(
            "analyzer.acl.completed",
            device=device_metadata.get("device_id"),
            lines=len(acl_config.split("\n")),
        )
        return response.content

    @staticmethod
    def extract_rules(acl_config: str) -> list[dict[str, Any]]:
        """Parse ACL lines into structured rules."""
        rules = []
        for line in acl_config.split("\n"):
            line = line.strip()
            if not line or line.startswith("!") or line.startswith("access-list"):
                continue

            # Basic rule extraction (permit/deny/remark)
            rule = {
                "raw": line,
                "action": "permit" if "permit" in line else "deny" if "deny" in line else "remark",
            }
            rules.append(rule)

        return rules

    @staticmethod
    def identify_overly_permissive_rules(acl_config: str) -> list[str]:
        """Identify rules with excessive permissions (any/any, 0.0.0.0/0, etc.)."""
        suspicious = []
        for line in acl_config.split("\n"):
            if "any" in line and ("any" in line.split("any")[1] if "any" in line else False):
                suspicious.append(line.strip())
            if "0.0.0.0" in line and "255.255.255.255" in line:
                suspicious.append(line.strip())

        return suspicious


class SecurityConfigAnalyzer:
    """Analyzes device security configuration."""

    @staticmethod
    async def analyze(
        device_config: str,
        device_metadata: dict[str, Any],
        process_fn,  # Injected process function
    ) -> str:
        """Analyze device config for CIS benchmark compliance."""
        request = CopilotRequest(
            operation=CopilotOperation.CONFIG_ANALYZE,
            user_message=f"Perform a security assessment of this Cisco {device_metadata.get('platform', 'IOS')} configuration:\n```\n{device_config}\n```",
            context={"device": device_metadata},
        )
        response = await process_fn(request)
        log.info(
            "analyzer.security_config.completed",
            device=device_metadata.get("device_id"),
            platform=device_metadata.get("platform"),
        )
        return response.content

    @staticmethod
    def check_management_plane_security(config: str) -> dict[str, Any]:
        """Check management plane security (SSH, AAA, SNMP)."""
        findings = {
            "ssh_enabled": "ssh" in config.lower() and "transport input ssh" in config.lower(),
            "telnet_disabled": "no telnet" in config.lower() or "transport input" in config.lower(),
            "aaa_configured": "aaa" in config.lower(),
            "snmp_community_strings": "community" in config.lower(),
        }
        return findings

    @staticmethod
    def check_unnecessary_services(config: str) -> list[str]:
        """Identify unnecessary services that should be disabled."""
        dangerous_services = [
            "http server",
            "cdp run",
            "telnet",
            "snmp",
            "finger",
            "bootp",
            "source-route",
        ]
        enabled_services = []
        for service in dangerous_services:
            if service in config.lower() and f"no {service}" not in config.lower():
                enabled_services.append(service)

        return enabled_services


class ThreatAnalyzer:
    """Analyzes threats and attack vectors."""

    @staticmethod
    async def analyze_attack_path(
        network_topology: dict[str, Any],
        compliance_findings: list[dict[str, Any]],
        process_fn,  # Injected process function
    ) -> str:
        """Analyze attack paths through network topology."""
        request = CopilotRequest(
            operation=CopilotOperation.ATTACK_PATH,
            user_message="Map potential attack paths through our network based on these findings.",
            context={"topology": network_topology, "findings": compliance_findings},
        )
        response = await process_fn(request)
        log.info("analyzer.threat.attack_path_analyzed")
        return response.content

    @staticmethod
    def map_mitre_techniques(attack_description: str) -> list[str]:
        """Extract MITRE ATT&CK technique codes from analysis."""
        # Placeholder: in production, use MITRE framework or ML model
        techniques = []
        mitre_keywords = {
            "T1021": "Remote Service Session Initiation",
            "T1098": "Account Manipulation",
            "T1110": "Brute Force",
            "T1555": "Credentials from Password Stores",
            "T1190": "Exploit Public-Facing Application",
        }

        for code, name in mitre_keywords.items():
            if name.lower() in attack_description.lower():
                techniques.append(code)

        return techniques
