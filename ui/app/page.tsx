"use client";

import { CopilotChat } from "@copilotkit/react-core/v2";

export default function Page() {
  return (
    <div style={{ height: "100vh" }}>
      {/*
        agentId must match a key in the runtime's `agents` map (route.ts
        registers it as "default"). Without it the client routes to an empty
        agent segment (/api/copilotkit/agent//run → /agent/run), yielding
        the HTTP 404 {"error":"Not found"} agent_run_failed error.
      */}
      <CopilotChat agentId="default" />
    </div>
  );
}
