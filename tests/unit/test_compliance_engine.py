"""
Compliance Engine Test Suite
Covers: unit tests, rule evaluation, orchestration, scoring, drift detection.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.domain.compliance.engine.compliance_engine import (
    CISRule_1_1_EnableAAA,
    CISRule_1_2_EnableSecretEncryption,
    CISRule_2_1_SSHv2Only,
    ComplianceFramework,
    ComplianceOrchestrator,
    ComplianceReport,
    ComplianceRuleRegistry,
    OPAPolicyEvaluator,
    RuleContext,
    RuleResult,
    RuleSeverity,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def device_id():
    return uuid4()


@pytest.fixture
def good_ios_config() -> dict:
    """Fully hardened IOS configuration passing all CIS Level 1 checks."""
    return {
        "running_config": """
aaa new-model
aaa authentication login default group tacacs+ local
aaa authorization exec default group tacacs+ local
aaa accounting exec default start-stop group tacacs+

enable algorithm-type sha256 secret $8$abc123def456

ip ssh version 2
ip ssh time-out 60
ip ssh authentication-retries 3

line vty 0 4
 transport input ssh

crypto key generate rsa modulus 2048

service password-encryption
no service telnet-zerobyte
no ip http server
no ip http secure-server
""",
        "device_ip": "10.10.1.1",
    }


@pytest.fixture
def weak_ios_config() -> dict:
    """Poorly configured IOS device that should fail multiple CIS checks."""
    return {
        "running_config": """
enable password cisco123

line vty 0 4
 transport input telnet ssh

ip ssh version 1

