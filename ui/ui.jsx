/* global React, marked, DOMPurify */
const { useState, useRef, useEffect, useLayoutEffect } = React;

/* ===================== Icons ===================== */
const I = {
  plus: (p) => <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><path d="M12 5v14M5 12h14"/></svg>,
  sidebar: (p) => <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="M9 4v16"/></svg>,
  send: (p) => <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M12 19V6M5 12l7-7 7 7"/></svg>,
  stop: (p) => <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" {...p}><rect x="6" y="6" width="12" height="12" rx="2.5"/></svg>,
  copy: (p) => <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><rect x="9" y="9" width="11" height="11" rx="2.5"/><path d="M5 15V5a2 2 0 0 1 2-2h8"/></svg>,
  check: (p) => <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M20 6 9 17l-5-5"/></svg>,
  retry: (p) => <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg>,
  sun: (p) => <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>,
  moon: (p) => <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>,
  chev: (p) => <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="m9 6 6 6-6 6"/></svg>,
  spark: (p) => <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" {...p}><path d="M12 2l1.6 6.4L20 10l-6.4 1.6L12 18l-1.6-6.4L4 10l6.4-1.6z"/></svg>,
  trash: (p) => <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/></svg>,
  menu: (p) => <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" {...p}><path d="M4 6h16M4 12h16M4 18h16"/></svg>,
  grid: (p) => <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></svg>,
  x: (p) => <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M6 6l12 12M18 6 6 18"/></svg>,
  arrow: (p) => <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M5 12h14M13 6l6 6-6 6"/></svg>,
};
const Glyph = () => <span className="glyph" />;

/* ===================== Markdown ===================== */
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
    // wrap <pre> in a copy container
    ref.current.querySelectorAll("pre").forEach((pre) => {
      if (pre.parentElement.classList.contains("code-wrap")) return;
      const wrap = document.createElement("div");
      wrap.className = "code-wrap";
      pre.parentNode.insertBefore(wrap, pre);
      wrap.appendChild(pre);
      const btn = document.createElement("button");
      btn.className = "code-copy";
      btn.innerHTML = "Copy";
      btn.onclick = () => {
        navigator.clipboard.writeText(pre.innerText);
        btn.innerHTML = "Copied";
        setTimeout(() => (btn.innerHTML = "Copy"), 1400);
      };
      wrap.appendChild(btn);
    });
    ref.current.querySelectorAll("a").forEach((a) => { a.target = "_blank"; a.rel = "noopener"; });
  }, [text]);
  return <div className="markdown" ref={ref} />;
}

/* ===================== Tool steps ===================== */
function ToolSteps({ steps, running }) {
  const [open, setOpen] = useState(true);
  const terminal = (s) => s.status !== "running" && s.status !== "pending";
  const hasRunning = steps.some((s) => !terminal(s));
  const allDone = steps.length > 0 && !hasRunning;
  const live = running || hasRunning;
  useEffect(() => { if (allDone && !running) setOpen(false); }, [allDone, running]);
  const doneCount = steps.filter(terminal).length;
  const label = live ? "Working…" : `Used ${steps.length} tool${steps.length > 1 ? "s" : ""}`;
  return (
    <div className={"steps" + (open ? " open" : "")}>
      <button className="steps-head" onClick={() => setOpen(!open)}>
        <span className="spark"><I.spark /></span>
        <span>{label}</span>
        <span className="count">· {doneCount}/{steps.length}</span>
        <I.chev className="chev" />
      </button>
      <div className="steps-body"><div><div className="steps-list">
        {steps.map((s, i) => (
          <div key={s.id || i} className={"step " + (s.status === "ok" ? "done" : s.status)}>
            <span className="node" />
            <div className="tool">{s.tool}</div>
            {s.input && <div className="inp">{s.input}</div>}
            <div className="res">{s.status === "running" ? "running…" : (s.result || (s.status === "error" ? "failed" : "done"))}</div>
          </div>
        ))}
      </div></div></div>
    </div>
  );
}

