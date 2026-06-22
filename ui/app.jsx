/* global React, ReactDOM, Sidebar, EmptyState, Composer, Message, SkillsModal, I */
const { useState, useRef, useEffect, useCallback } = React;

const STORE_KEY = "atlas.chat.v1";
const USER = { name: "Maya Okonkwo", role: "Operations · member", initials: "MO" };

const uid = () => Math.random().toString(36).slice(2, 10);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function greetingText() {
  const h = new Date().getHours();
  const t = h < 5 ? "late night" : h < 12 ? "morning" : h < 18 ? "afternoon" : "evening";
  return `Good ${t}, ${USER.name.split(" ")[0]}`;
}

/* ---- seed conversations so the sidebar feels lived-in ---- */
function seed() {
  const d = Date.now();
  return [
    { id: uid(), createdAt: d - 36e5, title: "Onboarding checklist for new hires",
      messages: [
        { id: uid(), role: "user", content: "What's the onboarding checklist for a new eng hire?" },
        { id: uid(), role: "agent", status: "done",
          steps: [{ tool: "search_docs", input: "engineering onboarding checklist", result: "Found 'Eng Onboarding v4' in the People wiki.", status: "done" }],
          content: "Here's the current **engineering onboarding** checklist (People wiki, v4):\n\n1. **Day 0** — laptop + SSO provisioned, added to `#eng` and team channel\n2. **Day 1** — repo access, dev environment setup, read the architecture overview\n3. **Week 1** — ship a starter PR, 1:1 with manager, security training\n4. **Week 2** — on-call shadowing, meet your onboarding buddy\n\nWant me to generate a personalized version for a specific role?" },
      ] },
    { id: uid(), createdAt: d - 50e5, title: "Q2 MRR growth by plan", messages: [] },
    { id: uid(), createdAt: d - 26e6, title: "Refund policy edge cases", messages: [] },
    { id: uid(), createdAt: d - 28e6, title: "Draft: infra migration status update", messages: [] },
    { id: uid(), createdAt: d - 30e6, title: "Top support themes — last week", messages: [] },
  ];
}

/* ===================== Backend ===================== */
const DEFAULT_BACKEND = "http://localhost:8000";
const getBackend = () => (localStorage.getItem("atlas.backend") || DEFAULT_BACKEND).replace(/\/+$/, "");

// pretty-print a tool input/output payload for the step card
function fmtPayload(v) {
  if (v == null) return "";
  if (typeof v === "string") return v;
  if (typeof v === "object") {
    // single string field (sql, code, query…) reads cleaner unwrapped
    const keys = Object.keys(v);
    if (keys.length === 1 && typeof v[keys[0]] === "string") return v[keys[0]];
    try { return JSON.stringify(v, null, keys.length > 2 ? 2 : 0); } catch (e) { return String(v); }
  }
  return String(v);
}

/* Parse a POST'd SSE stream, invoking onEvent(obj) for each `data:` frame.
   Resolves when the server closes the stream. Throws on network/HTTP error. */
async function streamChat(url, payload, { signal, onEvent }) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(payload),
    credentials: "include",
    signal,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  if (!res.body) throw new Error("no response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let sep;
    // SSE frames are separated by a blank line
    while ((sep = buf.search(/\r?\n\r?\n/)) !== -1) {
      const frame = buf.slice(0, sep);
      buf = buf.slice(sep + (buf[sep] === "\r" ? 4 : 2));
      const data = frame
        .split(/\r?\n/)
        .filter((l) => l.startsWith("data:"))
        .map((l) => l.slice(5).replace(/^ /, ""))
        .join("\n");
      if (!data || data === "[DONE]") continue;
      try { onEvent(JSON.parse(data)); } catch (e) { /* ignore keep-alives / partial */ }
    }
  }
}

