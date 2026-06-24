/* ============================================================
   ck-runtime.jsx  (v2 — dual-mode: mock + live)

   MOCK MODE  (default)
   ───────────────────
   Fully in-browser scripted LangGraph simulation. No network
   calls. Perfect for design iteration in Claude / offline demos.

   LIVE MODE
   ─────────
   Connects to the real FastAPI backend via the AG-UI protocol
   exposed by ag_ui_langgraph:
     add_langgraph_fastapi_endpoint(app, agent, path)  # default "/agent"

   The UI POSTs an AG-UI Input { thread_id, run_id, messages, tools,
   context } to <backend><path> and consumes the SSE event stream
   (TEXT_MESSAGE_CONTENT, TOOL_CALL_START/ARGS/END, RUN_FINISHED,
   RUN_ERROR), mapping it onto the same agentState the mock produces.

   HOW TO SWITCH
   ─────────────
   URL param (takes priority):
     ?mode=mock   (default)
     ?mode=live

   Persistent (localStorage):
     localStorage.setItem("atlas.mode", "live")
     localStorage.setItem("atlas.mode", "mock")

   Backend URL (live mode only):
     ?backend=http://localhost:8000   (URL param)
     localStorage.setItem("atlas.backend", "http://localhost:8000")

   AG-UI path (live mode only — must match the FastAPI mount):
     ?path=/agent
     localStorage.setItem("atlas.path", "/agent")

   ck-app.jsx needs ZERO changes — the hook surface is identical
   in both modes (CopilotKitProvider, useCopilotChat, useCoAgent,
   useCoAgentStateRender, useCopilotAction).
   ============================================================ */
/* global React */
const { createContext, useContext, useState, useRef, useCallback, useEffect } = React;

/* ── Mode + backend detection ────────────────────────────── */
const _qs = new URLSearchParams(location.search);
const ATLAS_MODE = _qs.get("mode") || localStorage.getItem("atlas.mode") || "mock";
const DEFAULT_BACKEND = "http://localhost:8000";
const getBackend = () =>
  (_qs.get("backend") || localStorage.getItem("atlas.backend") || DEFAULT_BACKEND).replace(/\/+$/, "");

/* AG-UI mount path on the FastAPI app — must match add_langgraph_fastapi_endpoint(app, agent, path) */
const DEFAULT_AGENT_PATH = "/agent";
const getAgentPath = () => {
  let p = _qs.get("path") || localStorage.getItem("atlas.path") || DEFAULT_AGENT_PATH;
  if (!p.startsWith("/")) p = "/" + p;
  return p.replace(/\/+$/, "");
};

/* ── Utilities ───────────────────────────────────────────── */
const uid  = () => Math.random().toString(36).slice(2, 10);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ── Shared helpers (used by live mode) ─────────────────── */
function fmt(v) {
  if (v == null) return "";
  if (typeof v === "string") return v;
  if (typeof v === "object") {
    const keys = Object.keys(v);
    if (keys.length === 1 && typeof v[keys[0]] === "string") return v[keys[0]];
    try { return JSON.stringify(v, null, keys.length > 2 ? 2 : 0); } catch (e) { return String(v); }
  }
  return String(v);
}

/* Parse a POST'd SSE stream, invoking onEvent(obj) for each `data:` frame. */
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
    while ((sep = buf.search(/\r?\n\r?\n/)) !== -1) {
      const frame = buf.slice(0, sep);
      buf = buf.slice(sep + (buf[sep] === "\r" ? 4 : 2));
      const data = frame
        .split(/\r?\n/)
        .filter((l) => l.startsWith("data:"))
        .map((l) => l.slice(5).replace(/^ /, ""))
        .join("\n");
      if (!data || data === "[DONE]") continue;
      try { onEvent(JSON.parse(data)); } catch (_) {}
    }
  }
}

