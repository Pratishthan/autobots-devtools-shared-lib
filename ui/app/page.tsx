"use client";

import { CopilotKit } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";

export default function Page() {
  return (
    <CopilotKit runtimeUrl="/api/copilotkit" agent="coordinator">
      <div style={{ height: "100vh" }}>
        <CopilotChat
          labels={{
            title: "Dynagent",
            initial: "Hello, how can I help you today?",
          }}
        />
      </div>
    </CopilotKit>
  );
}
