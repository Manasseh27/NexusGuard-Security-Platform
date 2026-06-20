"""
Enterprise Compliance Engine — Domain Layer
Implements: policy inheritance, weighted scoring, dynamic rule execution,
policy versioning, control grouping, rule chaining, exception workflows,
OPA integration, and multi-framework support (CIS, NIST, ISO27001, PCI-DSS, HIPAA, MITRE).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum, auto
from typing import Any, Protocol
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel, Field

log = structlog.get_logger(__name__)


# ── Enumerations ───────────────────────────────────────────────────────────────

class ComplianceFramework(str, Enum):
    CIS = "cis"
    NIST_CSF = "nist_csf"
    NIST_800_53 = "nist_800_53"
    ISO_27001 = "iso_27001"
    PCI_DSS = "pci_dss"
    HIPAA = "hipaa"
    MITRE_ATTACK = "mitre_attack"
    SOC2 = "soc2"
    CUSTOM = "custom"


class RuleSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class RuleResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    ERROR = "error"
    SKIPPED = "skipped"
    EXCEPTION = "exception"


class RemediationPriority(str, Enum):
    IMMEDIATE = "immediate"    # Critical findings — remediate within 24h
    URGENT = "urgent"          # High findings — remediate within 7d
    STANDARD = "standard"      # Medium findings — remediate within 30d
    PLANNED = "planned"        # Low findings — include in next cycle


SEVERITY_WEIGHTS: dict[RuleSeverity, Decimal] = {
    RuleSeverity.CRITICAL: Decimal("10.0"),
    RuleSeverity.HIGH: Decimal("7.5"),
    RuleSeverity.MEDIUM: Decimal("5.0"),
    RuleSeverity.LOW: Decimal("2.5"),
    RuleSeverity.INFORMATIONAL: Decimal("0.5"),
}

SEVERITY_TO_PRIORITY: dict[RuleSeverity, RemediationPriority] = {
    RuleSeverity.CRITICAL: RemediationPriority.IMMEDIATE,
    RuleSeverity.HIGH: RemediationPriority.URGENT,
    RuleSeverity.MEDIUM: RemediationPriority.STANDARD,
    RuleSeverity.LOW: RemediationPriority.PLANNED,
    RuleSeverity.INFORMATIONAL: RemediationPriority.PLANNED,
}


# ── Domain Models ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RuleContext:
    """Immutable execution context passed to each rule evaluator."""
    device_id: UUID
    device_config: dict[str, Any]
    device_metadata: dict[str, Any]
    framework: ComplianceFramework
    baseline_config: dict[str, Any] | None = None
    previous_results: list["RuleEvaluationResult"] = field(default_factory=list)


@dataclass
class RuleEvaluationResult:
    rule_id: str
    rule_name: str
    result: RuleResult
    severity: RuleSeverity
    framework: ComplianceFramework
    control_id: str
    score: Decimal
    findings: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    remediation_steps: list[str] = field(default_factory=list)
    remediation_priority: RemediationPriority = RemediationPriority.PLANNED
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    execution_ms: int = 0
    chained_from: str | None = None

    @property
    def passed(self) -> bool:
        return self.result in (RuleResult.PASS, RuleResult.EXCEPTION)

    @property
    def failed(self) -> bool:
        return self.result in (RuleResult.FAIL, RuleResult.ERROR)


@dataclass
class ComplianceReport:
    report_id: UUID = field(default_factory=uuid4)
    device_id: UUID = field(default_factory=uuid4)
    framework: ComplianceFramework = ComplianceFramework.CIS
    overall_score: Decimal = Decimal("0")
    weighted_score: Decimal = Decimal("0")
    max_possible_score: Decimal = Decimal("0")
    pass_count: int = 0
    fail_count: int = 0
    warn_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    exception_count: int = 0
    results: list[RuleEvaluationResult] = field(default_factory=list)
    control_summaries: dict[str, "ControlSummary"] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    baseline_delta: Decimal | None = None
    previous_score: Decimal | None = None

    @property
    def compliance_percentage(self) -> float:
        if self.max_possible_score == 0:
            return 0.0
        return float((self.weighted_score / self.max_possible_score) * 100)

    @property
    def critical_failures(self) -> list[RuleEvaluationResult]:
        return [r for r in self.results if r.failed and r.severity == RuleSeverity.CRITICAL]

    @property
    def content_hash(self) -> str:
        data = json.dumps({
            "device_id": str(self.device_id),
            "framework": self.framework.value,
            "score": str(self.overall_score),
            "results": [r.rule_id for r in self.results],
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()


@dataclass
class ControlSummary:
    control_id: str
    control_name: str
    framework: ComplianceFramework
    rules_passed: int = 0
    rules_failed: int = 0
    rules_total: int = 0
    weighted_score: Decimal = Decimal("0")
    max_score: Decimal = Decimal("0")


# ── Rule Interface ─────────────────────────────────────────────────────────────

class ComplianceRule(ABC):
    """Abstract base for all compliance rules. Subclass to implement a check."""

    rule_id: str
    rule_name: str
    description: str
    framework: ComplianceFramework
    control_id: str
    severity: RuleSeverity
    remediation_steps: list[str] = []
    requires_rules: list[str] = []  # Rule chaining: must-pass before evaluating this

    @abstractmethod
    async def evaluate(self, context: RuleContext) -> RuleEvaluationResult:
        """Evaluate this rule against the provided context."""
        ...

    def _make_result(
        self,
        result: RuleResult,
        findings: list[str] | None = None,
        evidence: dict[str, Any] | None = None,
        execution_ms: int = 0,
    ) -> RuleEvaluationResult:
        return RuleEvaluationResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            result=result,
            severity=self.severity,
            framework=self.framework,
            control_id=self.control_id,
            score=SEVERITY_WEIGHTS[self.severity] if result in (RuleResult.PASS, RuleResult.EXCEPTION) else Decimal("0"),
            findings=findings or [],
            evidence=evidence or {},
            remediation_steps=self.remediation_steps,
            remediation_priority=SEVERITY_TO_PRIORITY[self.severity],
            execution_ms=execution_ms,
        )


# ── Built-in CIS Rules ─────────────────────────────────────────────────────────

class CISRule_1_1_EnableAAA(ComplianceRule):
    """CIS IOS Level 1 — 1.1 Enable AAA."""
    rule_id = "CIS-IOS-1.1"
    rule_name = "Enable AAA Authentication"
    description = "AAA must be enabled for centralized authentication, authorization, and accounting."
    framework = ComplianceFramework.CIS
    control_id = "1.1"
    severity = RuleSeverity.HIGH
    remediation_steps = [
        "Enter global configuration mode",
        "Execute: aaa new-model",
        "Configure AAA authentication: aaa authentication login default group tacacs+ local",
        "Configure AAA authorization: aaa authorization exec default group tacacs+ local",
        "Configure AAA accounting: aaa accounting exec default start-stop group tacacs+",
    ]

    async def evaluate(self, context: RuleContext) -> RuleEvaluationResult:
        import time
        start = time.monotonic_ns()
        config = context.device_config.get("running_config", "")

        aaa_enabled = "aaa new-model" in config
        aaa_auth = "aaa authentication login" in config
        aaa_authz = "aaa authorization exec" in config
        aaa_acct = "aaa accounting" in config

        findings = []
        if not aaa_enabled:
            findings.append("AAA new-model is not configured")
        if not aaa_auth:
            findings.append("AAA authentication login policy is missing")
        if not aaa_authz:
            findings.append("AAA authorization exec policy is missing")
        if not aaa_acct:
            findings.append("AAA accounting is not configured")

        result = RuleResult.PASS if not findings else RuleResult.FAIL
        elapsed = (time.monotonic_ns() - start) // 1_000_000

        return self._make_result(
            result=result,
            findings=findings,
            evidence={"aaa_new_model": aaa_enabled, "aaa_auth": aaa_auth, "aaa_authz": aaa_authz, "aaa_acct": aaa_acct},
            execution_ms=elapsed,
        )


class CISRule_1_2_EnableSecretEncryption(ComplianceRule):
    """CIS IOS — 1.2 Encrypt enable secret."""
    rule_id = "CIS-IOS-1.2"
    rule_name = "Enable Secret Must Use Strong Encryption"
    description = "Enable secret must use type 8 or type 9 encryption (not MD5 type 5)."
    framework = ComplianceFramework.CIS
    control_id = "1.2"
    severity = RuleSeverity.CRITICAL
    remediation_steps = [
        "Remove weak enable password: no enable password",
        "Set strong enable secret: enable algorithm-type sha256 secret <password>",
        "Verify with: show running-config | include enable secret",
        "Ensure service password-encryption is active",
    ]

    async def evaluate(self, context: RuleContext) -> RuleEvaluationResult:
        import re, time
        start = time.monotonic_ns()
        config = context.device_config.get("running_config", "")

        enable_password_pattern = re.search(r"enable password\s+\d*\s*\S+", config)
        enable_secret_pattern = re.search(r"enable secret\s+(\d+)\s+\S+", config)

        findings = []
        evidence: dict[str, Any] = {}

        if enable_password_pattern:
            findings.append("Cleartext 'enable password' detected — use 'enable secret' instead")
            evidence["cleartext_password"] = True

        if enable_secret_pattern:
            enc_type = int(enable_secret_pattern.group(1))
            evidence["encryption_type"] = enc_type
            if enc_type in (0, 7):
                findings.append(f"Enable secret uses weak encryption type {enc_type}; upgrade to type 8 or 9")
            elif enc_type == 5:
                findings.append("Enable secret uses MD5 (type 5); upgrade to PBKDF2 (type 8) or scrypt (type 9)")
        elif not enable_secret_pattern:
            findings.append("No enable secret is configured")

        result = RuleResult.PASS if not findings else RuleResult.FAIL
        elapsed = (time.monotonic_ns() - start) // 1_000_000

        return self._make_result(result=result, findings=findings, evidence=evidence, execution_ms=elapsed)


class CISRule_2_1_SSHv2Only(ComplianceRule):
    """CIS IOS — 2.1 Allow only SSHv2."""
    rule_id = "CIS-IOS-2.1"
    rule_name = "Allow Only SSHv2 for Remote Access"
    description = "SSH version must be 2. Telnet must be disabled. SSH timeout and retries must be configured."
    framework = ComplianceFramework.CIS
    control_id = "2.1"
    severity = RuleSeverity.CRITICAL
    remediation_steps = [
        "Set SSH version: ip ssh version 2",
        "Set timeout: ip ssh time-out 60",
        "Set max retries: ip ssh authentication-retries 3",
        "Disable telnet on VTY lines: transport input ssh",
        "Generate RSA keys ≥2048 bits: crypto key generate rsa modulus 2048",
    ]

    async def evaluate(self, context: RuleContext) -> RuleEvaluationResult:
        import re, time
        start = time.monotonic_ns()
        config = context.device_config.get("running_config", "")

        ssh_v2 = bool(re.search(r"ip ssh version\s+2", config))
        telnet_allowed = bool(re.search(r"transport input\s+(telnet|all)", config))
        ssh_timeout = bool(re.search(r"ip ssh time-out\s+\d+", config))
        ssh_retries = bool(re.search(r"ip ssh authentication-retries\s+[1-5]", config))

        rsa_match = re.search(r"crypto key generate rsa modulus\s+(\d+)", config)
        rsa_bits = int(rsa_match.group(1)) if rsa_match else 0

        findings = []
        if not ssh_v2:
            findings.append("SSH version 2 is not explicitly enforced")
        if telnet_allowed:
            findings.append("Telnet is permitted on VTY lines — this must be disabled")
        if not ssh_timeout:
            findings.append("SSH session timeout is not configured")
        if not ssh_retries:
            findings.append("SSH authentication retry limit is not configured")
        if rsa_bits < 2048:
            findings.append(f"RSA key modulus is {rsa_bits} bits; minimum 2048 bits required")

        result = RuleResult.PASS if not findings else RuleResult.FAIL
        elapsed = (time.monotonic_ns() - start) // 1_000_000

        return self._make_result(
            result=result,
            findings=findings,
            evidence={"ssh_v2": ssh_v2, "telnet_allowed": telnet_allowed, "rsa_bits": rsa_bits},
            execution_ms=elapsed,
        )


# ── OPA Integration ────────────────────────────────────────────────────────────

class OPAPolicyEvaluator:
    """
    Open Policy Agent integration for Rego-based compliance policies.
    Communicates with OPA REST API to evaluate policies against device configs.
    """

    def __init__(self, opa_url: str = "http://opa:8181") -> None:
        self.opa_url = opa_url
        self._http: Any = None  # aiohttp.ClientSession — lazy init

    async def _get_session(self) -> Any:
        if self._http is None:
            import aiohttp
            self._http = aiohttp.ClientSession(
                base_url=self.opa_url,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10),
            )
        return self._http

    async def evaluate_policy(
        self,
        policy_path: str,
        input_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Evaluate an OPA policy at policy_path with input_data."""
        session = await self._get_session()
        payload = {"input": input_data}
        async with session.post(f"/v1/data/{policy_path}", json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"OPA evaluation failed [{resp.status}]: {text}")
            data = await resp.json()
            return data.get("result", {})

    async def check_bundle_health(self) -> bool:
        session = await self._get_session()
        try:
            async with session.get("/health") as resp:
                return resp.status == 200
        except Exception:
            return False


