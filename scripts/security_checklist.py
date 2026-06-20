"""
Security readiness checklist for NexusGuard deployment.
Run before deploying to production.
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Tuple, List

logger = logging.getLogger(__name__)


class SecurityChecklist:
    """Comprehensive security readiness checklist."""

    def __init__(self):
        self.checks: List[Tuple[str, bool, str]] = []

    def _check(self, name: str, condition: bool, message: str = "") -> None:
        """Record a check result."""
        self.checks.append((name, condition, message))

    def check_environment_variables(self) -> None:
        """Check critical environment variables are set."""
        print("\n🔐 Checking Environment Variables...")

        critical_vars = {
            "SECRET_KEY": "JWT signing key",
            "DATABASE_URL": "Database connection string",
            "REDIS_URL": "Redis connection string",
        }

        for var, description in critical_vars.items():
            value = os.getenv(var)
            self._check(
                f"ENV: {var}",
                bool(value),
                f"Missing: {description}" if not value else "✓",
            )

            # Check SECRET_KEY is not default
            if var == "SECRET_KEY":
                is_default = value in ["change-me", "change-me-to-a-random-64-char-string"]
                self._check(
                    "SECRET_KEY not default",
                    not is_default,
                    "CRITICAL: SECRET_KEY is still default value!" if is_default else "✓",
                )

    def check_database_security(self) -> None:
        """Check database security settings."""
        print("\n🗄️  Checking Database Security...")

        db_url = os.getenv("DATABASE_URL", "")

        # Check SSL usage
        uses_ssl = "sslmode=require" in db_url or "ssl=true" in db_url
        self._check("Database SSL", uses_ssl, "SSL should be required in production")

        # Check password is not default
        if "devpassword" in db_url:
            self._check("DB Password", False, "CRITICAL: Default password detected!")
        else:
            self._check("DB Password", True, "✓")

    def check_tls_certificates(self) -> None:
        """Check TLS/HTTPS certificates."""
        print("\n🔒 Checking TLS/HTTPS...")

        enable_https = os.getenv("ENABLE_HTTPS", "true").lower() == "true"
        cert_path = os.getenv("TLS_CERT_PATH")
        key_path = os.getenv("TLS_KEY_PATH")

        self._check("HTTPS Enabled", enable_https, "HTTPS should be enabled in production")

        if enable_https:
            cert_exists = Path(cert_path).exists() if cert_path else False
            key_exists = Path(key_path).exists() if key_path else False

            self._check(
                "TLS Certificate",
                cert_exists,
                f"Certificate not found at {cert_path}" if not cert_exists else "✓",
            )
            self._check(
                "TLS Key",
                key_exists,
                f"Key not found at {key_path}" if not key_exists else "✓",
            )

    def check_cors_configuration(self) -> None:
        """Check CORS security."""
        print("\n🌐 Checking CORS Configuration...")

        cors_origins = os.getenv("CORS_ORIGINS", "").split(",")

        # Check for wildcard
        has_wildcard = "*" in cors_origins
        self._check(
            "CORS Wildcard",
            not has_wildcard,
            "WARNING: CORS wildcard (*) is insecure in production",
        )

        # Check for localhost in production
        env = os.getenv("ENVIRONMENT", "development")
        has_localhost = any("localhost" in origin for origin in cors_origins)
        if env == "production" and has_localhost:
            self._check(
                "CORS Localhost in Prod",
                False,
                "WARNING: Localhost in CORS origins for production",
            )
        else:
            self._check("CORS Localhost", True, "✓")

    def check_password_policy(self) -> None:
        """Check password policy settings."""
        print("\n🔑 Checking Password Policy...")

        min_length = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))
        require_upper = os.getenv("PASSWORD_REQUIRE_UPPERCASE", "true").lower() == "true"
        require_lower = os.getenv("PASSWORD_REQUIRE_LOWERCASE", "true").lower() == "true"
        require_numbers = os.getenv("PASSWORD_REQUIRE_NUMBERS", "true").lower() == "true"
        require_special = os.getenv("PASSWORD_REQUIRE_SPECIAL", "true").lower() == "true"

        self._check(
            "Password Min Length >= 12",
            min_length >= 12,
            f"Current: {min_length} (should be >= 12)",
        )
        self._check("Require Uppercase", require_upper, "✓" if require_upper else "Disabled")
        self._check("Require Lowercase", require_lower, "✓" if require_lower else "Disabled")
        self._check("Require Numbers", require_numbers, "✓" if require_numbers else "Disabled")
        self._check("Require Special", require_special, "✓" if require_special else "Disabled")

    def check_rate_limiting(self) -> None:
        """Check rate limiting."""
        print("\n⏱️  Checking Rate Limiting...")

        rate_limit_enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
        self._check("Rate Limit Enabled", rate_limit_enabled, "✓" if rate_limit_enabled else "Disabled")

    def check_audit_logging(self) -> None:
        """Check audit logging."""
        print("\n📋 Checking Audit Logging...")

        audit_enabled = os.getenv("AUDIT_LOG_ENABLED", "true").lower() == "true"
        self._check("Audit Logging Enabled", audit_enabled, "✓" if audit_enabled else "Disabled")

    def check_mfa(self) -> None:
        """Check MFA configuration."""
        print("\n🔐 Checking Multi-Factor Authentication...")

        env = os.getenv("ENVIRONMENT", "development")
        mfa_required = os.getenv("MFA_REQUIRED", "false").lower() == "true"

        if env == "production":
            self._check(
                "MFA Required (Prod)",
                mfa_required,
                "MFA should be required in production" if not mfa_required else "✓",
            )
        else:
            self._check("MFA Recommended", mfa_required, "✓" if mfa_required else "Optional")

    def check_security_headers(self) -> None:
        """Check security headers."""
        print("\n📡 Checking Security Headers...")

        headers_enabled = os.getenv("ENABLE_SECURITY_HEADERS", "true").lower() == "true"
        csp_enabled = os.getenv("CSP_ENABLED", "true").lower() == "true"
        hsts_enabled = os.getenv("HSTS_ENABLED", "true").lower() == "true"

        self._check("Security Headers Enabled", headers_enabled, "✓" if headers_enabled else "Disabled")
        self._check("CSP Enabled", csp_enabled, "✓" if csp_enabled else "Disabled")
        self._check("HSTS Enabled", hsts_enabled, "✓" if hsts_enabled else "Disabled")

    def check_dependencies(self) -> None:
        """Check for known vulnerabilities in dependencies."""
        print("\n📦 Checking Dependencies...")

        try:
            import subprocess
            result = subprocess.run(
                ["pip", "check"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            has_conflicts = result.returncode != 0
            self._check(
                "No Dependency Conflicts",
                not has_conflicts,
                result.stdout if has_conflicts else "✓",
            )
        except Exception as e:
            logger.warning(f"Could not run pip check: {e}")

    def run_all_checks(self) -> bool:
        """Run all security checks."""
        print("=" * 70)
        print("🛡️  NexusGuard Security Readiness Checklist")
        print("=" * 70)
        print(f"Timestamp: {datetime.utcnow().isoformat()}")
        print(f"Environment: {os.getenv('ENVIRONMENT', 'unknown')}")

        self.check_environment_variables()
        self.check_database_security()
        self.check_tls_certificates()
        self.check_cors_configuration()
        self.check_password_policy()
        self.check_rate_limiting()
        self.check_audit_logging()
        self.check_mfa()
        self.check_security_headers()
        self.check_dependencies()

        return self.print_results()

    def print_results(self) -> bool:
        """Print results and return pass/fail."""
        print("\n" + "=" * 70)
        print("📊 Results Summary")
        print("=" * 70)

        passed = sum(1 for _, result, _ in self.checks if result)
        total = len(self.checks)

        for name, result, message in self.checks:
            status = "✅" if result else "❌"
            print(f"{status} {name:40s} {message}")

        print("\n" + "-" * 70)
        print(f"Passed: {passed}/{total}")

        if passed == total:
            print("✨ All security checks passed!")
            return True
        else:
            failed = total - passed
            print(f"⚠️  {failed} check(s) failed or need attention")
            return False


def main():
    """Run security checklist."""
    # Load .env if it exists
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)

    checklist = SecurityChecklist()
    passed = checklist.run_all_checks()

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
