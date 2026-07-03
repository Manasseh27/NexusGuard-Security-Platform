import { useState, useEffect } from "react";
import { useSearchParams, Link } from "react-router-dom";
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

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const [token, setToken] = useState(searchParams.get("token") ?? "");
  const [isLoading, setIsLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  // Auto-verify if token is in URL
  useEffect(() => {
    const t = searchParams.get("token");
    if (t) {
      setToken(t);
      verify(t);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const verify = async (t: string) => {
    setError("");
    setIsLoading(true);
    try {
      await authApi.verifyEmail(t.trim());
      setSuccess(true);
    } catch {
      setError("Invalid or expired verification token.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    verify(token);
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
          <h1 style={{ fontSize: 28, margin: "10px 0 6px" }}>Verify email</h1>
          <p style={{ margin: 0, color: C.textMuted, fontSize: 14 }}>
            Enter your verification token to activate your account.
          </p>
        </div>

        {isLoading && (
          <div style={{ textAlign: "center", padding: 24, color: C.textMuted, fontSize: 14 }}>
            Verifying…
          </div>
        )}

        {!isLoading && success && (
          <div>
            <div style={{
              padding: 16, borderRadius: 12, marginBottom: 20,
              background: "rgba(16,185,129,0.12)", color: C.green,
              border: `1px solid ${C.green}40`, fontSize: 14, lineHeight: 1.6,
            }}>
              Email verified successfully. Your account is now active.
            </div>
            <Link to="/login" style={{
              display: "block", textAlign: "center", padding: "12px 16px",
              borderRadius: 12, background: "linear-gradient(135deg, #22d3ee 0%, #2563eb 100%)",
              color: "white", fontWeight: 700, textDecoration: "none", fontSize: 15,
            }}>
              Sign in
            </Link>
          </div>
        )}

        {!isLoading && !success && (
          <form onSubmit={handleSubmit}>
            <label style={{ display: "block", marginBottom: 18 }}>
              <div style={{ marginBottom: 6, fontSize: 13, color: C.textMuted }}>Verification token</div>
              <input value={token} onChange={(e) => setToken(e.target.value)}
                required placeholder="Paste your verification token" style={inputStyle} />
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

            <button type="submit" style={{
              width: "100%", padding: "12px 16px", border: "none", borderRadius: 12,
              background: "linear-gradient(135deg, #22d3ee 0%, #2563eb 100%)",
              color: "white", fontWeight: 700, cursor: "pointer", fontSize: 15,
            }}>
              Verify email
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
