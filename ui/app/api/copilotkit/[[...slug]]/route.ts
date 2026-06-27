import {
  CopilotRuntime,
  createCopilotEndpoint,
  InMemoryAgentRunner,
} from "@copilotkit/runtime/v2";
import { LangGraphHttpAgent } from "@copilotkit/runtime/langgraph";
import { handle } from "hono/vercel";

// The dynagent graph runs under uvicorn + ag-ui-langgraph and speaks AG-UI
// directly, so we connect with LangGraphHttpAgent (URL only — no graphId).
// The server mounts the agent at /agent; AGENT_URL is the server origin.
const defaultAgent = new LangGraphHttpAgent({
  url: `${process.env.AGENT_URL || "http://localhost:8000"}/agent`,
});

const runtime = new CopilotRuntime({
  agents: { default: defaultAgent },
  runner: new InMemoryAgentRunner(),
});

// Default "multi-route" mode: serves /info, /agent/:id/run and /agent/:id/connect
// as discrete routes. The client opts into this via `useSingleEndpoint={false}`
// in the root layout; the /connect route is what powers thread-resume state
// replay (STATE_SNAPSHOT), matching the langgraph-fastapi reference example.
const app = createCopilotEndpoint({
  runtime,
  basePath: "/api/copilotkit",
});

export const GET = handle(app);
export const POST = handle(app);
export const PATCH = handle(app);
export const DELETE = handle(app);
