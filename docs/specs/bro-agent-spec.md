# bro - Business Requirement Oracle

## Component Vision Document Agent Specification

**Version**: 1.0
**Status**: Draft
**Last Updated**: 2026-01-31

---

## 1. Overview

**bro** (Business Requirement Oracle) is a chat agent that helps Product Owners create, edit, and manage Component Vision Documents through an interactive, section-based conversation flow.

### 1.1 Core Capabilities

- Create new vision documents from scratch
- Resume in-progress documents
- Edit completed documents
- Navigate between sections freely
- Export to human-readable Markdown

### 1.2 Technology Stack

| Component       | Technology                         |
| --------------- | ---------------------------------- |
| Chat Framework  | Chainlit                           |
| Agent Framework | LangChain / LangGraph              |
| LLM             | Google Gemini 2.0 Flash            |
| Storage         | File Server MCP                    |
| Authentication  | GitHub Login (via Chainlit)        |
| Pattern         | Follows `dynagent.py` architecture |

---

## 2. Interaction Model

### 2.1 Navigation Style

**Section-Based Navigation**: PO can jump to any section they want to work on. The agent tracks what's complete vs. incomplete and suggests the next logical section after completing one.

### 2.2 Entry Points

| Action     | Description                                  |
| ---------- | -------------------------------------------- |
| **New**    | Create a new vision document for a component |
| **Resume** | Continue working on an in-progress document  |
| **Edit**   | Modify a previously completed document       |

### 2.3 Session Greeting

When a PO starts a session, bro:

1. Remembers the last document the PO was working on
2. Displays a section status summary:

```markdown
Welcome back. You were working on **payment-gateway v2**:

| Section                        | Status                     |
| ------------------------------ | -------------------------- |
| 1. Preface                     | ✅ Complete                 |
| 2. Getting Started             | ✅ Complete                 |
| 3. Features & Business Process | 🟡 3/9 done                 |
| 4. Functional Design           | ⬜ Not started              |
| 5. Entities                    | 🟡 2 entities, needs detail |
| ...                            | ...                        |

Continue, or work on a different document?
```

### 2.4 Mid-Conversation Navigation

- PO can request to switch sections at any time
- Agent confirms before switching: "You have unsaved progress. Save as draft and switch, or continue here?"
- Progress is saved with appropriate status before switching

---

## 3. Document Structure

### 3.1 Identification

Documents are identified by **Component Name + Version**:

- `payment-gateway-v1`
- `payment-gateway-v2`
- `user-auth-v1`

### 3.2 Folder Structure

```
vision-docs/
  payment-gateway/
    v1/
      _meta.json                    # Document metadata, section statuses
      01-preface.json
      02-getting-started.json
      03-01-list-of-features.json
      03-02-business-processes.json
      03-03-feature-details.json
      03-04-l1-functional-capabilities.json
      03-05-l2-functional-capabilities.json
      03-06-unique-selling-points.json
      03-07-what-it-consumes.json
      03-08-what-it-produces.json
      03-09-control-restrictions.json
      03-10-extendibility-needs.json
      03-11-non-functional-needs.json
      04-functional-design.json
      05-entity-{name}.json         # Dynamic: one per entity
      06-01-list-of-apis.json
      06-02-list-of-events.json
      06-03-reusable-libraries.json
      06-04-user-interfaces.json
      06-05-error-messages.json
      06-06-extendibility-capabilities.json
      06-07-admin-configurations.json
      06-08-org-configurations.json
      07-iteration-{name}.json      # Dynamic: one per iteration
      08-01-acceptance-criteria.json
      08-02-use-cases.json
      09-01-faq.json
      09-02-dependencies-impact.json
      09-03-assumptions.json
      09-04-open-items.json
      09-05-third-party-integration.json
      09-06-additional-points.json
    v1.md                           # Combined Markdown export
```

### 3.3 Section Split Strategy

| Section                        | Structure | Files                                    |
| ------------------------------ | --------- | ---------------------------------------- |
| 1. Preface                     | Single    | `01-preface.json`                        |
| 2. Getting Started             | Single    | `02-getting-started.json`                |
| 3. Features & Business Process | Split 9+  | `03-01-*.json` through `03-11-*.json`    |
| 4. Functional Design           | Single    | `04-functional-design.json`              |
| 5. Entities                    | Dynamic   | `05-entity-{name}.json` per entity       |
| 6. APIs, Events, Messages      | Split 8   | `06-01-*.json` through `06-08-*.json`    |
| 7. Value Iterations            | Dynamic   | `07-iteration-{name}.json` per iteration |
| 8. Executable Specs            | Split 2   | `08-01-*.json`, `08-02-*.json`           |
| 9. Additional Details          | Split 6   | `09-01-*.json` through `09-06-*.json`    |