/* ===================== Approval card ===================== */
function ApprovalCard({ approval, onApproval }) {
  const input = approval.input;
  const keys = input && typeof input === "object" ? Object.keys(input) : [];
  const singleKey = keys.length === 1 && typeof input[keys[0]] === "string" ? keys[0] : null;
  const initial = singleKey ? input[singleKey]
    : typeof input === "string" ? input
    : input == null ? "" : JSON.stringify(input, null, 2);
  const [draft, setDraft] = useState(initial);
  const [note, setNote] = useState("");
  const [sent, setSent] = useState(null); // 'approve' | 'reject'

  function buildEdited() {
    if (!approval.editable || draft === initial) return undefined;
    if (singleKey) return { ...input, [singleKey]: draft };
    if (typeof input === "string") return draft;
    try { return JSON.parse(draft); } catch (e) { return input; }
  }
  function decide(decision) {
    if (sent) return;
    setSent(decision);
    onApproval(decision, decision === "approve" ? buildEdited() : undefined, note.trim() || undefined);
  }

  return (
    <div className={"approval" + (sent ? " resolved" : "")}>
      <div className="appr-head">
        <span className="appr-badge">Approval required</span>
        <span className="appr-tool">{approval.tool}</span>
      </div>
      {approval.reason && <p className="appr-reason">{approval.reason}</p>}
      <div className="appr-input-label">{approval.editable ? "Review · editable before approve" : "Input"}</div>
      {approval.editable ? (
        <textarea className="appr-input" value={draft} spellCheck={false}
          disabled={!!sent} onChange={(e) => setDraft(e.target.value)} rows={Math.min(12, draft.split("\n").length + 1)} />
      ) : (
        <pre className="appr-input ro">{initial}</pre>
      )}
      <input className="appr-note" placeholder="Add a note for the audit trail (optional)"
        value={note} disabled={!!sent} onChange={(e) => setNote(e.target.value)} />
      <div className="appr-actions">
        <button className="appr-btn reject" disabled={!!sent} onClick={() => decide("reject")}>Reject</button>
        <button className="appr-btn approve" disabled={!!sent} onClick={() => decide("approve")}>
          {sent === "approve" ? "Approved" : sent === "reject" ? "Rejected" : "Approve & run"}
        </button>
      </div>
    </div>
  );
}

/* ===================== Message ===================== */
function Message({ msg, onCopy, onRetry, onApproval, isLast }) {
  if (msg.role === "user") {
    return <div className="msg user"><div className="user-bubble">{msg.content}</div></div>;
  }
  const [copied, setCopied] = useState(false);
  const showThinking = msg.status === "thinking";
  const streaming = msg.status === "streaming";
  return (
    <div className="msg agent">
      <div className="msg-avatar"><Glyph /></div>
      <div className="msg-body">
        {msg.steps && msg.steps.length > 0 && (
          <ToolSteps steps={msg.steps} running={msg.status === "tools" || msg.status === "thinking" || msg.status === "awaiting_approval"} />
        )}
        {showThinking && !msg.steps?.length && (
          <div className="thinking"><span className="pulse"><i /><i /><i /></span> Thinking…</div>
        )}
        {msg.status === "tools" && (
          <div className="thinking"><span className="pulse"><i /><i /><i /></span> Running tools…</div>
        )}
        {msg.status === "awaiting_approval" && msg.approval && (
          <ApprovalCard approval={msg.approval} onApproval={onApproval} />
        )}
        {msg.status === "error" && (
          <div className="err-box">
            <span>{msg.errorMsg || "Couldn't reach the agent."}</span>
            {(msg.recoverable !== false) && <button onClick={() => onRetry(msg)}>Retry</button>}
          </div>
        )}
        {streaming && <div className="stream-text">{msg.reveal}<span className="cursor" /></div>}
        {msg.status === "done" && msg.content && <Markdown text={msg.content} />}
        {msg.status === "done" && (
          <div className="msg-actions">
            <button className={"act" + (copied ? " ok" : "")} onClick={() => { onCopy(msg.content); setCopied(true); setTimeout(() => setCopied(false), 1400); }}>
              {copied ? <I.check /> : <I.copy />}{copied ? "Copied" : "Copy"}
            </button>
            {isLast && <button className="act" onClick={() => onRetry(msg)}><I.retry />Regenerate</button>}
          </div>
        )}
      </div>
    </div>
  );
}