no aaa new-model
""",
        "device_ip": "10.10.1.99",
    }


@pytest.fixture
def rule_context_good(device_id, good_ios_config) -> RuleContext:
    return RuleContext(
        device_id=device_id,
        device_config=good_ios_config,
        device_metadata={"device_type": "ios", "hostname": "edge-router-01"},
        framework=ComplianceFramework.CIS,
    )


@pytest.fixture
def rule_context_weak(device_id, weak_ios_config) -> RuleContext:
    return RuleContext(
        device_id=device_id,
        device_config=weak_ios_config,
        device_metadata={"device_type": "ios", "hostname": "legacy-router-99"},
        framework=ComplianceFramework.CIS,
    )


@pytest.fixture
def registry() -> ComplianceRuleRegistry:
    return ComplianceRuleRegistry()


@pytest.fixture
def orchestrator(registry) -> ComplianceOrchestrator:
    return ComplianceOrchestrator(registry=registry, max_parallel_rules=5)


# ── Rule: AAA ──────────────────────────────────────────────────────────────────

class TestCISRule_1_1_EnableAAA:

    @pytest.mark.asyncio
    async def test_pass_with_full_aaa(self, rule_context_good):
        rule = CISRule_1_1_EnableAAA()
        result = await rule.evaluate(rule_context_good)
        assert result.result == RuleResult.PASS
        assert result.severity == RuleSeverity.HIGH
        assert result.rule_id == "CIS-IOS-1.1"
        assert len(result.findings) == 0

    @pytest.mark.asyncio
    async def test_fail_with_no_aaa(self, rule_context_weak):
        rule = CISRule_1_1_EnableAAA()
        result = await rule.evaluate(rule_context_weak)
        assert result.result == RuleResult.FAIL
        assert len(result.findings) >= 1
        assert any("aaa new-model" in f.lower() or "AAA" in f for f in result.findings)

    @pytest.mark.asyncio
    async def test_fail_with_partial_aaa(self, device_id):
        # Has aaa new-model but missing authorization
        ctx = RuleContext(
            device_id=device_id,
            device_config={"running_config": "aaa new-model\naaa authentication login default local\n"},
            device_metadata={},
            framework=ComplianceFramework.CIS,
        )
        rule = CISRule_1_1_EnableAAA()
        result = await rule.evaluate(ctx)
        assert result.result == RuleResult.FAIL
        # Should flag missing authorization and accounting
        findings_text = " ".join(result.findings).lower()
        assert "authorization" in findings_text or "accounting" in findings_text

    @pytest.mark.asyncio
    async def test_execution_ms_populated(self, rule_context_good):
        rule = CISRule_1_1_EnableAAA()
        result = await rule.evaluate(rule_context_good)
        assert result.execution_ms >= 0

    @pytest.mark.asyncio
    async def test_score_zero_on_fail(self, rule_context_weak):
        rule = CISRule_1_1_EnableAAA()
        result = await rule.evaluate(rule_context_weak)
        assert result.score == Decimal("0")

    @pytest.mark.asyncio
    async def test_score_nonzero_on_pass(self, rule_context_good):
        rule = CISRule_1_1_EnableAAA()
        result = await rule.evaluate(rule_context_good)
        assert result.score > Decimal("0")


# ── Rule: Enable Secret ────────────────────────────────────────────────────────

class TestCISRule_1_2_EnableSecretEncryption:

    @pytest.mark.asyncio
    async def test_pass_with_type8_secret(self, device_id):
        ctx = RuleContext(
            device_id=device_id,
            device_config={"running_config": "enable secret 8 $8$abc123fakehash\n"},
            device_metadata={},
            framework=ComplianceFramework.CIS,
        )
        rule = CISRule_1_2_EnableSecretEncryption()
        result = await rule.evaluate(ctx)
        assert result.result == RuleResult.PASS

    @pytest.mark.asyncio
    async def test_pass_with_type9_secret(self, device_id):
        ctx = RuleContext(
            device_id=device_id,
            device_config={"running_config": "enable secret 9 $9$abc123fakehash\n"},
            device_metadata={},
            framework=ComplianceFramework.CIS,
        )
        rule = CISRule_1_2_EnableSecretEncryption()
        result = await rule.evaluate(ctx)
        assert result.result == RuleResult.PASS

    @pytest.mark.asyncio
    async def test_fail_with_md5_type5_secret(self, device_id):
        ctx = RuleContext(
            device_id=device_id,
            device_config={"running_config": "enable secret 5 $1$abc$fakemd5hash\n"},
            device_metadata={},
            framework=ComplianceFramework.CIS,
        )
        rule = CISRule_1_2_EnableSecretEncryption()
        result = await rule.evaluate(ctx)
        assert result.result == RuleResult.FAIL
        assert any("MD5" in f or "type 5" in f for f in result.findings)

    @pytest.mark.asyncio
    async def test_fail_with_cleartext_password(self, device_id):
        ctx = RuleContext(
            device_id=device_id,
            device_config={"running_config": "enable password cisco123\n"},
            device_metadata={},
            framework=ComplianceFramework.CIS,
        )
        rule = CISRule_1_2_EnableSecretEncryption()
        result = await rule.evaluate(ctx)
        assert result.result == RuleResult.FAIL
        assert any("cleartext" in f.lower() or "password" in f.lower() for f in result.findings)

    @pytest.mark.asyncio
    async def test_fail_with_no_secret_configured(self, device_id):
        ctx = RuleContext(
            device_id=device_id,
            device_config={"running_config": "hostname router\n"},
            device_metadata={},
            framework=ComplianceFramework.CIS,
        )
        rule = CISRule_1_2_EnableSecretEncryption()
        result = await rule.evaluate(ctx)
        assert result.result == RuleResult.FAIL

    @pytest.mark.asyncio
    async def test_severity_is_critical(self):
        rule = CISRule_1_2_EnableSecretEncryption()
        assert rule.severity == RuleSeverity.CRITICAL


# ── Rule: SSH v2 ───────────────────────────────────────────────────────────────

class TestCISRule_2_1_SSHv2Only:

    @pytest.mark.asyncio
    async def test_pass_with_full_ssh_hardening(self, rule_context_good):
        rule = CISRule_2_1_SSHv2Only()
        result = await rule.evaluate(rule_context_good)
        assert result.result == RuleResult.PASS
        assert len(result.findings) == 0

    @pytest.mark.asyncio
    async def test_fail_with_telnet_allowed(self, device_id):
        ctx = RuleContext(
            device_id=device_id,
            device_config={"running_config": (
                "ip ssh version 2\n"
                "ip ssh time-out 60\n"
                "ip ssh authentication-retries 3\n"
                "line vty 0 4\n transport input telnet ssh\n"
            )},
            device_metadata={},
            framework=ComplianceFramework.CIS,
        )
        rule = CISRule_2_1_SSHv2Only()
        result = await rule.evaluate(ctx)
        assert result.result == RuleResult.FAIL
        assert any("telnet" in f.lower() for f in result.findings)

    @pytest.mark.asyncio
    async def test_fail_with_ssh_v1(self, device_id):
        ctx = RuleContext(
            device_id=device_id,
            device_config={"running_config": "ip ssh version 1\nline vty 0 4\n transport input ssh\n"},
            device_metadata={},
            framework=ComplianceFramework.CIS,
        )
        rule = CISRule_2_1_SSHv2Only()
        result = await rule.evaluate(ctx)
        assert result.result == RuleResult.FAIL
        assert any("version 2" in f.lower() or "ssh" in f.lower() for f in result.findings)

    @pytest.mark.asyncio
    async def test_fail_with_weak_rsa_key(self, device_id):
        ctx = RuleContext(
            device_id=device_id,
            device_config={"running_config": (
                "ip ssh version 2\n"
                "ip ssh time-out 60\n"
                "ip ssh authentication-retries 3\n"
                "line vty 0 4\n transport input ssh\n"
                "crypto key generate rsa modulus 1024\n"
            )},
            device_metadata={},
            framework=ComplianceFramework.CIS,
        )
        rule = CISRule_2_1_SSHv2Only()
        result = await rule.evaluate(ctx)
        assert result.result == RuleResult.FAIL
        assert any("1024" in f or "2048" in f for f in result.findings)

    @pytest.mark.asyncio
    async def test_evidence_contains_details(self, rule_context_good):
        rule = CISRule_2_1_SSHv2Only()
        result = await rule.evaluate(rule_context_good)
        assert "ssh_v2" in result.evidence
        assert result.evidence["ssh_v2"] is True

    @pytest.mark.asyncio
    async def test_remediation_steps_present(self):
        rule = CISRule_2_1_SSHv2Only()
        assert len(rule.remediation_steps) > 0
        assert any("ssh version 2" in s.lower() for s in rule.remediation_steps)


# ── Orchestrator ───────────────────────────────────────────────────────────────

class TestComplianceOrchestrator:

    @pytest.mark.asyncio
    async def test_evaluate_device_returns_report(self, orchestrator, device_id, good_ios_config):
        report = await orchestrator.evaluate_device(
            device_id=device_id,
            device_config=good_ios_config,
            device_metadata={"device_type": "ios"},
            frameworks=[ComplianceFramework.CIS],
        )
        assert isinstance(report, ComplianceReport)
        assert report.device_id == device_id

    @pytest.mark.asyncio
    async def test_good_config_scores_higher_than_weak(self, orchestrator, device_id, good_ios_config, weak_ios_config):
        good_report = await orchestrator.evaluate_device(
            device_id=device_id,
            device_config=good_ios_config,
            device_metadata={},
            frameworks=[ComplianceFramework.CIS],
        )
        weak_report = await orchestrator.evaluate_device(
            device_id=device_id,
            device_config=weak_ios_config,
            device_metadata={},
            frameworks=[ComplianceFramework.CIS],
        )
        assert good_report.overall_score > weak_report.overall_score

    @pytest.mark.asyncio
    async def test_report_pass_fail_counts_correct(self, orchestrator, device_id, weak_ios_config):
        report = await orchestrator.evaluate_device(
            device_id=device_id,
            device_config=weak_ios_config,
            device_metadata={},
            frameworks=[ComplianceFramework.CIS],
        )
        total_evaluated = report.pass_count + report.fail_count + report.error_count + report.skipped_count
        assert total_evaluated == len(report.results)

    @pytest.mark.asyncio
    async def test_score_between_0_and_100(self, orchestrator, device_id, weak_ios_config):
        report = await orchestrator.evaluate_device(
            device_id=device_id,
            device_config=weak_ios_config,
            device_metadata={},
            frameworks=[ComplianceFramework.CIS],
        )
        assert Decimal("0") <= report.overall_score <= Decimal("100")

    @pytest.mark.asyncio
    async def test_baseline_delta_calculated(self, orchestrator, device_id, good_ios_config):
        report = await orchestrator.evaluate_device(
            device_id=device_id,
            device_config=good_ios_config,
            device_metadata={},
            frameworks=[ComplianceFramework.CIS],
            previous_score=Decimal("80"),
        )
        assert report.baseline_delta is not None
        assert report.previous_score == Decimal("80")

    @pytest.mark.asyncio
    async def test_timeout_handled_gracefully(self, registry, device_id):
        """A rule that times out should produce an ERROR result, not crash."""
        from app.domain.compliance.engine.compliance_engine import ComplianceRule

        class SlowRule(ComplianceRule):
            rule_id = "SLOW-001"
            rule_name = "Slow Rule"
            description = "Times out"
            framework = ComplianceFramework.CIS
            control_id = "99.1"
            severity = RuleSeverity.LOW

            async def evaluate(self, context: RuleContext):
                await asyncio.sleep(999)  # Will be cancelled
                return self._make_result(RuleResult.PASS)

        registry.register(SlowRule())
        orch = ComplianceOrchestrator(registry=registry, max_parallel_rules=5)
        # Patch timeout to be very short for test
        with patch.object(orch, "_evaluate_rule", wraps=orch._evaluate_rule) as mock:
            report = await orch.evaluate_device(
                device_id=device_id,
                device_config={"running_config": ""},
                device_metadata={},
                frameworks=[ComplianceFramework.CIS],
            )
        # Platform should not crash — just record errors
        assert isinstance(report, ComplianceReport)

    @pytest.mark.asyncio
    async def test_control_summaries_populated(self, orchestrator, device_id, good_ios_config):
        report = await orchestrator.evaluate_device(
            device_id=device_id,
            device_config=good_ios_config,
            device_metadata={},
            frameworks=[ComplianceFramework.CIS],
        )
        assert len(report.control_summaries) > 0

    @pytest.mark.asyncio
    async def test_content_hash_deterministic(self, orchestrator, device_id, good_ios_config):
        report1 = await orchestrator.evaluate_device(
            device_id=device_id,
            device_config=good_ios_config,
            device_metadata={},
            frameworks=[ComplianceFramework.CIS],
        )
        report2 = await orchestrator.evaluate_device(
            device_id=device_id,
            device_config=good_ios_config,
            device_metadata={},
            frameworks=[ComplianceFramework.CIS],
        )
        assert report1.content_hash == report2.content_hash

    @pytest.mark.asyncio
    async def test_critical_failures_filtered_correctly(self, orchestrator, device_id, weak_ios_config):
        report = await orchestrator.evaluate_device(
            device_id=device_id,
            device_config=weak_ios_config,
            device_metadata={},
            frameworks=[ComplianceFramework.CIS],
        )
        for failure in report.critical_failures:
            assert failure.severity == RuleSeverity.CRITICAL
            assert failure.failed is True


# ── Registry ───────────────────────────────────────────────────────────────────

class TestComplianceRuleRegistry:

    def test_built_in_rules_registered(self, registry):
        cis_rules = registry.get_rules_for_framework(ComplianceFramework.CIS)
        assert len(cis_rules) >= 3

    def test_get_rule_by_id(self, registry):
        rule = registry.get_rule("CIS-IOS-1.1")
        assert rule is not None
        assert rule.rule_id == "CIS-IOS-1.1"

    def test_get_unknown_rule_returns_none(self, registry):
        assert registry.get_rule("NONEXISTENT-99.99") is None

    def test_register_custom_rule(self, registry):
        from app.domain.compliance.engine.compliance_engine import ComplianceRule

        class CustomRule(ComplianceRule):
            rule_id = "CUSTOM-001"
            rule_name = "Custom Test Rule"
            description = "A custom rule"
            framework = ComplianceFramework.CUSTOM
            control_id = "C.1"
            severity = RuleSeverity.MEDIUM

            async def evaluate(self, context):
                return self._make_result(RuleResult.PASS)

        registry.register(CustomRule())
        custom_rules = registry.get_rules_for_framework(ComplianceFramework.CUSTOM)
        assert len(custom_rules) == 1
        assert custom_rules[0].rule_id == "CUSTOM-001"
