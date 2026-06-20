import React from "react";
import { C } from "../../styles/tokens";

type Props = {
  children: React.ReactNode;
};

type State = {
  hasError: boolean;
};

export class AppErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
          background: C.bg,
          color: C.text,
          padding: 24,
        }}>
          <div style={{
            maxWidth: 560,
            width: "100%",
            padding: 32,
            borderRadius: 20,
            border: `1px solid ${C.border}`,
            background: C.surface2,
          }}>
            <div style={{ fontSize: 13, color: C.textMuted, marginBottom: 8 }}>Application error</div>
            <h1 style={{ margin: "0 0 12px", fontSize: 28 }}>The dashboard hit an unrecoverable error.</h1>
            <p style={{ margin: "0 0 20px", color: C.textMuted, lineHeight: 1.6 }}>
              Reload the page to reinitialize the session. If the issue persists, check the backend health endpoints and API logs.
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              style={{
                padding: "10px 16px",
                border: "none",
                borderRadius: 12,
                background: C.cyan,
                color: "white",
                cursor: "pointer",
                fontWeight: 600,
              }}
            >
              Reload application
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}