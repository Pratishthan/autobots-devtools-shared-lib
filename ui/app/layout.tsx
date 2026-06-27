import type { ReactNode } from "react";
import "@copilotkit/react-core/v2/styles.css";
import { CopilotKit } from "@copilotkit/react-core/v2";

export const metadata = {
  title: "Dynagent CopilotKit UI",
  description: "React chat UI for Dynagent agents over AG-UI.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      {/*
        suppressHydrationWarning: browser extensions (e.g. Grammarly) inject
        attributes onto <body> before React hydrates, which would otherwise
        surface as a hydration mismatch on first load.
      */}
      <body suppressHydrationWarning>
        {/*
          useSingleEndpoint={false} -> REST/multi-route transport (GET /info,
          POST /agent/:id/run, /agent/:id/connect), matching the multi-route
          endpoint in route.ts and the langgraph-fastapi reference. Omitting it
          defaults to true (single POST to the base URL), which 404s against a
          multi-route endpoint.
        */}
        <CopilotKit runtimeUrl="/api/copilotkit" useSingleEndpoint={false}>
          {children}
        </CopilotKit>
      </body>
    </html>
  );
}