/* ===================== Sidebar ===================== */
function Sidebar({ conversations, activeId, onSelect, onNew, onDelete, onToggle, onOpenSkills, theme, onTheme, user }) {
  const groups = [
    { label: "Today", items: [] }, { label: "Yesterday", items: [] }, { label: "Earlier", items: [] },
  ];
  const now = Date.now();
  conversations.forEach((c) => {
    const age = now - c.createdAt;
    if (age < 864e5) groups[0].items.push(c);
    else if (age < 1728e5) groups[1].items.push(c);
    else groups[2].items.push(c);
  });
  return (
    <aside className="sidebar">
      <div className="sb-rail">
        <div className="rail-brand"><div className="brand-mark"><Glyph /></div></div>
        <div className="rail-group">
          <button className="rail-btn" onClick={onToggle} title="Expand sidebar"><I.sidebar /></button>
          <button className="rail-btn rail-new" onClick={onNew} title="New chat"><I.plus /></button>
          <button className="rail-btn" onClick={onOpenSkills} title="Skills"><I.grid /></button>
        </div>
        <div className="rail-spacer" />
        <div className="rail-group">
          <button className="rail-btn" onClick={onTheme} title="Toggle theme">{theme === "dark" ? <I.sun /> : <I.moon />}</button>
          <button className="rail-avatar" onClick={onToggle} title={user.name}>{user.initials}</button>
        </div>
      </div>
      <div className="sb-inner">
        <div className="sb-head">
          <div className="brand">
            <div className="brand-mark"><Glyph /></div>
            <span className="brand-name">Atlas</span>
          </div>
          <button className="icon-btn" onClick={onToggle} title="Collapse sidebar"><I.sidebar /></button>
        </div>
        <button className="new-chat" onClick={onNew}><I.plus /> New chat</button>
        <button className="sb-skills" onClick={onOpenSkills}>
          <span className="sk-ic"><I.grid /></span>
          <span className="sk-label">Skills</span>
          <span className="sk-count">{SKILLS.length}</span>
        </button>
        <div className="sb-scroll">
          {groups.filter((g) => g.items.length).map((g) => (
            <div key={g.label}>
              <div className="group-label">{g.label}</div>
              {g.items.map((c) => (
                <button key={c.id} className={"convo" + (c.id === activeId ? " active" : "")} onClick={() => onSelect(c.id)}>
                  <span className="title">{c.title}</span>
                  <span className="del" onClick={(e) => { e.stopPropagation(); onDelete(c.id); }} title="Delete"><I.trash /></span>
                </button>
              ))}
            </div>
          ))}
        </div>
        <div className="sb-foot">
          <div className="user-chip">
            <div className="avatar">{user.initials}</div>
            <div className="user-meta"><span className="name">{user.name}</span><span className="role">{user.role}</span></div>
          </div>
          <button className="icon-btn" onClick={onTheme} title="Toggle theme">{theme === "dark" ? <I.sun /> : <I.moon />}</button>
        </div>
      </div>
    </aside>
  );
}

/* ===================== Skills (org-level) ===================== */
const SKILLS = [
  { name: "Docs & Knowledge", icon: "book", tint: 47,
    desc: "Search the internal wiki, policies, and runbooks, then answer with cited sources.",
    tools: ["search_docs"], example: "What's our PTO policy for contractors?" },
  { name: "Warehouse Analyst", icon: "bars", tint: 240,
    desc: "Run SQL over the analytics warehouse and summarize metrics, trends, and breakdowns.",
    tools: ["query_warehouse", "run_python"], example: "Pull Q2 MRR growth and break it down by plan" },
  { name: "Support Triage", icon: "chat", tint: 150,
    desc: "Scan Slack support channels to cluster recurring issues and surface emerging themes.",
    tools: ["slack_search"], example: "Summarize last week's #support threads by theme" },
  { name: "Onboarding Assistant", icon: "spark", tint: 300,
    desc: "Generate role-specific onboarding checklists from the People wiki.",
    tools: ["search_docs"], example: "Build an onboarding checklist for a new eng hire" },
  { name: "Forecasting", icon: "trend", tint: 200,
    desc: "Project signups, revenue, and usage from historical warehouse data.",
    tools: ["run_python", "query_warehouse"], example: "Forecast next month's signups from recent trend" },
  { name: "Web Research", icon: "globe", tint: 90,
    desc: "Look things up on the public web and bring back a concise, sourced briefing.",
    tools: ["web_search"], example: "Research how competitors price their team plans" },
];

