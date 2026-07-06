import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { copilotApi } from "../services/api";
import { useDashboardStore } from "../stores/dashboardStore";
import type { CopilotResponse } from "../types";
import { C, RADIUS, ANIM } from "../styles/tokens";

// ── Types ──────────────────────────────────────────────────────────────────────

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  meta?: Pick<CopilotResponse, "provider" | "model" | "latency_ms" | "tokens_used" | "cached">;
  error?: boolean;
}

interface QuickPrompt {
  label: string;
  text: string;
  icon: string;
}

// ── Constants ──────────────────────────────────────────────────────────────────

const MAX_RETRIES = 2;

const QUICK_PROMPTS: QuickPrompt[] = [
  { icon: "◈", label: "Security posture",     text: "Summarize the current security posture and top risks." },
  { icon: "⚑", label: "Compliance gaps",      text: "What are the most urgent compliance gaps and how should I prioritize them?" },
  { icon: "🔧", label: "Remediation plan",     text: "Recommend the top three remediation priorities with effort estimates." },
  { icon: "◎", label: "Incident guidance",    text: "What are the best practices for responding to a critical security incident?" },
  { icon: "◬", label: "Drift analysis",       text: "Explain what compliance drift means and how to prevent it." },
  { icon: "◫", label: "Device hardening",     text: "What device hardening steps should I prioritize for the fleet?" },
];

// ── Minimal markdown renderer (no external deps) ──────────────────────────────

