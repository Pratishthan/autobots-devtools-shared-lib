# Dynagent CopilotKit UI (reference app)

React chat UI that streams a Dynagent LangGraph agent via the AG-UI protocol.
Two processes: a Python FastAPI AG-UI server (shared-lib) and this Next.js proxy app.

## Prerequisites

- The shared venv is set up (`make setup` from `ws-autobots/`).
- The optional UI dependency is installed:
  `source ../.venv/bin/activate && pip install "ag-ui-langgraph>=0.0.42"`
  (or `pip install -e "autobots-devtools-shared-lib[copilotkit-ui]"`).
- `DYNAGENT_CONFIG_ROOT_DIR` is set for the target domain (see repo CLAUDE.md), e.g.
  `export DYNAGENT_CONFIG_ROOT_DIR=configs/bro`.

## Run

Terminal 1 — FastAPI AG-UI server (port 8000, path `/agent`):

```bash
cd autobots-devtools-shared-lib
source ../.venv/bin/activate
python -m autobots_devtools_shared_lib.dynagent.ui.copilotkit_server
```

Terminal 2 — Next.js app (port 3000):

```bash
cd autobots-devtools-shared-lib/ui
cp .env.example .env   # first run only
npm install            # first run only
npm run dev
```

Open http://localhost:3000

## Manual verification checklist

Send a message that triggers a tool call and a structured response, then confirm:

- [ ] Assistant text streams token-by-token (not all at once).
- [ ] Tool calls are visible in the chat as the agent runs them.
- [ ] Structured output renders as a final assistant message.
- [ ] Stopping the FastAPI server surfaces a clean error in chat (not a blank stream).