const SkillIco = {
  book: <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H19v15H6a2 2 0 0 0-2 2z"/><path d="M19 16H6a2 2 0 0 0-2 2"/></svg>,
  bars: <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M6 20V10M12 20V4M18 20v-7"/></svg>,
  chat: <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M20 12a8 8 0 0 1-11.4 7.2L4 20l.9-4.4A8 8 0 1 1 20 12z"/></svg>,
  spark: <svg viewBox="0 0 24 24" width="17" height="17" fill="currentColor"><path d="M12 2l1.6 6.4L20 10l-6.4 1.6L12 18l-1.6-6.4L4 10l6.4-1.6z"/></svg>,
  trend: <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M3 17l6-6 4 4 7-7"/><path d="M17 7h4v4"/></svg>,
  globe: <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18A14 14 0 0 1 12 3z"/></svg>,
};

function SkillsModal({ open, onClose, onPick }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="sk-overlay" onClick={onClose}>
      <div className="sk-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Skills">
        <div className="sk-modal-head">
          <div className="sk-modal-titles">
            <h2>Skills</h2>
            <p>Capabilities your workspace admins have enabled for everyone in the org.</p>
          </div>
          <button className="icon-btn" onClick={onClose} title="Close"><I.x /></button>
        </div>
        <div className="sk-grid">
          {SKILLS.map((s) => (
            <button key={s.name} className="skill-card" onClick={() => onPick(s.example)}>
              <div className="skill-top">
                <span className="skill-ico" style={{ color: `oklch(0.58 0.12 ${s.tint})`, background: `oklch(0.58 0.12 ${s.tint} / 0.12)` }}>{SkillIco[s.icon]}</span>
                <span className="skill-badge">Org</span>
              </div>
              <div className="skill-name">{s.name}</div>
              <div className="skill-desc">{s.desc}</div>
              <div className="skill-tools">
                {s.tools.map((t) => <span key={t} className="tool-chip">{t}</span>)}
              </div>
              <span className="skill-try">Try it <I.arrow /></span>
            </button>
          ))}
        </div>
        <div className="sk-modal-foot">
          <span className="dot-online" /> {SKILLS.length} skills available to your workspace · managed in Admin settings
        </div>
      </div>
    </div>
  );
}

/* ===================== Empty state ===================== */
const SUGGESTIONS = [
  { tool: "search_docs", text: "What's our PTO policy for contractors?" },
  { tool: "query_warehouse", text: "Pull Q2 MRR growth and break it down by plan" },
  { tool: "slack_search", text: "Summarize last week's #support threads by theme" },
  { tool: "run_python", text: "Forecast next month's signups from recent trend" },
];
function EmptyState({ onPick, greeting, onBrowseSkills }) {
  return (
    <div className="empty">
      <div className="empty-mark"><Glyph /></div>
      <h1>{greeting}</h1>
      <p className="sub">Ask Atlas to search docs, query the warehouse, or dig through Slack.</p>
      <div className="suggestions">
        {SUGGESTIONS.map((s, i) => (
          <button key={i} className="sugg" onClick={() => onPick(s.text)}>
            <span className="s-tool">{s.tool}</span>
            <span className="s-text">{s.text}</span>
          </button>
        ))}
      </div>
      <button className="browse-skills" onClick={onBrowseSkills}>
        <I.grid /> Browse {SKILLS.length} org skills
      </button>
    </div>
  );
}

/* ===================== Composer ===================== */
function Composer({ onSend, busy, onStop }) {
  const [val, setVal] = useState("");
  const ta = useRef(null);
  const grow = () => { const el = ta.current; if (!el) return; el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 200) + "px"; };
  useEffect(grow, [val]);
  const submit = () => { const t = val.trim(); if (!t || busy) return; onSend(t); setVal(""); requestAnimationFrame(grow); };
  return (
    <div className="composer-zone">
      <div className="composer-inner">
        <div className="composer">
          <textarea
            ref={ta} value={val} rows={1}
            placeholder="Message Atlas…"
            onChange={(e) => setVal(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
          />
          {busy
            ? <button className="send stop" onClick={onStop} title="Stop"><I.stop /></button>
            : <button className="send" disabled={!val.trim()} onClick={submit} title="Send"><I.send /></button>}
        </div>
        <div className="composer-hint">Atlas can make mistakes — verify important results. <kbd>Enter</kbd> to send · <kbd>Shift</kbd>+<kbd>Enter</kbd> for newline</div>
      </div>
    </div>
  );
}

Object.assign(window, { I, Glyph, Markdown, ToolSteps, ApprovalCard, Message, Sidebar, EmptyState, Composer, SkillsModal });
