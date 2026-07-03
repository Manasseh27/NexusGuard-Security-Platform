import { useState, useEffect } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { authApi } from "../services/api";
import { C } from "../styles/tokens";

const inputStyle = {
  width: "100%",
  padding: "12px 14px",
  borderRadius: 12,
  border: `1px solid ${C.border}`,
  background: C.surface3,
  color: C.text,
  outline: "none",
  boxSizing: "border-box" as const,
};

function PasswordStrength({ password }: { password: string }) {
  const checks = [
    { label: "12+ characters", ok: password.length >= 12 },
    { label: "Uppercase", ok: /[A-Z]/.test(password) },
    { label: "Lowercase", ok: /[a-z]/.test(password) },
    { label: "Number", ok: /\d/.test(password) },
    { label: "Special character", ok: /[^a-zA-Z0-9]/.test(password) },
  ];
  if (!password) return null;
  return (
    <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: 6 }}>
      {checks.map(({ label, ok }) => (
        <span key={label} style={{
          fontSize: 11, padding: "2px 8px", borderRadius: 20,
          background: ok ? "rgba(16,185,129,0.15)" : "rgba(239,68,68,0.12)",
          color: ok ? C.green : C.red, border: `1px solid ${ok ? C.green : C.red}40`,
        }}>
          {ok ? "✓" : "✗"} {label}
        </span>
      ))}
    </div>
  );
}

export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [token, setToken] = useState(searchParams.get("token") ?? "");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const t = searchParams.get("token");
    if (t) setToken(t);
  }, [searchParams]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setIsLoading(true);
    try {
      await authApi.resetPassword(token.trim(), password);
      setSuccess(true);
      setTimeout(() => navigate("/login", { replace: true }), 3000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Invalid or expired reset token.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh",
      display: "grid",
      placeItems: "center",
      padding: 24,
      background: "radial-gradient(circle at top, #152033 0%, #0b1020 45%, #050816 100%)",
      color: C.text,
    }}>
      <div style={{
        width: "100%",
        maxWidth: 440,
        padding: 32,
        borderRadius: 20,
        border: `1px solid ${C.border}`,
        background: "rgba(11, 16, 32, 0.88)",
        boxShadow: "0 24px 80px rgba(0,0,0,0.4)",
      }}>
        <div style={{ marginBottom: 28 }}>
          <div style={{ fontSize: 12, letterSpacing: 2, textTransform: "uppercase", color: C.textMuted }}>
            NexusGuard
          </div>
          <h1 style={{ fontSize: 28, margin: "10px 0 6px" }}>Set new password</h1>
          <p style={{ margin: 0, color: C.textMuted, fontSize: 14 }}>
            Enter your reset token and choose a new password.
          </p>
        </div>

        {success ? (
          <div>
            <div style={{
              padding: 16, borderRadius: 12, marginBottom: 20,
              background: "rgba(16,185,129,0.12)", color: C.green,
              border: `1px solid ${C.green}40`, fontSize: 14, lineHeight: 1.6,
            }}>
              Password reset successfully. Redirecting to sign in…
            </div>
            <Link to="/login" style={{
              display: "block", textAlign: "center", padding: "12px 16px",
              borderRadius: 12, background: "linear-gradient(135deg, #22d3ee 0%, #2563eb 100%)",
              color: "white", fontWeight: 700, textDecoration: "none", fontSize: 15,
            }}>
              Sign in now
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <label style={{ display: "block", marginBottom: 14 }}>
              <div style={{ marginBottom: 6, fontSize: 13, color: C.textMuted }}>Reset token</div>
              <input value={token} onChange={(e) => setToken(e.target.value)}
                required placeholder="Paste your reset token here" style={inputStyle} />
            </label>

            <label style={{ display: "block", marginBottom: 6 }}>
              <div style={{ marginBottom: 6, fontSize: 13, color: C.textMuted }}>New password</div>
              <input value={password} onChange={(e) => setPassword(e.target.value)}
                type="password" autoComplete="new-password" required minLength={12} style={inputStyle} />
            </label>
            <PasswordStrength password={password} />

            <label style={{ display: "block", marginTop: 14, marginBottom: 18 }}>
              <div style={{ marginBottom: 6, fontSize: 13, color: C.textMuted }}>Confirm new password</div>
              <input value={confirm} onChange={(e) => setConfirm(e.target.value)}
                type="password" autoComplete="new-password" required style={{
                  ...inputStyle,
                  borderColor: confirm && confirm !== password ? C.red : C.border,
                }} />
            </label>

            {error && (
              <div style={{
                marginBottom: 16, padding: 12, borderRadius: 12,
                background: "rgba(220,38,38,0.14)", color: "#fecaca",
                border: "1px solid rgba(220,38,38,0.35)", fontSize: 14,
              }}>
                {error}
              </div>
            )}

            <button type="submit" disabled={isLoading} style={{
              width: "100%", padding: "12px 16px", border: "none", borderRadius: 12,
              background: "linear-gradient(135deg, #22d3ee 0%, #2563eb 100%)",
              color: "white", fontWeight: 700, cursor: isLoading ? "wait" : "pointer",
              fontSize: 15,
            }}>
              {isLoading ? "Resetting…" : "Reset password"}
            </button>
          </form>
        )}

        <div style={{ marginTop: 20, textAlign: "center", fontSize: 14, color: C.textMuted }}>
          <Link to="/login" style={{ color: C.cyan, textDecoration: "none" }}>
            ← Back to sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
