# Architecture Diagrams & Design Documentation

This folder contains comprehensive architecture diagrams and design documentation for the bro-chat codebase.

## Quick Navigation

### 1. [High-Level Architecture](architecture-high-level.md)
**Best for:** Understanding the overall system at a glance

Shows:
- UI layer (Chainlit)
- BRO use case layer
- Generic agent framework (dynagent)
- Observability and utilities
- External services (Gemini, Langfuse, File System)

**Use when:** Onboarding, presenting to stakeholders, understanding major components

---

### 2. [Module Dependencies](module-dependencies.md)
**Best for:** Understanding how modules relate to each other

Shows:
- Complete module graph
- BRO use case modules (tools, services, models)
- Dynamic agent framework modules
- External integrations
- Dependency relationships between every major component

**Use when:** Implementing new features, refactoring, adding new modules, debugging import issues

---

### 3. [Agent Invocation Data Flow](data-flow-invocation.md)
**Best for:** Understanding what happens when a user sends a message

Shows:
- Sequence from user input → Chainlit → agent → LLM → tools → response
- Middleware interception and dynamic injection
- Tool resolution and execution
- State management during invocation

**Use when:** Debugging agent behavior, understanding tool execution, implementing new tools or agents

---

### 4. [Configuration Initialization Order](initialization-order.md)
**Best for:** Understanding startup sequence and configuration loading

Shows:
- Critical startup order (why order matters)
- Environment variable loading
- Tool registration
- Agent creation and configuration
- AgentMeta singleton initialization
- Why each step must happen in the correct order

**Use when:** Setting up the project, debugging startup issues, configuring new agents, understanding why a tool isn't available

---

### 5. [Document Lifecycle](document-lifecycle.md)
**Best for:** Understanding how BRO vision documents are managed

Shows:
- Document storage structure and file formats
- BRO tools flow (create, update, export)
- Session isolation with workspace directories
- Entity management
- Integration with coordinator and specialist agents
- Markdown export process

**Use when:** Working with document store, implementing new document features, understanding tool requirements, debugging document persistence

---

## Key Concepts

### Architecture Principles

1. **Separation of Concerns**
   - `dynagent/`: Generic, reusable agent orchestration framework
   - `bro_chat/`: Use-case specific vision document management
   - Zero circular imports between layers

2. **Dynamic Injection**
   - Same agent code runs for all agents (coordinator, preface_agent, etc.)
   - Prompts and tools injected at runtime per agent
   - New agents added via `agents.yaml` (no code changes)

3. **Tool Registry Pattern**
   - Centralized tool pool in tool_registry.py
   - Default tools + registered use-case tools
   - Tools filtered per agent from complete pool
   - Tools can be registered before agent creation

4. **Session Isolation**
   - Each user session gets `workspace/{session_id}/` directory
   - Document context persists in `_doc_context.json`
   - Prevents cross-session data leakage
   - Enables parallel sessions without interference

5. **Configuration Singletons**
   - `AgentMeta`: Loads agents.yaml once at startup
   - Cached in memory for performance
   - Reset method for test isolation
   - Provides type-safe accessors

---

## File Locations Referenced in Diagrams

### Configuration Files
- `configs/vision-agent/agents.yaml` - Agent definitions
- `configs/vision-agent/sections.yaml` - Document sections
- `configs/vision-agent/output-schemas/` - Structured output schemas

### Source Code
- `src/bro_chat/` - BRO use case implementation
- `src/dynagent/` - Generic agent framework
- `src/bro_chat/agents/bro_tools.py` - Vision document tools
- `src/dynagent/agents/base_agent.py` - Agent factory
- `src/dynagent/agents/middleware.py` - Dynamic injection
- `src/dynagent/tools/tool_registry.py` - Tool pool

### Data Storage
- `vision-docs/` - Document storage (component/version structure)
- `workspace/` - Session-specific data (session_id directories)

---

## Reading Guide by Role

### For Frontend/UI Developers
1. Start: Architecture (high-level)
2. Then: Data Flow (understand what happens when user interacts)
3. Deep-dive: Module Dependencies (understand UI integration points)

### For Agent/Backend Developers
1. Start: Initialization Order (critical for setup)
2. Then: Module Dependencies (understand component relationships)
3. Deep-dive: Data Flow (understand agent execution)
4. Reference: Document Lifecycle (understand tool requirements)

### For Product/Documentation
1. Start: Architecture (high-level overview)
2. Reference: Document Lifecycle (understand how docs are managed)

### For New Contributors
1. Read in order: Architecture → Dependencies → Data Flow → Initialization
2. Reference as needed: Document Lifecycle

---

## Related Files

- **CLAUDE.md** - Development commands and coding conventions
- **pyproject.toml** - Dependencies and project configuration
- **README.md** - Project overview and getting started
- **docs/living-docs/specs/bro-agent-spec.md** - Full BRO agent specification

---

## Updating These Diagrams

When making significant architectural changes:

1. **New module?** Update module-dependencies.md
2. **New agent or tool?** Update initialization-order.md and module-dependencies.md
3. **Changed data flow?** Update data-flow-invocation.md
4. **New document features?** Update document-lifecycle.md
5. **Major restructuring?** Update architecture-high-level.md

All diagrams use Mermaid syntax and can be rendered in:
- GitHub markdown preview
- Markdown viewers that support Mermaid
- Online Mermaid editor: https://mermaid.live/