---

## 4. Section Status Model

| Status         | Meaning                                             |
| -------------- | --------------------------------------------------- |
| `not_started`  | PO hasn't touched this section yet                  |
| `in_progress`  | PO is actively working on it                        |
| `needs_detail` | PO provided minimal answers, flagged for more depth |
| `draft`        | Content captured, but PO hasn't reviewed/confirmed  |
| `complete`     | PO explicitly marked as done                        |

### 4.1 Status Determination

- **Schema Validation**: All required fields populated
- **LLM Assessment**: Content is meaningful (not placeholder text)
- **PO Override**: PO can manually set any status regardless of validation

---

## 5. Agent Architecture

### 5.1 Subagent Model

Each section can have its own subagent with:

- Dedicated prompt
- Structured output schema
- Section-specific tools
- Configurable approach (Q&A, template, freeform)

### 5.2 Configuration Structure

```
configs/
  vision-agent/
    sections.yaml           # Section structure, navigation, status
    agents.yaml             # Agent-to-section mappings

prompts/
  vision-agent/
    coordinator.md          # Main coordinator prompt
    03-01-features.md       # Section-specific prompts
    05-entity.md
    ...

schemas/
  vision-agent/
    03-01-features.json     # JSON Schema for structured output
    05-entity.json
    ...
```

### 5.3 agents.yaml Example

```yaml
agents:
  coordinator:
    prompt: "vision-agent/coordinator"
    tools: ["handoff", "get_document_status", "list_documents", "export_markdown"]

  features_agent:
    section: "03-01"
    prompt: "vision-agent/03-01-features"
    output_schema: "vision-agent/03-01-features.json"
    approach: "qa"
    tools: ["read_file", "update_section", "get_document_status"]

  entity_agent:
    section: "05"
    type: "dynamic"
    prompt: "vision-agent/05-entity"
    output_schema: "vision-agent/05-entity.json"
    approach: "template"
    tools: ["read_file", "update_section", "list_entities", "create_entity"]
```

### 5.4 Section Approach Configuration

Section-to-approach mappings are **configurable** via YAML:

| Approach   | Use Case                                   |
| ---------- | ------------------------------------------ |
| `qa`       | Complex sections requiring guided Q&A      |
| `template` | Moderate sections with template + guidance |
| `freeform` | Simple sections with light validation      |

---

## 6. Agent Behavior

### 6.1 Personality & Tone

**Professional & Concise**: Straight to business, minimal pleasantries, efficient.

### 6.2 Adaptive Questioning

For Q&A-style sections, the agent:

- Gauges response richness from the PO
- If PO gives detailed answers → digs deeper with follow-ups
- If PO gives short answers → wraps up, flags section as `needs_detail`

### 6.3 Coordinator Flow

1. After completing a section, coordinator **suggests** the next logical section
2. PO can override and choose any section
3. Coordinator hands off to the appropriate subagent

---

## 7. Dynamic Sections

Sections 5 (Entities) and 7 (Value Iterations) support variable numbers of items.

### 7.1 Adding Items

- After completing an item, agent prompts: "Do you have another entity to add?"
- PO can also explicitly request: "Add another entity"

### 7.2 Editing Items

Agent supports both:

- **Direct naming**: "Edit Payment Profile entity"
- **List selection**: "Edit an entity" → shows list → PO picks

### 7.3 Removing Items

- Requires confirmation: "Are you sure you want to delete 'Payment Profile'? This cannot be undone."

### 7.4 Ordering

- Order matters (especially for Value Iterations)
- PO can reorder: "Move Iteration 3 before Iteration 2"

---

## 8. Tools

### 8.1 Standard Tools (from dynagent)

| Tool         | Purpose                        |
| ------------ | ------------------------------ |
| `read_file`  | Read file via File Server MCP  |
| `write_file` | Write file via File Server MCP |
| `list_files` | List files via File Server MCP |
| `handoff`    | Transition between subagents   |

### 8.2 Vision-Specific Tools