# ── Rule Registry ──────────────────────────────────────────────────────────────

class ComplianceRuleRegistry:
    """Central registry mapping frameworks to their rule sets."""

    def __init__(self) -> None:
        self._rules: dict[str, ComplianceRule] = {}
        self._framework_index: dict[ComplianceFramework, list[str]] = {}
        self._register_built_in_rules()

    def _register_built_in_rules(self) -> None:
        built_ins: list[ComplianceRule] = [
            CISRule_1_1_EnableAAA(),
            CISRule_1_2_EnableSecretEncryption(),
            CISRule_2_1_SSHv2Only(),
        ]
        for rule in built_ins:
            self.register(rule)

    def register(self, rule: ComplianceRule) -> None:
        self._rules[rule.rule_id] = rule
        self._framework_index.setdefault(rule.framework, []).append(rule.rule_id)
        log.debug("compliance.rule.registered", rule_id=rule.rule_id, framework=rule.framework)

    def get_rules_for_framework(self, framework: ComplianceFramework) -> list[ComplianceRule]:
        rule_ids = self._framework_index.get(framework, [])
        return [self._rules[rid] for rid in rule_ids]

    def get_rule(self, rule_id: str) -> ComplianceRule | None:
        return self._rules.get(rule_id)


# ── Compliance Orchestrator ────────────────────────────────────────────────────

