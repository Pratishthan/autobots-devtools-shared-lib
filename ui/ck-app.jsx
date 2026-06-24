/* ============================================================
   ck-app.jsx — application shell
   A host app surface with CopilotKit docked: thread rail +
   <CopilotChat> + a registered-actions (skills) panel.
   ============================================================ */
/* global React, ReactDOM, CopilotKitProvider, CopilotKitContext, useThreadStore, useCopilotChat,
   useCopilotAction, CopilotMessage, CopilotEmpty, CopilotInput, AgentStateRender, Ic, SkillGlyph, USER,
   useTweaks, TweaksPanel, TweakSection, TweakColor, TweakRadio, TweakToggle */
const { useState, useRef, useEffect, useCallback, useContext } = React;

/* ---- Skills, registered as CopilotKit actions (useCopilotAction) ---- */
const SKILL_ACTIONS = [
  { name: "search_docs", icon: "book", tint: "#6766fc", hitl: false,
    description: "Search the internal wiki, policies, and runbooks; answer with cited sources.",
    parameters: ["query"], example: "What's our PTO policy for contractors?" },
  { name: "query_warehouse", icon: "bars", tint: "#0ea5e9", hitl: true,
    description: "Run SQL over the analytics warehouse. Sensitive schemas require approval.",
    parameters: ["sql"], example: "Pull Q2 MRR growth and break it down by plan" },
  { name: "slack_search", icon: "chat", tint: "#16a34a", hitl: false,
    description: "Scan Slack support channels to cluster recurring issues and themes.",
    parameters: ["channels", "window"], example: "Summarize last week's #support threads by theme" },
  { name: "run_python", icon: "spark", tint: "#a855f7", hitl: false,
    description: "Execute Python for analysis, math, and forecasting over retrieved data.",
    parameters: ["code"], example: "Forecast next month's signups from recent trend" },
  { name: "forecast", icon: "trend", tint: "#f59e0b", hitl: false,
    description: "Project signups, revenue, and usage from historical warehouse data.",
    parameters: ["metric", "horizon"], example: "Forecast next month's signups from recent trend" },
  { name: "web_search", icon: "globe", tint: "#ef4444", hitl: false,
    description: "Look things up on the public web and return a concise, sourced briefing.",
    parameters: ["query"], example: "Research how competitors price their team plans" },
];

const SUGGESTIONS = [
  { action: "search_docs", text: "What's our PTO policy for contractors?" },
  { action: "query_warehouse", text: "Pull Q2 MRR growth and break it down by plan" },
  { action: "slack_search", text: "Summarize last week's #support threads by theme" },
  { action: "run_python", text: "Forecast next month's signups from recent trend" },
];

function greeting() {
  const h = new Date().getHours();
  const t = h < 5 ? "late night" : h < 12 ? "morning" : h < 18 ? "afternoon" : "evening";
  return `Good ${t}, ${USER.name.split(" ")[0]}`;
}

/* registers one CopilotKit action (keeps hook order stable) */
function ActionRegistrar({ def }) { useCopilotAction(def); return null; }

/* ============================================================
   Thread rail
   ============================================================ */