async function postApproval(approvalId, body) {
  const res = await fetch(`${getBackend()}/approvals/${approvalId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

/* ── LangGraph node definitions ──────────────────────────── */
const GRAPH_NODES = [
  { id: "route",    label: "route" },
  { id: "retrieve", label: "retrieve" },
  { id: "analyze",  label: "analyze" },
  { id: "respond",  label: "respond" },
];

/* ============================================================
   MOCK MODE — scripted LangGraph scenario engine
   ============================================================ */
const SCENARIOS = [
  {
    match: (t) => /pto|vacation|leave|policy|contractor/i.test(t),
    title: "PTO policy for contractors",
    async run(t, ctx) {
      await ctx.node("route");
      await sleep(420);
      await ctx.node("retrieve");
      const h = ctx.tool("search_docs", { query: "PTO policy contractors" });
      await sleep(900);
      ctx.end(h, "3 matches · People wiki › Policies › Time off (v6)");
      await sleep(350);
      await ctx.node("respond");
      await ctx.stream(
`Here's what the **People wiki › Time off (v6)** says for **contractors**:

- Contractors **accrue no PTO** — time off is unpaid and arranged directly with the engaging manager.
- Give **2+ weeks notice** for any absence longer than 3 days.
- Statutory public holidays follow the contractor's **country of record**, not the US calendar.
- Anything over **10 consecutive unpaid days** needs a note to People Ops for compliance.

Want me to draft the time-off request message to your manager?`);
    },
  },
  {
    match: (t) => /mrr|revenue|growth|plan|warehouse|sql/i.test(t),
    title: "Q2 MRR growth by plan",
    async run(t, ctx) {
      await ctx.node("route");
      await sleep(380);
      await ctx.node("retrieve");
      const h = ctx.tool("query_warehouse", { sql: "SELECT plan, mrr FROM finance.mrr_daily WHERE quarter = 'Q2'" });
      await sleep(750);
      const decision = await ctx.interrupt({
        action: "confirm_warehouse_query",
        tool: "query_warehouse",
        reason: "This query hits the finance schema (revenue-sensitive). Approve before the CoAgent runs it. You can edit the SQL first.",
        editable: true,
        input: { sql: "SELECT plan, mrr\nFROM finance.mrr_daily\nWHERE quarter = 'Q2'\nGROUP BY plan" },
      });
      if (decision.type === "reject") {
        ctx.end(h, "rejected by reviewer", "error");
        await ctx.node("respond");
        await ctx.stream("I've held off — the warehouse query wasn't approved, so I didn't pull any revenue figures. Let me know if you'd like to adjust the query or scope.");
        return;
      }
      ctx.end(h, "342 rows · finance.mrr_daily");
      await sleep(300);
      await ctx.node("analyze");
      const h2 = ctx.tool("run_python", { code: "df.groupby('plan').mrr.agg(['sum','pct_change'])" });
      await sleep(820);
      ctx.end(h2, "computed MRR + QoQ growth per plan");
      await sleep(250);
      await ctx.node("respond");
      await ctx.stream(
`**Q2 MRR growth by plan** (finance.mrr_daily, approved query):

| Plan | Q2 MRR | QoQ growth |
|------|-------:|----------:|
| Enterprise | $1.82M | **+14.2%** |
| Business | $940K | +8.6% |
| Team | $410K | +5.1% |
| Starter | $96K | −2.3% |

Enterprise drove **most of the net new MRR** this quarter; Starter contracted slightly as accounts upgraded. Want a breakdown by region or a forecast into Q3?`);
    },
  },
  {
    match: (t) => /slack|support|#support|theme|ticket|issue/i.test(t),
    title: "Support themes — last week",
    async run(t, ctx) {
      await ctx.node("route");
      await sleep(360);
      await ctx.node("retrieve");
      const h = ctx.tool("slack_search", { channels: "#support, #support-escalations", window: "7d" });
      await sleep(980);
      ctx.end(h, "212 threads scanned");
      await sleep(260);
      await ctx.node("analyze");
      const h2 = ctx.tool("run_python", { code: "cluster(threads, k=4)" });
      await sleep(700);
      ctx.end(h2, "4 clusters");
      await sleep(220);
      await ctx.node("respond");
      await ctx.stream(
`Top **#support** themes over the last 7 days (212 threads):

1. **SSO / login loops** — 38 threads, mostly Okta SAML clock skew. Trending **up**.
2. **Billing proration confusion** — 27 threads after the new plan rollout.
3. **Export timeouts** — 19 threads on large CSV exports (>500k rows).
4. **Mobile push not arriving** — 11 threads, iOS 18 only.

The SSO cluster is the one I'd escalate — it doubled week-over-week. Want me to draft an incident summary for #eng?`);
    },
  },
  {
    match: (t) => /forecast|project|signup|next month|trend/i.test(t),
    title: "Forecast next month's signups",
    async run(t, ctx) {
      await ctx.node("route");
      await sleep(360);
      await ctx.node("retrieve");
      const h = ctx.tool("query_warehouse", { sql: "SELECT day, signups FROM growth.signups_daily ORDER BY day DESC LIMIT 180" });
      await sleep(760);
      ctx.end(h, "180 days of signups");
      await sleep(240);
      await ctx.node("analyze");
      const h2 = ctx.tool("run_python", { code: "Prophet().fit(df).predict(30)" });
      await sleep(900);
      ctx.end(h2, "30-day projection · MAPE 6.4%");
      await sleep(240);
      await ctx.node("respond");
      await ctx.stream(
`Based on the last 180 days (Prophet, MAPE ≈ 6.4%):

- **Next-month signups:** ~**12,400** (80% interval 11,200–13,700)
- That's **+9%** vs. the trailing 30 days.
- Weekly seasonality is strong — expect ~**2× weekday volume** vs. weekends.

The growth is steady rather than spiky, so no single campaign is driving it. Want this as a chart or pushed to the growth dashboard?`);
    },
  },
  {
    match: (t) => /onboard|new hire|checklist|eng hire/i.test(t),
    title: "Onboarding checklist",
    async run(t, ctx) {
      await ctx.node("route");
      await sleep(380);
      await ctx.node("retrieve");
      const h = ctx.tool("search_docs", { query: "engineering onboarding checklist" });
      await sleep(860);
      ctx.end(h, "found 'Eng Onboarding v4'");
      await sleep(280);
      await ctx.node("respond");
      await ctx.stream(
`Here's the current **engineering onboarding** checklist (People wiki, v4):

1. **Day 0** — laptop + SSO provisioned, added to \`#eng\` and team channel
2. **Day 1** — repo access, dev environment, read the architecture overview
3. **Week 1** — ship a starter PR, 1:1 with manager, security training
4. **Week 2** — on-call shadowing, meet your onboarding buddy

Want me to generate a personalized version for a specific role or level?`);
    },
  },
  {
    match: (t) => /research|competitor|web|pricing|look up/i.test(t),
    title: "Web research",
    async run(t, ctx) {
      await ctx.node("route");
      await sleep(360);
      await ctx.node("retrieve");
      const h = ctx.tool("web_search", { query: "competitor team plan pricing" });
      await sleep(1000);
      ctx.end(h, "6 sources");
      await sleep(260);
      await ctx.node("respond");
      await ctx.stream(
`Quick scan of public pricing for **team plans** (3 closest competitors):

- **Linear-style flat seat:** ~$8–10/user/mo, no minimum.
- **Tiered with annual lock-in:** ~$15/user/mo, 5-seat floor.
- **Usage + seat hybrid:** $6 base + metered automation runs.

The market is drifting toward **per-seat with a usage rider**. Want a side-by-side table with sources cited?`);
    },
  },
];