| Tool                  | Purpose                                          |
| --------------------- | ------------------------------------------------ |
| `get_document_status` | Retrieve status of all sections for a vision doc |
| `update_section`      | Save content to a specific section               |
| `export_markdown`     | Generate human-readable Markdown export          |
| `set_section_status`  | Allow PO to manually override section status     |
| `list_documents`      | List available vision documents                  |
| `create_document`     | Initialize a new vision document                 |

---

## 9. Export

### 9.1 Format

Combined Markdown file following the ToC structure.

### 9.2 Triggers

| Trigger              | Description                                                             |
| -------------------- | ----------------------------------------------------------------------- |
| **On Demand**        | PO explicitly requests "export to markdown"                             |
| **Auto on Complete** | Automatically generated when all sections reach at least `draft` status |

---

## 10. Error Handling

### 10.1 Retry Strategy

- Agent retries failed operations automatically (2-3 attempts)
- Only surfaces error to PO if all retries fail

### 10.2 On Failure

- Halt the workflow
- Clearly explain the issue
- Ask PO to resolve before continuing

---

## 11. Session Management

### 11.1 Persistence

Sessions are persistent (handled by Chainlit/LangGraph checkpointer). PO can close browser and resume later.

### 11.2 User Model

Single user per document. No concurrent editing.

---

## 12. Future Scope

The following features are noted for future iterations:

| Feature                       | Description                                                         |
| ----------------------------- | ------------------------------------------------------------------- |
| **Conversational Discovery**  | Freeform conversation that maps responses to sections automatically |
| **Configurable Tone**         | Let POs set preferred agent personality (formal, friendly, etc.)    |
| **JIRA Integration**          | Create epics/stories from value iterations and features             |
| **Confluence Export**         | Push completed docs to wiki for visibility                          |
| **Git Integration**           | Auto-commit version changes                                         |
| **Notifications**             | Alert stakeholders on document status changes                       |
| **Collaborative Editing**     | Multiple POs working on the same document                           |
| **Section Templates Library** | Pre-built templates for common component types                      |

---

## 13. File Reference

### 13.1 Key Files to Create

| Path                                 | Purpose                       |
| ------------------------------------ | ----------------------------- |
| `src/bro_chat/agents/bro.py`         | Main bro agent implementation |
| `configs/vision-agent/sections.yaml` | Section structure config      |
| `configs/vision-agent/agents.yaml`   | Subagent mappings             |
| `prompts/vision-agent/*.md`          | Section prompts               |
| `schemas/vision-agent/*.json`        | Structured output schemas     |

### 13.2 Existing Files to Reference

| Path                              | Purpose                 |
| --------------------------------- | ----------------------- |
| `src/bro_chat/agents/dynagent.py` | Pattern to follow       |
| `docs/living-docs/toc.md`         | ToC structure reference |

---

## Appendix A: _meta.json Schema

```json
{
  "component": "payment-gateway",
  "version": "v1",
  "created_at": "2026-01-31T10:00:00Z",
  "updated_at": "2026-01-31T14:30:00Z",
  "last_section": "03-02",
  "sections": {
    "01-preface": {
      "status": "complete",
      "updated_at": "2026-01-31T10:15:00Z"
    },
    "02-getting-started": {
      "status": "complete",
      "updated_at": "2026-01-31T10:30:00Z"
    },
    "03-01-list-of-features": {
      "status": "in_progress",
      "updated_at": "2026-01-31T14:30:00Z"
    }
  },
  "dynamic_items": {
    "entities": ["payment-profile", "transaction-record"],
    "value_iterations": ["mvp", "phase-2"]
  }
}
```

---

## Appendix B: Decision Log

| Decision          | Choice                                 | Rationale                                 |
| ----------------- | -------------------------------------- | ----------------------------------------- |
| Interaction Model | Section-Based Navigation               | Flexibility for POs to work non-linearly  |
| Storage Format    | JSON per section + MD export           | Manageable schemas, human-readable export |
| Section Approach  | Configurable (Q&A/template/freeform)   | Different sections have different needs   |
| Agent Tone        | Professional & Concise                 | Respects PO time                          |
| Validation        | Schema + LLM + PO Override             | Quality assurance with human control      |
| Document ID       | Component + Version                    | Supports iteration on components          |
| Dynamic Sections  | Agent prompts, confirm delete, ordered | Intuitive CRUD for variable items         |
| Error Handling    | Retry then halt                        | Graceful but clear when issues arise      |

---

*Specification compiled from iterative Q&A session on 2026-01-31*
