/* ============================================================
   ck-components.jsx
   Recreations of CopilotKit's prebuilt chat components, themed
   via the --copilot-kit-* variables. Class names mirror the real
   library (.copilotKitMessages, .copilotKitInput, …) so the markup
   reads like a styled CopilotKit instance.
   ============================================================ */
/* global React, marked, DOMPurify, CopilotKitContext, GRAPH_NODES */
const { useState, useRef, useEffect, useLayoutEffect, useContext, useCallback } = React;

/* ---------- icons ---------- */
const Ic = {
  spark: (p) => <svg viewBox="0 0 24 24" fill="currentColor" {...p}><path d="M12 2l1.7 6.6L20 10l-6.3 1.4L12 18l-1.7-6.6L4 10l6.3-1.4z"/></svg>,
  send: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M12 19V6M5 12l7-7 7 7"/></svg>,
  stop: (p) => <svg viewBox="0 0 24 24" fill="currentColor" {...p}><rect x="6" y="6" width="12" height="12" rx="2.5"/></svg>,
  plus: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" {...p}><path d="M12 5v14M5 12h14"/></svg>,
  copy: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><rect x="9" y="9" width="11" height="11" rx="2.5"/><path d="M5 15V5a2 2 0 0 1 2-2h8"/></svg>,
  check: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M20 6 9 17l-5-5"/></svg>,
  retry: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg>,
  chev: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="m9 6 6 6-6 6"/></svg>,
  trash: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/></svg>,
  menu: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" {...p}><path d="M4 6h16M4 12h16M4 18h16"/></svg>,
  sidebar: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="M9 4v16"/></svg>,
  grid: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></svg>,
  x: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M6 6l12 12M18 6 6 18"/></svg>,
  bolt: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M13 2 4 14h7l-1 8 9-12h-7z"/></svg>,
  sun: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>,
  moon: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>,
};
const SkillGlyph = {
  book: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H19v15H6a2 2 0 0 0-2 2z"/><path d="M19 16H6a2 2 0 0 0-2 2"/></svg>,
  bars: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M6 20V10M12 20V4M18 20v-7"/></svg>,
  chat: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M20 12a8 8 0 0 1-11.4 7.2L4 20l.9-4.4A8 8 0 1 1 20 12z"/></svg>,
  spark: <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l1.6 6.4L20 10l-6.4 1.6L12 18l-1.6-6.4L4 10l6.4-1.6z"/></svg>,
  trend: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M3 17l6-6 4 4 7-7"/><path d="M17 7h4v4"/></svg>,
  globe: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18A14 14 0 0 1 12 3z"/></svg>,
};

/* ============================================================
   CopilotKit registration hooks (mock)
   ============================================================ */
function useCopilotAction(def) {
  const ck = useContext(CopilotKitContext);
  useEffect(() => {
    if (!ck) return;
    return ck.registerAction(def);
    // eslint-disable-next-line
  }, [def.name]);
}
function useCoAgentStateRender(/* { name, render } */) {
  // In real CopilotKit this registers a renderer for streaming agent state.
  // Our AgentStateRender component below performs the same job inline.
}

/* ============================================================
   Markdown
   ============================================================ */