function ThreadRail({ threads, activeId, onSelect, onNew, onDelete, dark, onToggleDark, actionsOpen, onToggleSkills, skillCount, collapsed, onToggleCollapse }) {
  const groups = [
    { label: "Today", items: [] }, { label: "Yesterday", items: [] }, { label: "Earlier", items: [] },
  ];
  const now = Date.now();
  threads.forEach((c) => {
    const age = now - c.createdAt;
    if (age < 864e5) groups[0].items.push(c);
    else if (age < 1728e5) groups[1].items.push(c);
    else groups[2].items.push(c);
  });
  return (
    <aside className="rail">
      <div className="rail-mini">
        <span className="brand-mark"><span className="glyph" /></span>
        <button className="mini-btn" onClick={onToggleCollapse} title="Expand sidebar"><Ic.sidebar /></button>
        <button className="mini-btn mini-new" onClick={onNew} title="New chat"><Ic.plus /></button>
        <button className={"mini-btn" + (actionsOpen ? " active" : "")} onClick={onToggleSkills} title="Skills"><Ic.grid /></button>
        <div className="mini-spacer" />
        <button className="mini-btn" onClick={onToggleDark} title="Toggle theme">{dark ? <Ic.sun /> : <Ic.moon />}</button>
        <button className="mini-avatar" onClick={onToggleCollapse} title={USER.name}>{USER.initials}</button>
      </div>
      <div className="rail-full">
      <div className="rail-head">
        <div className="brand">
          <span className="brand-mark"><span className="glyph" /></span>
          <span className="brand-name">Atlas</span>
        </div>
        <button className="icon-btn" onClick={onToggleCollapse} title="Collapse sidebar"><Ic.sidebar /></button>
      </div>
      <button className="rail-new" onClick={onNew}><Ic.plus /> New chat</button>
      <button className={"rail-skills" + (actionsOpen ? " active" : "")} onClick={onToggleSkills}>
        <span className="sk-ic"><Ic.grid /></span>
        <span className="sk-label">Skills</span>
        <span className="sk-count">{skillCount}</span>
      </button>
      <div className="rail-scroll">
        {groups.filter((g) => g.items.length).map((g) => (
          <div key={g.label}>
            <div className="rail-group-label">{g.label}</div>
            {g.items.map((c) => (
              <button key={c.id} className={"thread-item" + (c.id === activeId ? " active" : "")} onClick={() => onSelect(c.id)}>
                <span className="t-title">{c.title}</span>
                <span className="t-del" onClick={(e) => { e.stopPropagation(); onDelete(c.id); }} title="Delete"><Ic.trash /></span>
              </button>
            ))}
          </div>
        ))}
      </div>
      <div className="rail-foot">
        <span className="avatar">{USER.initials}</span>
        <span className="meta"><span className="n">{USER.name}</span><span className="r">{USER.role}</span></span>
        <button className="icon-btn" onClick={onToggleDark} title="Toggle theme">{dark ? <Ic.sun /> : <Ic.moon />}</button>
      </div>
      </div>
    </aside>
  );
}

/* ============================================================
   Registered actions panel  (the useCopilotAction registry)
   ============================================================ */
function ActionsPanel({ onTrigger }) {
  const ck = useContext(CopilotKitContext);
  const actions = ck ? ck.actions : [];
  return (
    <aside className="actions-panel">
      <div className="actions-head">
        <div className="ah-title"><Ic.bolt /> Registered actions</div>
        <div className="ah-sub">Skills exposed to the CoAgent via <code>useCopilotAction</code>. The agent can call these; click to try one.</div>
      </div>
      <div className="actions-scroll">
        {actions.map((a) => (
          <button key={a.name} className="action-card" onClick={() => onTrigger(a.example)}>
            <div className="ac-top">
              <span className="ac-ico" style={{ color: a.tint, background: `color-mix(in srgb, ${a.tint} 13%, transparent)` }}>{SkillGlyph[a.icon]}</span>
              <span className="ac-name">{a.name}</span>
              {a.hitl && <span className="ac-hitl">HITL</span>}
            </div>
            <div className="ac-desc">{a.description}</div>
            <div className="ac-params">{a.parameters.map((p) => <span key={p} className="ac-param">{p}</span>)}</div>
          </button>
        ))}
      </div>
      <div className="actions-foot">
          <span className={"dot" + (ck && ck.conn === "online" ? " dot-online" : "")} />
          {actions.length} actions registered
          {ck && ck.mode === "live"
            ? <> · <span style={{color: ck.conn === "online" ? "var(--c-green,#16a34a)" : ck.conn === "offline" ? "#ef4444" : "inherit"}}>{ck.conn === "online" ? "live · online" : ck.conn === "offline" ? "live · offline" : "live · connecting…"}</span></>
            : " · runtime mocked"}
        </div>
    </aside>
  );
}

/* ============================================================
   CopilotChat — header + messages + input
   ============================================================ */
function CopilotChat({ chat, threads, activeId, onMenu }) {
  const { messages, isLoading, sendMessage, resolveInterrupt, stopGeneration, regenerate } = chat;
  const scrollRef = useRef(null);
  const active = threads.find((t) => t.id === activeId);
  const lastAsstId = [...messages].reverse().find((m) => m.role === "assistant")?.id;

  useEffect(() => {
    const el = scrollRef.current; if (!el) return;
    requestAnimationFrame(() => el.scrollTo({ top: el.scrollHeight, behavior: "smooth" }));
  }, [messages, isLoading]);

  return (
    <div className="copilotKitWindow">
      <div className="copilotKitHeader">
        <button className="icon-btn menu-btn head-btn" onClick={onMenu}><Ic.menu /></button>
        <div className="ck-head-title">
          <span className="h-name">{active ? active.title : "Atlas CoAgent"}</span>
          <span className="h-sub">{isLoading ? "running LangGraph…" : (window.ATLAS_MODE === "live" ? "LangGraph CoAgent · live" : "LangGraph CoAgent · mock")}</span>
        </div>
        <span className="ck-agent-badge"><span className="dot" /> {isLoading ? "running" : "ready"}</span>
      </div>
      <div className="copilotKitMessages" ref={scrollRef}>
        {!active || messages.length === 0 ? (
          <CopilotEmpty greeting={greeting()} suggestions={SUGGESTIONS} onPick={sendMessage} />
        ) : (
          <div className="copilotKitMessagesInner">
            {messages.map((m) => (
              <CopilotMessage key={m.id} msg={m}
                onCopy={(t) => navigator.clipboard.writeText(t)}
                onRegenerate={regenerate}
                onResolveInterrupt={resolveInterrupt}
                isLast={m.id === lastAsstId}
                busy={isLoading} />
            ))}
          </div>
        )}
      </div>
      <CopilotInput onSend={sendMessage} busy={isLoading} onStop={stopGeneration} />
    </div>
  );
}

