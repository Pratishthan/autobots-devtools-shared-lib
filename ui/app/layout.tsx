import type { ReactNode } from "react";

export const metadata = {
  title: "Dynagent CopilotKit UI",
  description: "React chat UI for Dynagent agents over AG-UI.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
