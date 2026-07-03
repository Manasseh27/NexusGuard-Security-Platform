import { useState } from "react";
import { Link } from "react-router-dom";
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

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);
    try {
      await authApi.forgotPassword(email);
      setSubmitted(true);
    } catch {
      setError("Something went wrong. Please try again.");
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
        maxWidth: 420,
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
          <h1 style={{ fontSize: 28, margin: "10px 0 6px" }}>Reset password</h1>
          <p style={{ margin: 0, color: C.textMuted, fontSize: 14 }}>
            Enter your email and we'll send a reset token.
          </p>
        </div>

        {submitted ? (
          <div>
            <div style={{
              padding: 16, borderRadius: 12, marginBottom: 20,
              background: "rgba(16,185,129,0.12)", color: C.green,
              border: `1px solid ${C.green}40`, fontSize: 14, lineHeight: 1.6,
            }}>
              If an account exists for <strong>{email}</strong>, a password reset token has been issued.
              Check your email or use the token directly on the reset page.
            </div>
            <Link to="/reset-password" style={{
              display: "block", textAlign: "center", padding: "12px 16px",
              borderRadius: 12, background: "linear-gradient(135deg, #22d3ee 0%, #2563eb 100%)",
              color: "white", fontWeight: 700, textDecoration: "none", fontSize: 15,
            }}>
              Enter reset token
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <label style={{ display: "block", marginBottom: 18 }}>
              <div style={{ marginBottom: 6, fontSize: 13, color: C.textMuted }}>Email address</div>
              <input value={email} onChange={(e) => setEmail(e.target.value)}
                type="email" autoComplete="email" required style={inputStyle} />
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
              {isLoading ? "Sending…" : "Send reset token"}
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
