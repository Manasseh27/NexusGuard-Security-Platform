import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";
import { C } from "../styles/tokens";

export default function LoginPage() {
  const navigate = useNavigate();
  const login = useAuthStore((state) => state.login);
  const error = useAuthStore((state) => state.error);
  const isLoading = useAuthStore((state) => state.isLoading);
  const clearError = useAuthStore((state) => state.clearError);
  const accessToken = useAuthStore((state) => state.accessToken);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    clearError();
  }, [clearError]);

  useEffect(() => {
    if (accessToken) {
      navigate("/", { replace: true });
    }
  }, [accessToken, navigate]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      await login(username, password);
      navigate("/", { replace: true });
    } catch {
      // store.error is updated by the auth store
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
      <form onSubmit={handleSubmit} style={{
        width: "100%",
        maxWidth: 420,
        padding: 32,
        borderRadius: 20,
        border: `1px solid ${C.border}`,
        background: "rgba(11, 16, 32, 0.88)",
        boxShadow: "0 24px 80px rgba(0, 0, 0, 0.4)",
      }}>
        <div style={{ marginBottom: 24 }}>
          <div style={{ fontSize: 12, letterSpacing: 2, textTransform: "uppercase", color: C.textMuted }}>
            NexusGuard
          </div>
          <h1 style={{ fontSize: 32, margin: "12px 0 8px" }}>Secure access</h1>
          <p style={{ margin: 0, color: C.textMuted }}>
            Sign in to the enterprise security operations platform.
          </p>
        </div>

        <label style={{ display: "block", marginBottom: 14 }}>
          <div style={{ marginBottom: 6, fontSize: 13, color: C.textMuted }}>Username</div>
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            required
            style={{
              width: "100%",
              padding: "12px 14px",
              borderRadius: 12,
              border: `1px solid ${C.border}`,
              background: C.surface3,
              color: C.text,
              outline: "none",
            }}
          />
        </label>

        <label style={{ display: "block", marginBottom: 18 }}>
          <div style={{ marginBottom: 6, fontSize: 13, color: C.textMuted }}>Password</div>
          <input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            autoComplete="current-password"
            required
            style={{
              width: "100%",
              padding: "12px 14px",
              borderRadius: 12,
              border: `1px solid ${C.border}`,
              background: C.surface3,
              color: C.text,
              outline: "none",
            }}
          />
        </label>

        {error && (
          <div style={{
            marginBottom: 16,
            padding: 12,
            borderRadius: 12,
            background: "rgba(220, 38, 38, 0.14)",
            color: "#fecaca",
            border: "1px solid rgba(220, 38, 38, 0.35)",
          }}>
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={isLoading}
          style={{
            width: "100%",
            padding: "12px 16px",
            border: "none",
            borderRadius: 12,
            background: "linear-gradient(135deg, #22d3ee 0%, #2563eb 100%)",
            color: "white",
            fontWeight: 700,
            cursor: isLoading ? "wait" : "pointer",
          }}
        >
          {isLoading ? "Signing in..." : "Sign in"}
        </button>

        <div style={{ marginTop: 16, fontSize: 12, color: C.textMuted, lineHeight: 1.5 }}>
          Use your platform credentials. Demo users are available in development only.
        </div>
      </form>
    </div>
  );
}