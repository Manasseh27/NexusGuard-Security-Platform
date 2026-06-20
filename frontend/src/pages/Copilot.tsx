import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { copilotApi } from "../services/api";
import type { ChatMessage, CopilotResponse } from "../types";
import { C } from "../styles/tokens";

type Message = ChatMessage & { id: string; meta?: Omit<CopilotResponse, "content"> };

const QUICK_PROMPTS = [
  "Summarize the current security posture in one paragraph.",
  "Explain the most urgent compliance gaps.",
  "Recommend the top three remediation priorities.",
];

export default function CopilotPage() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Ask about compliance, devices, alerts, incidents, or remediation guidance.",
    },
  ]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState(() => localStorage.getItem("copilot_session_id") ?? undefined);
  const [providerStatus, setProviderStatus] = useState<string>("unknown");

  useEffect(() => {
    let mounted = true;
    copilotApi.providersHealth()
      .then(() => mounted && setProviderStatus("online"))
      .catch(() => mounted && setProviderStatus("unavailable"));
    return () => {
      mounted = false;
    };
  }, []);

  const canSend = useMemo(() => input.trim().length > 0 && !isSending, [input, isSending]);

  async function sendMessage(prompt?: string) {
    const message = (prompt ?? input).trim();
    if (!message || isSending) {
      return;
    }

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: message,
    };

    setMessages((current) => [...current, userMessage]);
    setInput("");
    setIsSending(true);
    setError(null);

    try {
      const history = messages.map(({ role, content }) => ({ role, content }));
      const response = await copilotApi.chat(message, history, sessionId);
      setSessionId(response.session_id ?? sessionId);
      if (response.session_id) {
        localStorage.setItem("copilot_session_id", response.session_id);
      }
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: response.content,
          meta: response,
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Copilot request failed");
    } finally {
      setIsSending(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", background: "linear-gradient(180deg, #07111f 0%, #050816 100%)", color: C.text }}>
      <header style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: 16,
        padding: "20px 24px",
        borderBottom: `1px solid ${C.border}`,
        background: "rgba(8, 14, 28, 0.82)",
        backdropFilter: "blur(16px)",
      }}>
        <div>
          <div style={{ fontSize: 12, letterSpacing: 2, textTransform: "uppercase", color: C.textMuted }}>AI Copilot</div>
          <h1 style={{ margin: "8px 0 0", fontSize: 28 }}>Security analyst assistant</h1>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ fontSize: 12, color: C.textMuted }}>
            Providers: <span style={{ color: providerStatus === "online" ? C.green : C.yellow }}>{providerStatus}</span>
          </div>
          <button
            type="button"
            onClick={() => navigate("/")}
            style={{
              padding: "10px 14px",
              borderRadius: 12,
              border: `1px solid ${C.border}`,
              background: C.surface3,
              color: C.text,
              cursor: "pointer",
            }}
          >
            Back to dashboard
          </button>
        </div>
      </header>

      <main style={{
        display: "grid",
        gridTemplateColumns: "minmax(0, 1.7fr) minmax(280px, 0.9fr)",
        gap: 16,
        padding: 24,
        maxWidth: 1500,
        margin: "0 auto",
      }}>
        <section style={{
          border: `1px solid ${C.border}`,
          borderRadius: 20,
          background: "rgba(11, 16, 32, 0.88)",
          boxShadow: "0 24px 80px rgba(0, 0, 0, 0.35)",
          overflow: "hidden",
        }}>
          <div style={{ padding: 16, borderBottom: `1px solid ${C.border}` }}>
            <div style={{ fontSize: 13, color: C.textMuted }}>Conversation</div>
          </div>

          <div style={{ minHeight: 500, maxHeight: "calc(100vh - 300px)", overflowY: "auto", padding: 16, display: "grid", gap: 12 }}>
            {messages.map((message) => (
              <article
                key={message.id}
                style={{
                  marginLeft: message.role === "user" ? "auto" : 0,
                  maxWidth: "86%",
                  padding: "12px 14px",
                  borderRadius: 16,
                  border: `1px solid ${message.role === "user" ? `${C.cyan}60` : C.border}`,
                  background: message.role === "user" ? "rgba(34, 211, 238, 0.12)" : C.surface3,
                  whiteSpace: "pre-wrap",
                  lineHeight: 1.6,
                }}
              >
                <div style={{ fontSize: 11, letterSpacing: 1.2, textTransform: "uppercase", color: C.textMuted, marginBottom: 8 }}>
                  {message.role}
                </div>
                <div>{message.content}</div>
                {message.meta && (
                  <div style={{ marginTop: 10, fontSize: 11, color: C.textMuted }}>
                    {message.meta.provider} · {message.meta.model || "default model"} · {message.meta.latency_ms} ms
                  </div>
                )}
              </article>
            ))}
            {isSending && (
              <div style={{ color: C.textMuted, fontSize: 13 }}>Copilot is generating a response...</div>
            )}
          </div>

          <div style={{ padding: 16, borderTop: `1px solid ${C.border}` }}>
            {error && (
              <div style={{ marginBottom: 12, padding: 12, borderRadius: 12, background: "rgba(127, 29, 29, 0.22)", color: "#fecaca" }}>
                {error}
              </div>
            )}
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void sendMessage();
              }}
              style={{ display: "grid", gap: 12 }}
            >
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                rows={4}
                placeholder="Ask Copilot about compliance, incidents, alerts, or remediation steps..."
                style={{
                  width: "100%",
                  resize: "vertical",
                  padding: 14,
                  borderRadius: 14,
                  border: `1px solid ${C.border}`,
                  background: C.surface2,
                  color: C.text,
                  outline: "none",
                }}
              />
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {QUICK_PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => void sendMessage(prompt)}
                      style={{
                        padding: "8px 12px",
                        borderRadius: 999,
                        border: `1px solid ${C.border}`,
                        background: C.surface3,
                        color: C.textMuted,
                        cursor: "pointer",
                        fontSize: 12,
                      }}
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
                <button
                  type="submit"
                  disabled={!canSend}
                  style={{
                    padding: "10px 16px",
                    border: "none",
                    borderRadius: 12,
                    background: canSend ? "linear-gradient(135deg, #22d3ee 0%, #2563eb 100%)" : C.surface3,
                    color: canSend ? "white" : C.textMuted,
                    fontWeight: 700,
                    cursor: canSend ? "pointer" : "not-allowed",
                  }}
                >
                  {isSending ? "Sending..." : "Send message"}
                </button>
              </div>
            </form>
          </div>
        </section>

        <aside style={{ display: "grid", gap: 16 }}>
          <section style={{ padding: 18, borderRadius: 20, border: `1px solid ${C.border}`, background: C.surface2 }}>
            <div style={{ fontSize: 12, letterSpacing: 1.2, textTransform: "uppercase", color: C.textMuted, marginBottom: 8 }}>Capabilities</div>
            <ul style={{ margin: 0, paddingLeft: 18, color: C.textMuted, lineHeight: 1.8 }}>
              <li>Summarize compliance posture.</li>
              <li>Explain failed controls and findings.</li>
              <li>Generate remediation guidance.</li>
              <li>Analyze alerts and incidents.</li>
            </ul>
          </section>

          <section style={{ padding: 18, borderRadius: 20, border: `1px solid ${C.border}`, background: C.surface2 }}>
            <div style={{ fontSize: 12, letterSpacing: 1.2, textTransform: "uppercase", color: C.textMuted, marginBottom: 8 }}>Session</div>
            <div style={{ color: C.textMuted, lineHeight: 1.7, fontSize: 13 }}>
              Session ID
              <div style={{ marginTop: 6, color: C.text }}>{sessionId ?? "new session"}</div>
            </div>
          </section>
        </aside>
      </main>
    </div>
  );
}