class ComplianceOrchestrator:
    """
    High-level orchestrator: drives rule evaluation, aggregates scores,
    resolves rule chains, and produces a ComplianceReport.
    """

    def __init__(
        self,
        registry: ComplianceRuleRegistry,
        opa_evaluator: OPAPolicyEvaluator | None = None,
        max_parallel_rules: int = 10,
    ) -> None:
        self._registry = registry
        self._opa = opa_evaluator
        self._semaphore = asyncio.Semaphore(max_parallel_rules)

    async def evaluate_device(
        self,
        device_id: UUID,
        device_config: dict[str, Any],
        device_metadata: dict[str, Any],
        frameworks: list[ComplianceFramework],
        baseline_config: dict[str, Any] | None = None,
        previous_score: Decimal | None = None,
    ) -> ComplianceReport:
        all_results: list[RuleEvaluationResult] = []

        for framework in frameworks:
            rules = self._registry.get_rules_for_framework(framework)
            context = RuleContext(
                device_id=device_id,
                device_config=device_config,
                device_metadata=device_metadata,
                framework=framework,
                baseline_config=baseline_config,
            )

            # Resolve rule evaluation order (topological sort for chaining)
            ordered_rules = self._topological_sort(rules)
            passed_rule_ids: set[str] = set()

            for rule in ordered_rules:
                # Check rule chain prerequisites
                if rule.requires_rules and not all(r in passed_rule_ids for r in rule.requires_rules):
                    log.debug("compliance.rule.skipped_chain", rule_id=rule.rule_id)
                    result = rule._make_result(
                        result=RuleResult.SKIPPED,
                        findings=["Prerequisite rule(s) did not pass"],
                    )
                else:
                    result = await self._evaluate_rule(rule, context)

                if result.passed:
                    passed_rule_ids.add(rule.rule_id)
                all_results.append(result)

        return self._aggregate_report(device_id, all_results, frameworks[0], previous_score)

    async def _evaluate_rule(
        self, rule: ComplianceRule, context: RuleContext
    ) -> RuleEvaluationResult:
        async with self._semaphore:
            try:
                return await asyncio.wait_for(rule.evaluate(context), timeout=30.0)
            except asyncio.TimeoutError:
                log.warning("compliance.rule.timeout", rule_id=rule.rule_id)
                return rule._make_result(
                    result=RuleResult.ERROR,
                    findings=["Rule evaluation timed out after 30 seconds"],
                )
            except Exception as exc:
                log.error("compliance.rule.error", rule_id=rule.rule_id, error=str(exc))
                return rule._make_result(
                    result=RuleResult.ERROR,
                    findings=[f"Rule evaluation error: {exc}"],
                )

    def _topological_sort(self, rules: list[ComplianceRule]) -> list[ComplianceRule]:
        """Sort rules so prerequisites evaluate before dependent rules."""
        rule_map = {r.rule_id: r for r in rules}
        visited: set[str] = set()
        order: list[ComplianceRule] = []

        def visit(rule: ComplianceRule) -> None:
            if rule.rule_id in visited:
                return
            visited.add(rule.rule_id)
            for dep_id in rule.requires_rules:
                if dep_id in rule_map:
                    visit(rule_map[dep_id])
            order.append(rule)

        for rule in rules:
            visit(rule)
        return order

    def _aggregate_report(
        self,
        device_id: UUID,
        results: list[RuleEvaluationResult],
        primary_framework: ComplianceFramework,
        previous_score: Decimal | None,
    ) -> ComplianceReport:
        weighted_score = Decimal("0")
        max_score = Decimal("0")
        control_summaries: dict[str, ControlSummary] = {}

        for result in results:
            weight = SEVERITY_WEIGHTS[result.severity]
            max_score += weight

            if result.result == RuleResult.SKIPPED:
                max_score -= weight  # Don't penalize skipped rules
                continue

            if result.passed:
                weighted_score += weight

            ctrl = control_summaries.setdefault(
                result.control_id,
                ControlSummary(
                    control_id=result.control_id,
                    control_name=result.control_id,
                    framework=result.framework,
                )
            )
            ctrl.rules_total += 1
            ctrl.max_score += weight
            if result.passed:
                ctrl.rules_passed += 1
                ctrl.weighted_score += weight
            else:
                ctrl.rules_failed += 1

        overall = weighted_score / max_score * 100 if max_score else Decimal("0")

        report = ComplianceReport(
            device_id=device_id,
            framework=primary_framework,
            overall_score=round(overall, 2),
            weighted_score=round(weighted_score, 2),
            max_possible_score=round(max_score, 2),
            pass_count=sum(1 for r in results if r.result == RuleResult.PASS),
            fail_count=sum(1 for r in results if r.result == RuleResult.FAIL),
            warn_count=sum(1 for r in results if r.result == RuleResult.WARN),
            error_count=sum(1 for r in results if r.result == RuleResult.ERROR),
            skipped_count=sum(1 for r in results if r.result == RuleResult.SKIPPED),
            exception_count=sum(1 for r in results if r.result == RuleResult.EXCEPTION),
            results=results,
            control_summaries=control_summaries,
            previous_score=previous_score,
            baseline_delta=(overall - previous_score) if previous_score is not None else None,
        )

        log.info(
            "compliance.report.generated",
            device_id=str(device_id),
            score=str(report.overall_score),
            pass_count=report.pass_count,
            fail_count=report.fail_count,
            critical_failures=len(report.critical_failures),
        )
        return report