function escapeHtml(s) { return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
function Markdown({ text }) {
  const ref = useRef(null);
  useLayoutEffect(() => {
    if (!ref.current) return;
    let html = text || "";
    try {
      marked.setOptions({ breaks: true, gfm: true });
      html = marked.parse(text || "");
      if (window.DOMPurify) html = DOMPurify.sanitize(html);
    } catch (e) { html = escapeHtml(text || ""); }
    ref.current.innerHTML = html;
    ref.current.querySelectorAll("pre").forEach((pre) => {
      if (pre.parentElement.classList.contains("ck-code-wrap")) return;
      const wrap = document.createElement("div");
      wrap.className = "ck-code-wrap";
      pre.parentNode.insertBefore(wrap, pre);
      wrap.appendChild(pre);
      const btn = document.createElement("button");
      btn.className = "ck-code-copy";
      btn.textContent = "Copy";
      btn.onclick = () => { navigator.clipboard.writeText(pre.innerText); btn.textContent = "Copied"; setTimeout(() => (btn.textContent = "Copy"), 1300); };
      wrap.appendChild(btn);
    });
    ref.current.querySelectorAll("a").forEach((a) => { a.target = "_blank"; a.rel = "noopener"; });
  }, [text]);
  return <div className="ck-markdown" ref={ref} />;
}

/* ============================================================
   CoAgent state render  (useCoAgentStateRender generative UI)
   ============================================================ */
function AgentStateRender({ state }) {
  const [open, setOpen] = useState(true);
  const running = state.active;
  useEffect(() => { if (!running && state.tools.length) { const id = setTimeout(() => setOpen(false), 400); return () => clearTimeout(id); } }, [running]);
  const doneTools = state.tools.filter((t) => t.status !== "running").length;
  const label = running ? "CoAgent running…" : `${state.name}`;
  return (
    <div className={"ck-coagent" + (open ? " open" : "")}>
      <button className="ck-coagent-head" onClick={() => setOpen(!open)}>
        <span className="ck-spark"><Ic.spark /></span>
        <span>{running ? label : "Agent run"}</span>
        <span className="agent-name">{state.name}</span>
        {state.tools.length > 0 && <span className="ck-count">{doneTools}/{state.tools.length} tools</span>}
        <span className="ck-chev"><Ic.chev /></span>
      </button>
      <div className="ck-coagent-body"><div>
        <div className="ck-nodes">
          {state.nodes.map((n) => (
            <span key={n.id} className={"ck-node-pill " + n.status}>
              <span className="n-dot" />{n.label}
            </span>
          ))}
        </div>
        {state.tools.length > 0 && (
          <div className="ck-tools">
            {state.tools.map((t) => (
              <div key={t.id} className={"ck-tool " + t.status}>
                <span className="node" />
                <div className="t-name">{t.name}</div>
                {t.input && <div className="t-in">{t.input}</div>}
                <div className="t-out">{t.status === "running" ? "running…" : (t.output || (t.status === "error" ? "failed" : "done"))}</div>
              </div>
            ))}
          </div>
        )}
      </div></div>
    </div>
  );
}

/* ============================================================
   HITL interrupt  (renderAndWaitForResponse)
   ============================================================ */
function InterruptCard({ interrupt, onResolve }) {
  const input = interrupt.input;
  const keys = input && typeof input === "object" ? Object.keys(input) : [];
  const singleKey = keys.length === 1 && typeof input[keys[0]] === "string" ? keys[0] : null;
  const initial = singleKey ? input[singleKey]
    : typeof input === "string" ? input
    : input == null ? "" : JSON.stringify(input, null, 2);
  const [draft, setDraft] = useState(initial);
  const [note, setNote] = useState("");
  const [sent, setSent] = useState(null);

  function buildArgs() {
    if (!interrupt.editable || draft === initial) return input;
    if (singleKey) return { ...input, [singleKey]: draft };
    if (typeof input === "string") return draft;
    try { return JSON.parse(draft); } catch (e) { return input; }
  }
  function decide(type) {
    if (sent) return;
    setSent(type);
    onResolve({ type, args: type === "approve" ? buildArgs() : undefined, note: note.trim() || undefined });
  }
  return (
    <div className={"ck-interrupt" + (sent ? " resolved" : "")}>
      <div className="ck-int-head">
        <span className="ck-int-badge"><Ic.bolt style={{ width: 12, height: 12 }} /> Action required</span>
        <span className="ck-int-tool">{interrupt.action}</span>
      </div>
      {interrupt.reason && <p className="ck-int-reason">{interrupt.reason}</p>}
      <div className="ck-int-label">{interrupt.editable ? "Arguments · editable before approve" : "Arguments"}</div>
      {interrupt.editable ? (
        <textarea className="ck-int-input" value={draft} spellCheck={false} disabled={!!sent}
          onChange={(e) => setDraft(e.target.value)} rows={Math.min(12, draft.split("\n").length + 1)} />
      ) : (
        <pre className="ck-int-input ro">{initial}</pre>
      )}
      <input className="ck-int-note" placeholder="Note for the audit trail (optional)" value={note}
        disabled={!!sent} onChange={(e) => setNote(e.target.value)} />
      <div className="ck-int-actions">
        <button className="ck-int-btn reject" disabled={!!sent} onClick={() => decide("reject")}>Reject</button>
        <button className="ck-int-btn approve" disabled={!!sent} onClick={() => decide("approve")}>
          {sent === "approve" ? "Approved" : sent === "reject" ? "Rejected" : "Approve & run"}
        </button>
      </div>
    </div>
  );
}

/* ============================================================
   Message
   ============================================================ */
function CopilotMessage({ msg, onCopy, onRegenerate, onResolveInterrupt, isLast, busy }) {
  const [copied, setCopied] = useState(false);
  if (msg.role === "user") {
    return <div className="copilotKitMessage copilotKitUserMessage"><div className="bubble">{msg.content}</div></div>;
  }
  const thinking = msg.status === "thinking";
  const streaming = msg.status === "streaming";
  return (
    <div className="copilotKitMessage copilotKitAssistantMessage">
      <div className="ck-avatar"><span className="glyph" /></div>
      <div className="ck-msg-col">
        {msg.agentState && (msg.agentState.nodes.length > 0 || msg.agentState.tools.length > 0) && (
          <AgentStateRender state={msg.agentState} />
        )}
        {thinking && !msg.agentState && (
          <div className="ck-generating"><span className="dots"><i /><i /><i /></span> Routing to CoAgent…</div>
        )}
        {msg.status === "awaiting_input" && msg.interrupt && (
          <InterruptCard interrupt={msg.interrupt} onResolve={(d) => onResolveInterrupt(msg, d)} />
        )}
        {msg.status === "error" && (
          <div className="ck-generating" style={{ color: "#ef4444" }}>{msg.errorMsg || "CoAgent run failed."}</div>
        )}
        {streaming && <div className="ck-markdown" style={{ whiteSpace: "pre-wrap" }}>{msg.content}<span className="ck-cursor" /></div>}
        {msg.status === "complete" && msg.content && <Markdown text={msg.content} />}
        {msg.status === "complete" && (
          <div className="copilotKitMessageControls">
            <button className={"copilotKitMessageControlButton" + (copied ? " ok" : "")} onClick={() => { onCopy(msg.content); setCopied(true); setTimeout(() => setCopied(false), 1300); }}>
              {copied ? <Ic.check /> : <Ic.copy />}{copied ? "Copied" : "Copy"}
            </button>
            {isLast && !busy && <button className="copilotKitMessageControlButton" onClick={() => onRegenerate(msg)}><Ic.retry />Regenerate</button>}
          </div>
        )}
      </div>
    </div>
  );
}

/* ============================================================
   Empty state
   ============================================================ */
function CopilotEmpty({ greeting, suggestions, onPick }) {
  return (
    <div className="ck-empty">
      <div className="ck-empty-logo"><span className="glyph" /></div>
      <h1>{greeting}</h1>
      <p className="sub">Ask the Atlas CoAgent to search docs, query the warehouse, or scan Slack — it streams its LangGraph state as it works.</p>
      <div className="ck-suggestions">
        {suggestions.map((s, i) => (
          <button key={i} className="copilotKitSuggestion" onClick={() => onPick(s.text)}>
            <span className="s-action">{s.action}</span>
            <span className="s-text">{s.text}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

/* ============================================================
   Input  (copilotKitInput)
   ============================================================ */
function CopilotInput({ onSend, busy, onStop }) {
  const [val, setVal] = useState("");
  const ta = useRef(null);
  const grow = () => { const el = ta.current; if (!el) return; el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 190) + "px"; };
  useEffect(grow, [val]);
  const submit = () => { const t = val.trim(); if (!t || busy) return; onSend(t); setVal(""); requestAnimationFrame(grow); };
  return (
    <div className="copilotKitInput">
      <div className="copilotKitInputInner">
        <div className="copilotKitInputControls">
          <textarea ref={ta} value={val} rows={1} placeholder="Message the Atlas CoAgent…"
            onChange={(e) => setVal(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }} />
          {busy
            ? <button className="copilotKitInputControlButton stop" onClick={onStop} title="Stop"><Ic.stop /></button>
            : <button className="copilotKitInputControlButton" disabled={!val.trim()} onClick={submit} title="Send"><Ic.send /></button>}
        </div>
        <div className="ck-poweredby">Powered by <b>CopilotKit</b> · agent <code style={{ fontFamily: "var(--font-mono)", fontSize: 10.5 }}>atlas_coagent</code></div>
      </div>
    </div>
  );
}

Object.assign(window, {
  Ic, SkillGlyph, Markdown, AgentStateRender, InterruptCard, CopilotMessage,
  CopilotEmpty, CopilotInput, useCopilotAction, useCoAgentStateRender,
});