const DEFAULT_SCENARIO = {
  title: "Atlas",
  async run(t, ctx) {
    await ctx.node("route");
    await sleep(380);
    await ctx.node("retrieve");
    const h = ctx.tool("search_docs", { query: t.slice(0, 60) });
    await sleep(820);
    ctx.end(h, "scanned internal knowledge base");
    await sleep(260);
    await ctx.node("respond");
    await ctx.stream(
`I looked through the internal knowledge base for **"${t.slice(0, 80)}"**.

I can search docs & policies, query the analytics warehouse, scan Slack support, run Python for analysis, or research the public web. Pick one of the registered actions on the right, or tell me a bit more about what you're after.`);
  },
};

function pickScenario(text) {
  return SCENARIOS.find((s) => s.match(text)) || DEFAULT_SCENARIO;
}

/* ============================================================
   CopilotKit context
   ============================================================ */
const CopilotKitContext = createContext(null);

function CopilotKitProvider({ agent = "atlas_coagent", children }) {
  const actionsRef = useRef(new Map());
  const [actionList, setActionList] = useState([]);
  const [backendUrl, setBackendUrl] = useState(getBackend);
  const [conn, setConn] = useState(ATLAS_MODE === "mock" ? "mock" : "checking");

  const registerAction = useCallback((def) => {
    actionsRef.current.set(def.name, def);
    setActionList([...actionsRef.current.values()]);
    return () => {
      actionsRef.current.delete(def.name);
      setActionList([...actionsRef.current.values()]);
    };
  }, []);

  /* probe backend health on mount + backendUrl change (live only) */
  useEffect(() => {
    if (ATLAS_MODE !== "live") return;
    let alive = true;
    setConn("checking");
    (async () => {
      try {
        await fetch(backendUrl + "/", { method: "GET", mode: "no-cors" });
        if (alive) setConn("online");
      } catch (e) {
        if (alive) setConn("offline");
      }
    })();
    return () => { alive = false; };
  }, [backendUrl]);

  /* persist backend URL to localStorage */
  useEffect(() => {
    localStorage.setItem("atlas.backend", backendUrl);
  }, [backendUrl]);

  const value = {
    agent,
    actionsRef,
    actions: actionList,
    registerAction,
    /* mode info — readable by any component */
    mode: ATLAS_MODE,       // "mock" | "live"
    conn,                   // "mock" | "checking" | "online" | "offline"
    setConn,
    backendUrl,
    setBackendUrl,
    agentPath: getAgentPath(),   // AG-UI endpoint path (default "/agent")
  };
  return <CopilotKitContext.Provider value={value}>{children}</CopilotKitContext.Provider>;
}

