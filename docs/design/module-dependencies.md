# Detailed Module Dependencies Diagram

```mermaid
graph TB
    subgraph "Entry Point"
        UI["usecase_ui.py"]
    end

    subgraph "BRO Use Case bro_chat/"
        direction LR
        BroTools["agents/bro_tools.py<br/>10 tools for doc mgmt"]
        Store["services/document_store.py<br/>JSON persistence"]
        Export["services/markdown_exporter.py<br/>Doc→Markdown"]
        DocModel["models/document.py<br/>DocumentMeta, SectionMeta"]
        StatusEnum["models/status.py<br/>Section lifecycle"]
        Formatting["utils/formatting.py<br/>Output formatters"]
        BroSettings["config/settings.py<br/>App configuration"]
    end

    subgraph "Dynamic Agent Framework dynagent/"
        direction LR
        BaseAgent["agents/base_agent.py<br/>Agent factory"]
        Middleware["agents/middleware.py<br/>Dynamic injection"]
        AgentMeta["agents/agent_meta.py<br/>Config singleton"]
        ConfigUtils["agents/agent_config_utils.py<br/>YAML parsing"]

        ToolRegistry["tools/tool_registry.py<br/>Tool pool"]
        StateTools["tools/state_tools.py<br/>handoff, file I/O"]
        FormatTools["tools/format_tools.py<br/>Structured output"]
        StructConverter["tools/structured_converter.py<br/>LLM extraction"]

        LLMFactory["llm/llm.py<br/>Gemini factory"]
        State["models/state.py<br/>Agent state schema"]
        Batch["agents/batch.py<br/>Parallel invocation"]

        Tracing["observability/tracing.py<br/>Langfuse integration"]
        TracingConfig["config/settings.py<br/>Langfuse config"]

        UIUtils["ui/ui_utils.py<br/>Streaming, markdown"]
    end

    subgraph "External Integrations"
        Gemini["🔷 Google Gemini<br/>LLM API"]
        Langfuse["🔷 Langfuse<br/>Observability"]
        FileIO["💾 File System<br/>workspace/, vision-docs/"]
    end

    UI -->|1. registers| BroTools
    UI -->|2. creates| BaseAgent
    UI -->|3. initializes| Tracing
    UI -->|4. streams via| UIUtils

    BroTools -->|depends on| Store
    BroTools -->|depends on| StateTools
    BroTools -->|depends on| Export

    Store -->|uses| DocModel
    Export -->|uses| DocModel
    DocModel -->|uses| StatusEnum

    Formatting -->|re-exports from| UIUtils

    BaseAgent -->|injects tools via| Middleware
    BaseAgent -->|uses tool set from| ToolRegistry
    BaseAgent -->|calls| LLMFactory
    BaseAgent -->|manages| State
    BaseAgent -->|applies| Batch

    Middleware -->|reads config from| AgentMeta
    AgentMeta -->|parses| ConfigUtils

    ToolRegistry -->|contains| StateTools
    ToolRegistry -->|contains| FormatTools
    ToolRegistry -->|contains| BroTools

    FormatTools -->|converts via| StructConverter
    StructConverter -->|calls LLM for| LLMFactory

    LLMFactory -->|requests| Gemini
    Tracing -->|sends events to| Langfuse

    BroSettings -->|configures| UI
    TracingConfig -->|configures| Tracing

    StateTools -->|manages| FileIO
    Store -->|persists to| FileIO
    Batch -->|isolated sessions in| FileIO
```

## Module Organization

### BRO Use Case Layer (`src/bro_chat/`)
- **agents/bro_tools.py** - 10 tools for document management and entity creation
- **services/document_store.py** - File-based JSON persistence
- **services/markdown_exporter.py** - Converts vision documents to markdown
- **models/document.py** - DocumentMeta, SectionMeta, DynamicItems
- **models/status.py** - Section lifecycle states
- **utils/formatting.py** - Output formatting for different sections
- **config/settings.py** - Application configuration (API keys, OAuth, ports)

### Generic Agent Framework (`src/dynagent/`)
- **agents/base_agent.py** - Creates compiled LangGraph agent
- **agents/middleware.py** - Dynamic prompt/tool injection per agent
- **agents/agent_meta.py** - Configuration singleton (YAML-based)
- **agents/agent_config_utils.py** - YAML parser for agent definitions
- **tools/tool_registry.py** - Centralized tool pool (default + use-case tools)
- **tools/state_tools.py** - handoff, file I/O, document management
- **tools/format_tools.py** - Structured output conversion
- **tools/structured_converter.py** - LLM-based data extraction
- **llm/llm.py** - Gemini factory singleton
- **models/state.py** - Agent state schema (agent_name, session_id routing)
- **agents/batch.py** - Batch processing interface for parallel invocation
- **observability/tracing.py** - Langfuse integration
- **config/settings.py** - Langfuse configuration
- **ui/ui_utils.py** - Streaming utilities and markdown rendering

### Key Dependency Patterns
1. **No circular imports** - dynagent never imports bro_chat
2. **Singleton configs** - AgentMeta loaded once at startup
3. **Tool registration** - BRO tools registered before agent creation
4. **Lazy initialization** - AgentMeta instance created on first agent use
5. **Session isolation** - Workspace directories per session_id