function renderMarkdown(text: string): string {
  return text
    // fenced code blocks
    .replace(/```(\w*)\n?([\s\S]*?)```/g, (_, _lang, code) =>
      `<pre style="background:${C.surface};border:1px solid ${C.border};border-radius:6px;padding:10px 12px;overflow-x:auto;font-size:12px;line-height:1.5;margin:8px 0"><code>${code.trim().replace(/</g, "&lt;").replace(/>/g, "&gt;")}</code></pre>`
    )
    // inline code
    .replace(/`([^`]+)`/g, `<code style="background:${C.surface};border:1px solid ${C.border};border-radius:4px;padding:1px 5px;font-size:12px">$1</code>`)
    // bold
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    // headers
    .replace(/^### (.+)$/gm, `<div style="font-size:13px;font-weight:700;color:${C.cyanBright};margin:12px 0 4px">$1</div>`)
    .replace(/^## (.+)$/gm,  `<div style="font-size:14px;font-weight:700;color:${C.text};margin:14px 0 6px">$1</div>`)
    .replace(/^# (.+)$/gm,   `<div style="font-size:16px;font-weight:700;color:${C.text};margin:16px 0 8px">$1</div>`)
    // bullet lists
    .replace(/^[-*] (.+)$/gm, `<div style="display:flex;gap:8px;margin:2px 0"><span style="color:${C.cyan};flex-shrink:0">▸</span><span>$1</span></div>`)
    // numbered lists
    .replace(/^\d+\. (.+)$/gm, `<div style="display:flex;gap:8px;margin:2px 0"><span style="color:${C.textMuted};flex-shrink:0;min-width:16px">•</span><span>$1</span></div>`)
    // line breaks
    .replace(/\n\n/g, `<div style="height:8px"></div>`)
    .replace(/\n/g, "<br/>");
}

// ── Streaming dot indicator ────────────────────────────────────────────────────

function StreamingDots() {
  return (
    <span style={{ display: "inline-flex", gap: 3, alignItems: "center", marginLeft: 4 }}>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          style={{
            width: 5, height: 5, borderRadius: "50%",
            background: C.cyan,
            animation: "pulse 1.2s ease-in-out infinite",
            animationDelay: `${i * 0.2}s`,
            display: "inline-block",
          }}
        />
      ))}
    </span>
  );
}

// ── Message bubble ─────────────────────────────────────────────────────────────

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";
  return (
    <article style={{
      marginLeft: isUser ? "auto" : 0,
      maxWidth: "88%",
      padding: "12px 16px",
      borderRadius: isUser ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
      border: `1px solid ${isUser ? `${C.cyan}50` : msg.error ? `${C.red}50` : C.border}`,
      background: isUser
        ? `${C.cyan}12`
        : msg.error
          ? `${C.red}10`
          : C.surface3,
      lineHeight: 1.65,
      fontSize: 13,
    }}>
      <div style={{
        fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase",
        color: isUser ? C.cyan : msg.error ? C.red : C.textMuted,
        marginBottom: 8, fontWeight: 600,
      }}>
        {isUser ? "You" : msg.error ? "Error" : "NexusGuard AI"}
      </div>

      {isUser ? (
        <div style={{ color: C.text, whiteSpace: "pre-wrap" }}>{msg.content}</div>
      ) : (
        <div
          style={{ color: msg.error ? C.red : C.textSub }}
          dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
        />
      )}

      {msg.streaming && <StreamingDots />}

      {msg.meta && !msg.streaming && (
        <div style={{
          marginTop: 10, paddingTop: 8,
          borderTop: `1px solid ${C.border}`,
          display: "flex", gap: 12, flexWrap: "wrap",
          fontSize: 10, color: C.textMuted,
        }}>
          <span>{msg.meta.provider}</span>
          {msg.meta.model && <span>{msg.meta.model}</span>}
          <span>{msg.meta.latency_ms}ms</span>
          <span>{msg.meta.tokens_used} tokens</span>
          {msg.meta.cached && <span style={{ color: C.green }}>cached</span>}
        </div>
      )}
    </article>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function CopilotPage() {
  const navigate = useNavigate();
  const summary = useDashboardStore((s) => s.summary);

  const [messages, setMessages] = useState<Message[]>([{
    id: "welcome",
    role: "assistant",
    content: "Hello! I'm the NexusGuard AI Security Copilot. I can help with compliance analysis, incident response, device recommendations, remediation guidance, and more.\n\nUse the quick prompts below or ask me anything about your security posture.",
  }]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId] = useState<string>(() => {
    const stored = localStorage.getItem("copilot_session_id");
    if (stored) return stored;
    const id = crypto.randomUUID();
    localStorage.setItem("copilot_session_id", id);
    return id;
  });
  const [providerInfo, setProviderInfo] = useState<{ primary?: string; status: "checking" | "online" | "degraded" | "offline" }>({ status: "checking" });
  const [useStreaming, setUseStreaming] = useState(true);

  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  // Check provider health on mount
  useEffect(() => {
    copilotApi.providersHealth()
      .then((data: { primary?: string; providers?: Record<string, boolean> }) => {
        const anyOnline = data.providers ? Object.values(data.providers).some(Boolean) : true;
        setProviderInfo({
          primary: data.primary,
          status: anyOnline ? "online" : "degraded",
        });
      })
      .catch(() => setProviderInfo({ status: "offline" }));
  }, []);

  // Build platform context from dashboard summary
  const buildContext = useCallback(() => {
    if (!summary) return {};
    return {
      fleet: {
        total_devices: summary.fleet.total_devices,
        healthy: summary.fleet.healthy,
        drifting: summary.fleet.drifting,
        average_compliance_score: summary.fleet.average_compliance_score,
        active_drift_events: summary.fleet.active_drift_events,
      },
      compliance: {
        frameworks: summary.frameworks.map((f) => ({
          id: f.id,
          avg_score: f.avg_score,
          devices_critical: f.devices_critical,
        })),
      },
      incidents: summary.incidents,
      audit_24h: summary.audit.last_24h,
    };
  }, [summary]);

  // Core send function with retry and streaming support
  const sendMessage = useCallback(async (prompt?: string, retryCount = 0) => {
    const message = (prompt ?? input).trim();
    if (!message || isSending) return;

    // Cancel any in-flight stream
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    const userMsgId = crypto.randomUUID();
    const assistantMsgId = crypto.randomUUID();

    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: "user", content: message },
      { id: assistantMsgId, role: "assistant", content: "", streaming: true },
    ]);
    setInput("");
    setIsSending(true);
    setError(null);

    try {
      if (useStreaming) {
        const reader = await copilotApi.chatStream(message, sessionId, abortRef.current.signal);
        let accumulated = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          // Parse SSE lines
          const lines = value.split("\n");
          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            try {
              const parsed = JSON.parse(line.slice(6));
              if (parsed.error) throw new Error(parsed.error);
              if (parsed.done) break;
              if (parsed.token) {
                accumulated += parsed.token;
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMsgId
                      ? { ...m, content: accumulated }
                      : m
                  )
                );
              }
            } catch (parseErr) {
              if ((parseErr as Error).message !== "Unexpected end of JSON input") throw parseErr;
            }
          }
        }

        // Mark streaming done
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId ? { ...m, streaming: false } : m
          )
        );
      } else {
        // Non-streaming fallback
        const context = buildContext();
        const response = await copilotApi.chat(message, [], sessionId);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? {
                  ...m,
                  content: response.content,
                  streaming: false,
                  meta: {
                    provider: response.provider,
                    model: response.model,
                    latency_ms: response.latency_ms,
                    tokens_used: response.tokens_used,
                    cached: response.cached,
                  },
                }
              : m
          )
        );
      }
    } catch (err: unknown) {
      if ((err as Error).name === "AbortError") {
        // User cancelled — remove the empty assistant bubble
        setMessages((prev) => prev.filter((m) => m.id !== assistantMsgId));
        setIsSending(false);
        return;
      }

      const errMsg = err instanceof Error ? err.message : "Request failed";

      // Retry logic
      if (retryCount < MAX_RETRIES) {
        setMessages((prev) => prev.filter((m) => m.id !== assistantMsgId && m.id !== userMsgId));
        setIsSending(false);
        await new Promise((r) => setTimeout(r, 800 * (retryCount + 1)));
        return sendMessage(message, retryCount + 1);
      }

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsgId
            ? { ...m, content: errMsg, streaming: false, error: true }
            : m
        )
      );
      setError(`Failed after ${MAX_RETRIES + 1} attempts: ${errMsg}`);
    } finally {
      setIsSending(false);
    }
  }, [input, isSending, sessionId, useStreaming, buildContext]);

  // Keyboard shortcut: Ctrl/Cmd+Enter to send
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      void sendMessage();
    }
  };

  const handleStop = () => {
    abortRef.current?.abort();
    setIsSending(false);
  };

  const handleClearSession = async () => {
    await copilotApi.clearSession(sessionId).catch(() => undefined);
    setMessages([{
      id: crypto.randomUUID(),
      role: "assistant",
      content: "Conversation cleared. How can I help you?",
    }]);
    setError(null);
  };

  const statusColor = {
    checking: C.textMuted,
    online:   C.green,
    degraded: C.yellow,
    offline:  C.red,
  }[providerInfo.status];

  const canSend = input.trim().length > 0 && !isSending;

  return (
    <div style={{ minHeight: "100vh", background: `linear-gradient(180deg, #07111f 0%, #050816 100%)`, color: C.text }}>

      {/* ── Header ── */}
      <header style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        padding: "16px 24px", borderBottom: `1px solid ${C.border}`,
        background: "rgba(8,14,28,0.9)", backdropFilter: "blur(16px)",
        position: "sticky", top: 0, zIndex: 100,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{
            width: 36, height: 36, borderRadius: RADIUS.md,
            background: `linear-gradient(135deg, ${C.cyan}, ${C.purple})`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 18, boxShadow: `0 0 16px ${C.cyan}40`,
          }}>◎</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 15, color: C.text }}>NexusGuard AI Copilot</div>
            <div style={{ fontSize: 11, color: C.textMuted }}>Security intelligence assistant</div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {/* Provider status */}
          <div style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: "5px 10px", borderRadius: RADIUS.full,
            background: `${statusColor}12`, border: `1px solid ${statusColor}30`,
            fontSize: 11,
          }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: statusColor, display: "inline-block" }} />
            <span style={{ color: statusColor, fontWeight: 600 }}>
              {providerInfo.primary ?? "AI"} · {providerInfo.status}
            </span>
          </div>

          {/* Streaming toggle */}
          <button
            onClick={() => setUseStreaming((v) => !v)}
            style={{
              padding: "5px 10px", borderRadius: RADIUS.full, cursor: "pointer",
              border: `1px solid ${useStreaming ? C.cyan : C.border}`,
              background: useStreaming ? `${C.cyan}12` : "transparent",
              color: useStreaming ? C.cyan : C.textMuted, fontSize: 11, fontWeight: 600,
            }}
            title="Toggle streaming responses"
          >
            {useStreaming ? "⚡ Stream" : "⚡ Stream off"}
          </button>

          <button
            onClick={handleClearSession}
            style={{
              padding: "5px 10px", borderRadius: RADIUS.full, cursor: "pointer",
              border: `1px solid ${C.border}`, background: "transparent",
              color: C.textMuted, fontSize: 11,
            }}
          >
            Clear session
          </button>

          <button
            onClick={() => navigate("/")}
            style={{
              padding: "8px 14px", borderRadius: RADIUS.md, cursor: "pointer",
              border: `1px solid ${C.border}`, background: C.surface3,
              color: C.text, fontSize: 12,
            }}
          >
            ← Dashboard
          </button>
        </div>
      </header>

      <main style={{
        display: "grid",
        gridTemplateColumns: "minmax(0, 1fr) 280px",
        gap: 16, padding: 20,
        maxWidth: 1400, margin: "0 auto",
        height: "calc(100vh - 70px)",
      }}>

        {/* ── Chat panel ── */}
        <section style={{
          display: "flex", flexDirection: "column",
          border: `1px solid ${C.border}`, borderRadius: RADIUS.xl,
          background: "rgba(11,16,32,0.9)", overflow: "hidden",
        }}>

          {/* Context banner */}
          {summary && (
            <div style={{
              padding: "8px 16px", borderBottom: `1px solid ${C.border}`,
              background: `${C.cyan}08`,
              display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap",
              fontSize: 11, color: C.textMuted,
            }}>
              <span style={{ color: C.cyan, fontWeight: 600 }}>◈ Live context</span>
              <span>{summary.fleet.total_devices} devices</span>
              <span style={{ color: summary.fleet.average_compliance_score >= 85 ? C.green : C.yellow }}>
                {summary.fleet.average_compliance_score.toFixed(1)}% compliance
              </span>
              <span style={{ color: summary.incidents.critical_open > 0 ? C.red : C.textMuted }}>
                {summary.incidents.open} open incidents
              </span>
              <span style={{ color: summary.fleet.active_drift_events > 0 ? C.orange : C.textMuted }}>
                {summary.fleet.active_drift_events} drift events
              </span>
            </div>
          )}

          {/* Messages */}
          <div
            ref={scrollRef}
            style={{
              flex: 1, overflowY: "auto", padding: 16,
              display: "flex", flexDirection: "column", gap: 12,
            }}
          >
            {messages.map((msg) => <MessageBubble key={msg.id} msg={msg} />)}
          </div>

          {/* Input area */}
          <div style={{ padding: 16, borderTop: `1px solid ${C.border}` }}>
            {error && (
              <div style={{
                marginBottom: 10, padding: "10px 14px", borderRadius: RADIUS.md,
                background: `${C.red}12`, border: `1px solid ${C.red}30`,
                color: C.red, fontSize: 12,
                display: "flex", justifyContent: "space-between", alignItems: "center",
              }}>
                <span>{error}</span>
                <button
                  onClick={() => setError(null)}
                  style={{ background: "none", border: "none", color: C.red, cursor: "pointer", fontSize: 14 }}
                >✕</button>
              </div>
            )}

            {/* Quick prompts */}
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
              {QUICK_PROMPTS.map((p) => (
                <button
                  key={p.label}
                  onClick={() => void sendMessage(p.text)}
                  disabled={isSending}
                  style={{
                    padding: "5px 10px", borderRadius: RADIUS.full, cursor: "pointer",
                    border: `1px solid ${C.border}`, background: C.surface2,
                    color: C.textMuted, fontSize: 11,
                    transition: `all ${ANIM.fast}`,
                    opacity: isSending ? 0.5 : 1,
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = C.cyan; e.currentTarget.style.color = C.cyan; }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = C.border; e.currentTarget.style.color = C.textMuted; }}
                >
                  {p.icon} {p.label}
                </button>
              ))}
            </div>

            <form
              onSubmit={(e) => { e.preventDefault(); void sendMessage(); }}
              style={{ display: "flex", gap: 10, alignItems: "flex-end" }}
            >
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={3}
                placeholder="Ask about compliance, incidents, devices, or remediation… (Ctrl+Enter to send)"
                style={{
                  flex: 1, resize: "none", padding: "12px 14px",
                  borderRadius: RADIUS.md,
                  border: `1px solid ${input ? C.borderMid : C.border}`,
                  background: C.surface2, color: C.text,
                  fontSize: 13, lineHeight: 1.5, outline: "none",
                  transition: `border-color ${ANIM.fast}`,
                }}
                onFocus={(e) => { e.currentTarget.style.borderColor = C.cyan; }}
                onBlur={(e) => { e.currentTarget.style.borderColor = input ? C.borderMid : C.border; }}
              />
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {isSending ? (
                  <button
                    type="button"
                    onClick={handleStop}
                    style={{
                      padding: "10px 16px", borderRadius: RADIUS.md, cursor: "pointer",
                      border: `1px solid ${C.red}50`, background: `${C.red}15`,
                      color: C.red, fontWeight: 700, fontSize: 12, whiteSpace: "nowrap",
                    }}
                  >
                    ■ Stop
                  </button>
                ) : (
                  <button
                    type="submit"
                    disabled={!canSend}
                    style={{
                      padding: "10px 18px", borderRadius: RADIUS.md, cursor: canSend ? "pointer" : "not-allowed",
                      border: "none",
                      background: canSend
                        ? `linear-gradient(135deg, ${C.cyan} 0%, ${C.blue} 100%)`
                        : C.surface3,
                      color: canSend ? "#fff" : C.textMuted,
                      fontWeight: 700, fontSize: 12, whiteSpace: "nowrap",
                      transition: `all ${ANIM.fast}`,
                    }}
                  >
                    Send ↵
                  </button>
                )}
              </div>
            </form>
          </div>
        </section>

        {/* ── Sidebar ── */}
        <aside style={{ display: "flex", flexDirection: "column", gap: 12, overflowY: "auto" }}>

          {/* Capabilities */}
          <div style={{ padding: 16, borderRadius: RADIUS.lg, border: `1px solid ${C.border}`, background: C.surface2 }}>
            <div style={{ fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", color: C.textMuted, marginBottom: 12, fontWeight: 600 }}>
              Capabilities
            </div>
            {[
              { icon: "◈", label: "Compliance analysis",       desc: "Explain failures, score gaps, framework recommendations" },
              { icon: "⚑", label: "Incident analysis",         desc: "Severity assessment, MITRE mapping, containment steps" },
              { icon: "◫", label: "Device recommendations",    desc: "Per-device hardening, drift analysis, patch guidance" },
              { icon: "🔧", label: "Remediation guidance",      desc: "Prioritized fixes with CLI commands and effort estimates" },
              { icon: "◬", label: "Attack path analysis",      desc: "Kill chain mapping, lateral movement, MITRE ATT&CK" },
              { icon: "◎", label: "Risk prioritization",       desc: "Risk-scored roadmap with regulatory context" },
              { icon: "📋", label: "Executive summaries",       desc: "SOC briefings, compliance posture, trend analysis" },
              { icon: "🔍", label: "CVE explanation",           desc: "Vulnerability impact, affected assets, mitigations" },
            ].map((cap) => (
              <div key={cap.label} style={{ marginBottom: 10 }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 2 }}>
                  <span style={{ fontSize: 12 }}>{cap.icon}</span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: C.textSub }}>{cap.label}</span>
                </div>
                <div style={{ fontSize: 11, color: C.textMuted, paddingLeft: 20 }}>{cap.desc}</div>
              </div>
            ))}
          </div>

          {/* Session info */}
          <div style={{ padding: 16, borderRadius: RADIUS.lg, border: `1px solid ${C.border}`, background: C.surface2 }}>
            <div style={{ fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", color: C.textMuted, marginBottom: 10, fontWeight: 600 }}>
              Session
            </div>
            <div style={{ fontSize: 11, color: C.textMuted, marginBottom: 6 }}>Session ID</div>
            <div style={{
              fontSize: 10, color: C.textDim, fontFamily: "monospace",
              background: C.surface3, padding: "6px 8px", borderRadius: RADIUS.sm,
              wordBreak: "break-all",
            }}>
              {sessionId}
            </div>
            <div style={{ marginTop: 10, fontSize: 11, color: C.textMuted }}>
              {messages.filter((m) => m.role === "user").length} message(s) this session
            </div>
            <div style={{ marginTop: 6, fontSize: 11, color: C.textMuted }}>
              Memory: server-side (Redis)
            </div>
          </div>

          {/* Context status */}
          <div style={{ padding: 16, borderRadius: RADIUS.lg, border: `1px solid ${C.border}`, background: C.surface2 }}>
            <div style={{ fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", color: C.textMuted, marginBottom: 10, fontWeight: 600 }}>
              Platform context
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
              <span style={{
                width: 7, height: 7, borderRadius: "50%",
                background: summary ? C.green : C.textMuted,
                display: "inline-block",
              }} />
              <span style={{ color: summary ? C.green : C.textMuted }}>
                {summary ? "Live data injected" : "No dashboard data"}
              </span>
            </div>
            {summary && (
              <div style={{ marginTop: 8, fontSize: 11, color: C.textMuted, lineHeight: 1.7 }}>
                The AI has access to your current fleet status, compliance scores, incident counts, and drift events.
              </div>
            )}
          </div>
        </aside>
      </main>
    </div>
  );
}