/* ============================================================
   Thread store
   ============================================================ */
const THREAD_KEY = "atlas.copilotkit.threads.v1";
const USER = { name: "Maya Okonkwo", role: "Operations · member", initials: "MO" };

function seedThreads() {
  const d = Date.now();
  return [
    { id: uid(), createdAt: d - 36e5, title: "Onboarding checklist for new hires", messages: [
      { id: uid(), role: "user", content: "What's the onboarding checklist for a new eng hire?" },
      { id: uid(), role: "assistant", status: "complete", content:
`Here's the current **engineering onboarding** checklist (People wiki, v4):

1. **Day 0** — laptop + SSO provisioned, added to \`#eng\` and team channel
2. **Day 1** — repo access, dev environment, read the architecture overview
3. **Week 1** — ship a starter PR, 1:1 with manager, security training
4. **Week 2** — on-call shadowing, meet your onboarding buddy`,
        agentState: { name: "atlas_coagent", active: false, nodes: [
          { id: "route",    label: "route",    status: "done" },
          { id: "retrieve", label: "retrieve", status: "done" },
          { id: "respond",  label: "respond",  status: "done" },
        ], tools: [{ id: uid(), name: "search_docs", input: '{"query":"engineering onboarding checklist"}', output: "found 'Eng Onboarding v4'", status: "done" }] },
      },
    ] },
    { id: uid(), createdAt: d - 50e5,  title: "Q2 MRR growth by plan",               messages: [] },
    { id: uid(), createdAt: d - 26e6,  title: "Refund policy edge cases",             messages: [] },
    { id: uid(), createdAt: d - 28e6,  title: "Draft: infra migration status update", messages: [] },
    { id: uid(), createdAt: d - 30e6,  title: "Top support themes — last week",       messages: [] },
  ];
}

