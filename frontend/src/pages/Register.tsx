import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";
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
    { label: "Uppercase letter", ok: /[A-Z]/.test(password) },
    { label: "Lowercase letter", ok: /[a-z]/.test(password) },
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

export default function RegisterPage() {
  const navigate = useNavigate();
  const register = useAuthStore((s) => s.register);
  const error = useAuthStore((s) => s.error);
  const isLoading = useAuthStore((s) => s.isLoading);
  const clearError = useAuthStore((s) => s.clearError);
  const accessToken = useAuthStore((s) => s.accessToken);

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [localError, setLocalError] = useState("");

  useEffect(() => { clearError(); }, [clearError]);
  useEffect(() => { if (accessToken) navigate("/", { replace: true }); }, [accessToken, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError("");
    if (password !== confirm) {
      setLocalError("Passwords do not match.");
      return;
    }
    try {
      await register(username, email, password);
      navigate("/", { replace: true });
    } catch { /* error shown via store */ }
  };

  const displayError = localError || error;

  return (
    <div style={{
      minHeight: "100vh",
      display: "grid",
      placeItems: "center",
      padding: 24,
      background: "radial-gradient(circle at top, #152033 0%, #0b1020 45%, #050816 100%)",
      color: C.text,
    }}>
      <form onSubmit={handleSubmit} style={{
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
          <h1 style={{ fontSize: 28, margin: "10px 0 6px" }}>Create account</h1>
          <p style={{ margin: 0, color: C.textMuted, fontSize: 14 }}>
            Join the security operations platform.
          </p>
        </div>

        <label style={{ display: "block", marginBottom: 14 }}>
          <div style={{ marginBottom: 6, fontSize: 13, color: C.textMuted }}>Username</div>
          <input value={username} onChange={(e) => setUsername(e.target.value)}
            autoComplete="username" required minLength={3} maxLength={64} style={inputStyle} />
        </label>

        <label style={{ display: "block", marginBottom: 14 }}>
          <div style={{ marginBottom: 6, fontSize: 13, color: C.textMuted }}>Email address</div>
          <input value={email} onChange={(e) => setEmail(e.target.value)}
            type="email" autoComplete="email" required style={inputStyle} />
        </label>

        <label style={{ display: "block", marginBottom: 6 }}>
          <div style={{ marginBottom: 6, fontSize: 13, color: C.textMuted }}>Password</div>
          <input value={password} onChange={(e) => setPassword(e.target.value)}
            type="password" autoComplete="new-password" required minLength={12} style={inputStyle} />
        </label>
        <PasswordStrength password={password} />

        <label style={{ display: "block", marginTop: 14, marginBottom: 18 }}>
          <div style={{ marginBottom: 6, fontSize: 13, color: C.textMuted }}>Confirm password</div>
          <input value={confirm} onChange={(e) => setConfirm(e.target.value)}
            type="password" autoComplete="new-password" required style={{
              ...inputStyle,
              borderColor: confirm && confirm !== password ? C.red : C.border,
            }} />
        </label>

        {displayError && (
          <div style={{
            marginBottom: 16, padding: 12, borderRadius: 12,
            background: "rgba(220,38,38,0.14)", color: "#fecaca",
            border: "1px solid rgba(220,38,38,0.35)", fontSize: 14,
          }}>
            {displayError}
          </div>
        )}

        <button type="submit" disabled={isLoading} style={{
          width: "100%", padding: "12px 16px", border: "none", borderRadius: 12,
          background: "linear-gradient(135deg, #22d3ee 0%, #2563eb 100%)",
          color: "white", fontWeight: 700, cursor: isLoading ? "wait" : "pointer",
          fontSize: 15,
        }}>
          {isLoading ? "Creating account…" : "Create account"}
        </button>

        <div style={{ marginTop: 20, textAlign: "center", fontSize: 14, color: C.textMuted }}>
          Already have an account?{" "}
          <Link to="/login" style={{ color: C.cyan, textDecoration: "none", fontWeight: 600 }}>
            Sign in
          </Link>
        </div>
      </form>
    </div>
  );
}
