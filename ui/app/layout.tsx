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
        <CopilotKit runtimeUrl="/api/copilotkit">{children}</CopilotKit>
      </body>
    </html>
  );
}