async function postApproval(id, body) {
  const res = await fetch(`${getBackend()}/approvals/${id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

/* ===================== App ===================== */
function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem("atlas.theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
  const [collapsed, setCollapsed] = useState(() => innerWidth < 820);
  const [conversations, setConversations] = useState(() => {
    try { const s = JSON.parse(localStorage.getItem(STORE_KEY)); if (s && s.length) return s; } catch (e) {}
    return seed();
  });
  const [activeId, setActiveId] = useState(() => null);
  const [busy, setBusy] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [skillsOpen, setSkillsOpen] = useState(false);
  const [backendUrl, setBackendUrl] = useState(() => getBackend());
  const [conn, setConn] = useState("checking"); // checking | online | offline
  const stopRef = useRef(false);
  const abortRef = useRef(null);
  const scrollRef = useRef(null);

  // active conversation: null => brand new (empty) screen
  const active = conversations.find((c) => c.id === activeId) || null;

  useEffect(() => { document.documentElement.setAttribute("data-theme", theme); localStorage.setItem("atlas.theme", theme); }, [theme]);
  useEffect(() => { try { localStorage.setItem(STORE_KEY, JSON.stringify(conversations.slice(0, 40))); } catch (e) {} }, [conversations]);
  useEffect(() => { localStorage.setItem("atlas.backend", backendUrl); }, [backendUrl]);

  // probe the backend so the header pill reflects reality
  useEffect(() => {
    let alive = true;
    setConn("checking");
    (async () => {
      try {
        await fetch(backendUrl + "/", { method: "GET", mode: "no-cors" });
        if (alive) setConn("online");
      } catch (e) { if (alive) setConn("offline"); }
    })();
    return () => { alive = false; };
  }, [backendUrl]);

  function changeBackend() {
    const next = prompt("Atlas backend URL", backendUrl);
    if (next && next.trim()) setBackendUrl(next.trim().replace(/\/+$/, ""));
  }

  const scrollDown = useCallback((smooth = true) => {
    const el = scrollRef.current; if (!el) return;
    requestAnimationFrame(() => { el.scrollTo({ top: el.scrollHeight, behavior: smooth ? "smooth" : "auto" }); });
  }, []);

  // mutate a message inside a conversation
  const patchMsg = (convoId, msgId, patch) => setConversations((cs) => cs.map((c) => c.id !== convoId ? c : {
    ...c, messages: c.messages.map((m) => m.id !== msgId ? m : (typeof patch === "function" ? patch(m) : { ...m, ...patch })),
  }));

  async function runTurn(convoId, message, agentMsgId) {
    stopRef.current = false;
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setBusy(true);

    // accumulators kept outside React state so handlers stay consistent
    let answer = "";
    let steps = [];
    const stepAt = {}; // event id -> index in steps

    const onEvent = (evt) => {
      switch (evt && evt.type) {
        case "token": {
          answer += evt.content || "";
          patchMsg(convoId, agentMsgId, (m) => ({ ...m, status: "streaming", reveal: answer, approval: null }));
          scrollDown(false);
          break;
        }
        case "tool_step": {
          const name = evt.name || "";
          if (evt.phase === "start") {
            if (!name) break; // skip unnamed placeholder frames
            stepAt[evt.id] = steps.length;
            steps = [...steps, { id: evt.id, tool: name, input: fmtPayload(evt.input), result: "", status: "running" }];
          } else if (evt.phase === "end") {
            const done = { result: fmtPayload(evt.output), status: evt.status === "error" ? "error" : "done" };
            const i = stepAt[evt.id];
            if (i != null) steps = steps.map((s, j) => (j === i ? { ...s, ...done } : s));
            else if (name) steps = [...steps, { id: evt.id, tool: name, input: fmtPayload(evt.input), ...done }];
          }
          patchMsg(convoId, agentMsgId, (m) => ({ ...m, status: answer ? "streaming" : "tools", steps: [...steps] }));
          scrollDown(false);
          break;
        }
        case "approval_request": {
          patchMsg(convoId, agentMsgId, (m) => ({
            ...m, status: "awaiting_approval",
            approval: { id: evt.id, tool: evt.tool, input: evt.input, reason: evt.reason, editable: !!evt.editable },
          }));
          scrollDown();
          break;
        }
        case "error": {
          patchMsg(convoId, agentMsgId, (m) => ({ ...m, status: "error", errorMsg: evt.message, recoverable: !!evt.recoverable }));
          break;
        }
        case "done": {
          patchMsg(convoId, agentMsgId, (m) => ({
            ...m, status: "done", content: answer || m.reveal || "", reveal: undefined,
            approval: null, messageId: evt.message_id, finishReason: evt.finish_reason,
          }));
          scrollDown();
          break;
        }
        default: break;
      }
    };

    try {
      await streamChat(`${backendUrl}/chat`, { conversation_id: convoId, message }, { signal: ctrl.signal, onEvent });
      setConn("online");
      // finalize if the server closed without an explicit `done`
      patchMsg(convoId, agentMsgId, (m) =>
        (m.status === "done" || m.status === "error" || m.status === "awaiting_approval")
          ? m : ({ ...m, status: "done", content: answer || m.reveal || "", reveal: undefined }));
    } catch (e) {
      if (ctrl.signal.aborted) {
        patchMsg(convoId, agentMsgId, (m) => ({ ...m, status: "done", content: answer || m.reveal || "_(stopped)_", reveal: undefined, approval: null }));
      } else {
        setConn("offline");
        patchMsg(convoId, agentMsgId, (m) => ({ ...m, status: "error", recoverable: true, errorMsg: e.message }));
      }
    } finally {
      if (abortRef.current === ctrl) abortRef.current = null;
      setBusy(false);
    }
  }

  // resolve a paused approval; the open /chat stream resumes from its checkpoint
  async function resolveApproval(convoId, msgId, approval, decision, editedInput, note) {
    patchMsg(convoId, msgId, (m) => ({ ...m, approval: null, status: m.reveal ? "streaming" : "tools" }));
    const body = { decision };
    if (decision === "approve" && editedInput !== undefined) body.edited_input = editedInput;
    if (note) body.note = note;
    try {
      await postApproval(approval.id, body);
    } catch (e) {
      patchMsg(convoId, msgId, (m) => ({ ...m, status: "error", recoverable: true, errorMsg: "Approval failed — " + e.message }));
    }
  }

  function send(text) {
    const userMsg = { id: uid(), role: "user", content: text };
    const agentMsg = { id: uid(), role: "agent", status: "thinking", steps: null, content: "" };
    let convoId = activeId;

    if (!active) {
      convoId = uid();
      const convo = { id: convoId, createdAt: Date.now(), title: text.slice(0, 48), messages: [userMsg, agentMsg] };
      setConversations((cs) => [convo, ...cs]);
      setActiveId(convoId);
    } else {
      setConversations((cs) => cs.map((c) => c.id !== convoId ? c : { ...c, messages: [...c.messages, userMsg, agentMsg] }));
    }
    scrollDown();
    runTurn(convoId, text, agentMsg.id);
  }

  function regenerate(agentMsg) {
    if (!active || busy) return;
    const idx = active.messages.findIndex((m) => m.id === agentMsg.id);
    if (idx < 1) return;
    const prevUser = active.messages.slice(0, idx).reverse().find((m) => m.role === "user");
    if (!prevUser) return;
    patchMsg(active.id, agentMsg.id, { status: "thinking", steps: null, content: "", reveal: "", approval: null });
    runTurn(active.id, prevUser.content, agentMsg.id);
  }

  function newChat() { setActiveId(null); setCollapsed(innerWidth < 820 ? true : collapsed); }
  function deleteConvo(id) {
    setConversations((cs) => cs.filter((c) => c.id !== id));
    if (id === activeId) setActiveId(null);
  }

  const msgs = active ? active.messages : [];
  const lastAgentId = [...msgs].reverse().find((m) => m.role === "agent")?.id;

  return (
    <div className={"app" + (collapsed ? " collapsed" : "")}>
      <Sidebar
        conversations={conversations} activeId={activeId}
        onSelect={(id) => { setActiveId(id); if (innerWidth < 820) setCollapsed(true); }}
        onNew={newChat} onDelete={deleteConvo}
        onToggle={() => setCollapsed((v) => !v)}
        onOpenSkills={() => setSkillsOpen(true)}
        theme={theme} onTheme={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
        user={USER}
      />
      <div className="scrim" onClick={() => setCollapsed(true)} />
      <main className="main">
        <div className={"topbar" + (scrolled ? " scrolled" : "")}>
          <button className="icon-btn menu-btn" onClick={() => setCollapsed((v) => !v)}><I.menu /></button>
          <span className="conv-title">{active ? active.title : "New chat"}</span>
          <button className={"agent-pill conn-" + conn} onClick={changeBackend} title={backendUrl + " — click to change"}>
            <span className="dot-online" /> {conn === "online" ? "Atlas · online" : conn === "offline" ? "Backend offline" : "Connecting…"}
          </button>
        </div>
        <div className="chat-scroll" ref={scrollRef} onScroll={(e) => setScrolled(e.target.scrollTop > 8)}>
          {!active || msgs.length === 0 ? (
            <EmptyState greeting={greetingText()} onPick={send} onBrowseSkills={() => setSkillsOpen(true)} />
          ) : (
            <div className="thread">
              {msgs.map((m) => (
                <Message key={m.id} msg={m} onCopy={(t) => navigator.clipboard.writeText(t)} onRetry={regenerate}
                  onApproval={(decision, edited, note) => resolveApproval(active.id, m.id, m.approval, decision, edited, note)}
                  isLast={m.id === lastAgentId && !busy} />
              ))}
            </div>
          )}
        </div>
        <Composer onSend={send} busy={busy} onStop={() => { stopRef.current = true; abortRef.current && abortRef.current.abort(); }} />
      </main>
      <SkillsModal open={skillsOpen} onClose={() => setSkillsOpen(false)} onPick={(t) => { setSkillsOpen(false); send(t); }} />
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