function useThreadStore() {
  const [threads, setThreads] = useState(() => {
    try {
      const s = JSON.parse(localStorage.getItem(THREAD_KEY));
      if (s && s.length) return s;
    } catch (e) {}
    return seedThreads();
  });
  useEffect(() => {
    try { localStorage.setItem(THREAD_KEY, JSON.stringify(threads.slice(0, 40))); } catch (e) {}
  }, [threads]);
  return [threads, setThreads];
}

/* ============================================================
   useCopilotChat — owns one active thread's run loop
   Dispatches to runAgentMock or runAgentLive based on ATLAS_MODE
   ============================================================ */
function useCopilotChat({ threads, setThreads, activeId, setActiveId }) {
  const ck = useContext(CopilotKitContext);
  const [isLoading, setIsLoading] = useState(false);
  const cancelRef = useRef(false);   /* mock stop flag */
  const abortRef  = useRef(null);    /* live AbortController */

  const active   = threads.find((t) => t.id === activeId) || null;
  const messages = active ? active.messages : [];

  const patch = useCallback((threadId, msgId, fn) => {
    setThreads((ts) => ts.map((t) =>
      t.id !== threadId ? t : {
        ...t,
        messages: t.messages.map((m) =>
          m.id !== msgId ? m : (typeof fn === "function" ? fn(m) : { ...m, ...fn })
        ),
      }
    ));
  }, [setThreads]);

  /* ── MOCK run ─────────────────────────────────────────── */
  const runAgentMock = useCallback(async (threadId, text, msgId) => {
    cancelRef.current = false;
    setIsLoading(true);
    const scenario = pickScenario(text);
    const agentName = ck ? ck.agent : "atlas_coagent";

    const state = { name: agentName, active: true, nodes: [], tools: [] };
    const toolIndex = {};
    let answer = "";

    const flush = (extra = {}) =>
      patch(threadId, msgId, (m) => ({
        ...m,
        agentState: { ...state, nodes: [...state.nodes], tools: [...state.tools] },
        ...extra,
      }));

    const ctx = {
      async node(id) {
        const def = GRAPH_NODES.find((n) => n.id === id);
        state.nodes = state.nodes.map((n) =>
          n.status === "active" ? { ...n, status: "done" } : n
        );
        if (!state.nodes.find((n) => n.id === id))
          state.nodes.push({ id, label: def ? def.label : id, status: "active" });
        flush({ status: "generating" });
      },
      tool(name, input) {
        const id = uid();
        toolIndex[id] = state.tools.length;
        state.tools.push({ id, name, input: fmt(input), output: "", status: "running" });
        flush({ status: "generating" });
        return id;
      },
      end(id, output, status = "done") {
        const i = toolIndex[id];
        if (i != null) state.tools[i] = { ...state.tools[i], output: fmt(output), status };
        flush();
      },
      async interrupt(payload) {
        return new Promise((resolve) => {
          const intr = {
            id: uid(),
            action:   payload.action,
            tool:     payload.tool,
            reason:   payload.reason,
            editable: !!payload.editable,
            input:    payload.input,
            resolve:  (decision) => {
              patch(threadId, msgId, (m) => ({ ...m, interrupt: null }));
              resolve(decision);
            },
          };
          patch(threadId, msgId, (m) => ({
            ...m,
            status: "awaiting_input",
            interrupt: intr,
            agentState: { ...state, active: false, nodes: [...state.nodes], tools: [...state.tools] },
          }));
        });
      },
      async stream(md) {
        const tokens = md.split(/(\s+)/);
        for (const tk of tokens) {
          if (cancelRef.current) break;
          answer += tk;
          patch(threadId, msgId, (m) => ({ ...m, status: "streaming", content: answer }));
          await sleep(7 + Math.random() * 15);
        }
      },
    };

    try {
      await scenario.run(text, ctx);
      state.nodes = state.nodes.map((n) =>
        n.status === "active" ? { ...n, status: "done" } : n
      );
      state.active = false;
      patch(threadId, msgId, (m) => ({
        ...m,
        status: "complete",
        content: answer || m.content,
        agentState: { ...state, nodes: [...state.nodes], tools: [...state.tools] },
      }));
    } catch (e) {
      patch(threadId, msgId, (m) => ({
        ...m, status: "error", errorMsg: e.message || "CoAgent run failed",
      }));
    } finally {
      setIsLoading(false);
    }
  }, [ck, patch]);

  /* ── LIVE run — speaks AG-UI protocol (ag_ui_langgraph) ── */
  const runAgentLive = useCallback(async (threadId, text, msgId) => {
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setIsLoading(true);
    if (ck) ck.setConn("checking");

    let answer   = "";
    let tools    = [];
    const toolAt = {};   /* tool_call_id → index in tools[] */
    const toolArgBuf = {}; /* tool_call_id → accumulating JSON string */
    let nodes    = [{ id: "route", label: "route", status: "active" }];

    const agentName = ck ? ck.agent : "atlas_coagent";
    const agentPath = ck ? (ck.agentPath || "/agent") : "/agent";

    const flush = (extra = {}) =>
      patch(threadId, msgId, (m) => ({
        ...m,
        agentState: { name: agentName, active: true, nodes: [...nodes], tools: [...tools] },
        ...extra,
      }));

    const advanceNode = (nextId) => {
      if (nodes.find((n) => n.id === nextId)) return;
      nodes = nodes.map((n) => n.status === "active" ? { ...n, status: "done" } : n);
      const def = GRAPH_NODES.find((n) => n.id === nextId);
      nodes.push({ id: nextId, label: def ? def.label : nextId, status: "active" });
    };

    /* ── AG-UI event → internal state mapping ─────────────── */
    const onEvent = (evt) => {
      switch (evt && evt.type) {

        /* Streaming assistant text ─────────────────────────── */
        case "TEXT_MESSAGE_CONTENT": {
          advanceNode("respond");
          answer += evt.delta || "";
          flush({ status: "streaming", content: answer });
          break;
        }

        /* Tool call lifecycle ──────────────────────────────── */
        case "TOOL_CALL_START": {
          const name = evt.tool_call_name || "";
          if (!tools.length) advanceNode("retrieve");
          else advanceNode("analyze");
          toolAt[evt.tool_call_id] = tools.length;
          toolArgBuf[evt.tool_call_id] = "";
          tools = [...tools, { id: evt.tool_call_id, name, input: "", output: "", status: "running" }];
          flush({ status: answer ? "streaming" : "generating" });
          break;
        }
        case "TOOL_CALL_ARGS": {
          /* Args arrive as streaming JSON chunks — accumulate then pretty-print */
          toolArgBuf[evt.tool_call_id] = (toolArgBuf[evt.tool_call_id] || "") + (evt.delta || "");
          const i = toolAt[evt.tool_call_id];
          if (i != null) {
            let prettyInput = toolArgBuf[evt.tool_call_id];
            try { prettyInput = JSON.stringify(JSON.parse(prettyInput), null, 2); } catch (_) {}
            tools = tools.map((t, j) => j === i ? { ...t, input: prettyInput } : t);
            flush({ status: answer ? "streaming" : "generating" });
          }
          break;
        }
        case "TOOL_CALL_END": {
          const i = toolAt[evt.tool_call_id];
          if (i != null) {
            tools = tools.map((t, j) => j === i ? { ...t, status: "done" } : t);
          }
          flush({ status: answer ? "streaming" : "generating" });
          break;
        }

        /* Run lifecycle ────────────────────────────────────── */
        case "RUN_STARTED": {
          flush({ status: "generating" });
          break;
        }
        case "RUN_FINISHED": {
          nodes = nodes.map((n) => ({ ...n, status: "done" }));
          patch(threadId, msgId, (m) => ({
            ...m,
            status: "complete",
            content: answer || m.content,
            interrupt: null,
            agentState: { name: agentName, active: false, nodes: [...nodes], tools: [...tools] },
          }));
          break;
        }
        case "RUN_ERROR": {
          patch(threadId, msgId, (m) => ({
            ...m, status: "error", errorMsg: evt.message || "Agent error",
          }));
          break;
        }

        default: break;
      }
    };

    /* AG-UI RunAgentInput shape — camelCase keys; state/forwardedProps required.
       threadId carries conversation continuity. */
    const agUiPayload = {
      threadId:       threadId,
      runId:          uid(),
      state:          {},
      messages:       [{ id: uid(), role: "user", content: text }],
      tools:          [],
      context:        [],
      forwardedProps: {},
    };

    try {
      await streamChat(
        `${getBackend()}${agentPath}`,
        agUiPayload,
        { signal: ctrl.signal, onEvent }
      );
      if (ck) ck.setConn("online");
      /* Finalize if server closed without explicit RUN_FINISHED */
      patch(threadId, msgId, (m) =>
        ["complete", "error", "awaiting_input"].includes(m.status) ? m : {
          ...m,
          status: "complete",
          content: answer || m.content,
          interrupt: null,
          agentState: {
            name: agentName,
            active: false,
            nodes: nodes.map((n) => ({ ...n, status: "done" })),
            tools: [...tools],
          },
        }
      );
    } catch (e) {
      if (ctrl.signal.aborted) {
        patch(threadId, msgId, (m) => ({
          ...m, status: "complete", content: answer || "_(stopped)_", interrupt: null,
        }));
      } else {
        if (ck) ck.setConn("offline");
        patch(threadId, msgId, (m) => ({
          ...m, status: "error", errorMsg: e.message,
        }));
      }
    } finally {
      if (abortRef.current === ctrl) abortRef.current = null;
      setIsLoading(false);
    }
  }, [ck, patch]);

  /* ── Dispatch to correct runner ──────────────────────── */
  const runAgent = ATLAS_MODE === "live" ? runAgentLive : runAgentMock;

  /* ── Public API ──────────────────────────────────────── */
  const sendMessage = useCallback((text) => {
    const userMsg = { id: uid(), role: "user",      content: text };
    const asstMsg = { id: uid(), role: "assistant", status: "thinking", content: "", agentState: null, interrupt: null };
    let threadId = activeId;

    if (!active) {
      threadId = uid();
      setThreads((ts) => [
        { id: threadId, createdAt: Date.now(), title: text.slice(0, 46), messages: [userMsg, asstMsg] },
        ...ts,
      ]);
      setActiveId(threadId);
    } else {
      setThreads((ts) => ts.map((t) =>
        t.id !== threadId ? t : { ...t, messages: [...t.messages, userMsg, asstMsg] }
      ));
    }
    runAgent(threadId, text, asstMsg.id);
  }, [active, activeId, runAgent, setThreads, setActiveId]);

  /* Resolve a pending HITL interrupt (calls interrupt.resolve) */
  const resolveInterrupt = useCallback((msg, decision) => {
    if (msg.interrupt && msg.interrupt.resolve) msg.interrupt.resolve(decision);
  }, []);

  const stopGeneration = useCallback(() => {
    cancelRef.current = true;          /* mock */
    abortRef.current && abortRef.current.abort(); /* live */
  }, []);

  const regenerate = useCallback((msg) => {
    if (!active || isLoading) return;
    const idx = active.messages.findIndex((m) => m.id === msg.id);
    const prevUser = active.messages.slice(0, idx).reverse().find((m) => m.role === "user");
    if (!prevUser) return;
    patch(active.id, msg.id, { status: "thinking", content: "", agentState: null, interrupt: null });
    runAgent(active.id, prevUser.content, msg.id);
  }, [active, isLoading, patch, runAgent]);

  return { messages, isLoading, sendMessage, resolveInterrupt, stopGeneration, regenerate, USER };
}

/* ── Export everything ck-app.jsx + ck-components.jsx needs ─ */
Object.assign(window, {
  CopilotKitProvider,
  CopilotKitContext,
  useCopilotChat,
  useThreadStore,
  GRAPH_NODES,
  USER,
  uid,
  ATLAS_MODE,
});