/* ============================================================
   Root
   ============================================================ */
const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "primaryColor": "#c0632f",
  "headerStyle": "light",
  "showActions": true,
  "dark": false
}/*EDITMODE-END*/;

function AppInner() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [threads, setThreads] = useThreadStore();
  const [activeId, setActiveId] = useState(null);
  const [railOpen, setRailOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => innerWidth < 1100);

  const chat = useCopilotChat({ threads, setThreads, activeId, setActiveId });

  // apply CopilotKit theme variables from tweaks
  useEffect(() => {
    const r = document.documentElement;
    r.style.setProperty("--copilot-kit-primary-color", t.primaryColor);
    r.setAttribute("data-header", t.headerStyle);
    r.setAttribute("data-dark", t.dark ? "true" : "false");
  }, [t.primaryColor, t.headerStyle, t.dark]);

  const newChat = () => { setActiveId(null); setRailOpen(false); };
  const selectThread = (id) => { setActiveId(id); setRailOpen(false); };
  const deleteThread = (id) => { setThreads((ts) => ts.filter((c) => c.id !== id)); if (id === activeId) setActiveId(null); };
  const trigger = (text) => { setRailOpen(false); chat.sendMessage(text); };

  return (
    <div className={"ck-app" + (railOpen ? " rail-open" : "") + (collapsed ? " collapsed" : "") + (t.showActions ? "" : " no-actions")}>
      <ThreadRail threads={threads} activeId={activeId} onSelect={selectThread} onNew={newChat}
        onDelete={deleteThread} dark={t.dark} onToggleDark={() => setTweak("dark", !t.dark)}
        actionsOpen={t.showActions} onToggleSkills={() => setTweak("showActions", !t.showActions)} skillCount={SKILL_ACTIONS.length}
        collapsed={collapsed} onToggleCollapse={() => setCollapsed((v) => !v)} />
      <div className="scrim" onClick={() => setRailOpen(false)} />
      <div className={"workspace" + (t.showActions ? "" : " no-actions")}>
        <CopilotChat chat={chat} threads={threads} activeId={activeId} onMenu={() => setRailOpen(true)} />
        {t.showActions && <ActionsPanel onTrigger={trigger} />}
      </div>

      {/* skills registered as CopilotKit actions */}
      {SKILL_ACTIONS.map((a) => <ActionRegistrar key={a.name} def={a} />)}
      {/* the HITL confirmation action (renderAndWaitForResponse) */}
      <ActionRegistrar def={{
        name: "confirm_warehouse_query", icon: "bars", tint: "#6766fc", hitl: true,
        description: "Human-in-the-loop gate. Renders an approval card and waits before the CoAgent runs a sensitive query.",
        parameters: ["sql"], example: "Pull Q2 MRR growth and break it down by plan",
      }} />

      <TweaksPanel>
        <TweakSection label="CopilotKit theme" />
        <TweakColor label="Primary color" value={t.primaryColor}
          options={["#c0632f", "#6766fc", "#0ea5e9", "#16a34a", "#111827"]}
          onChange={(v) => setTweak("primaryColor", v)} />
        <TweakRadio label="Header" value={t.headerStyle} options={["light", "solid"]}
          onChange={(v) => setTweak("headerStyle", v)} />
        <TweakToggle label="Dark mode" value={t.dark} onChange={(v) => setTweak("dark", v)} />
        <TweakSection label="Layout" />
        <TweakToggle label="Show actions panel" value={t.showActions} onChange={(v) => setTweak("showActions", v)} />
      </TweaksPanel>
    </div>
  );
}

function App() {
  return (
    <CopilotKitProvider agent="atlas_coagent">
      <AppInner />
    </CopilotKitProvider>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
