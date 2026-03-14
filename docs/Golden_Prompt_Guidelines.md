# Prompt Engineering Guidelines for Dynagent Agent Prompts

These guidelines define how to write, structure, and maintain agent prompts in the Dynagent multi-agent system. Each instruction is anchored to [Anthropic's prompt engineering best practices](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview)

---

## Instruction Index

| #     | Title                                                                                                                     | Priority |
| ----- | ------------------------------------------------------------------------------------------------------------------------- | -------- |
| 1.1   | [Use XML Tags to Separate Structural Concerns](#11-use-xml-tags-to-separate-structural-concerns)                          | HIGH     |
| 2     | [Standard Prompt Template](#2-standard-prompt-template)                                                                   | HIGH     |
| 3.1   | [Give the Agent a Pipeline-Aware Role](#31-give-the-agent-a-pipeline-aware-role)                                          | HIGH     |
| 3.2   | [Declare Inputs Explicitly](#32-declare-inputs-explicitly)                                                                | MEDIUM   |
| 3.3   | [Context: Reference Files](#33-context-reference-files)                                               | HIGH     |
| 3.4   | [Provide 3–5 Diverse Examples Including Edge Cases](#34-provide-35-diverse-examples-including-edge-cases)                 | HIGH     |
| 3.5   | [Output: Schema, Guidance, Location](#35-output-schema-guidance-location)                                                 | HIGH     |
| 3.5.1 | [Use Self-Describing Schemas with x-fbp-pragmas](#351-use-self-describing-schemas-with-x-fbp-pragmas)                     | HIGH     |
| 3.6   | [Workflow: Step-by-Step Procedure](#36-workflow-step-by-step-procedure)                                                   | HIGH     |
| 3.6.1 | [Use step XML Tags for Workflow Steps](#361-use-step-xml-tags-for-workflow-steps)                                         | HIGH     |
| 3.6.2 | [Be Explicit About Tool Sequencing and Parallelism](#362-be-explicit-about-tool-sequencing-and-parallelism)               | HIGH     |
| 3.7   | [Add a Self-Verification Step Before Final Output](#37-add-a-self-verification-step-before-final-output)                  | HIGH     |
| 4.1   | [Eliminate Redundant Sections](#41-eliminate-redundant-sections)                                                          | MEDIUM   |
| 4.2   | [Explain the WHY Behind Critical Rules](#42-explain-the-why-behind-critical-rules)                                        | MEDIUM   |
| 4.3   | [Reframe Negative Instructions as Positive Directives](#43-reframe-negative-instructions-as-positive-directives)          | MEDIUM   |
| 4.4   | [Extract Shared Boilerplate into Reusable Reference](#44-extract-shared-boilerplate-into-reusable-reference)              | LOW      |
| 4.5   | [Place Long-Form Reference Data at Top, Instructions After](#45-place-long-form-reference-data-at-top-instructions-after) | MEDIUM   |
| 5     | [Applying These Instructions: Checklist](#5-applying-these-instructions-checklist)                                        | —        |

---

## 1. Structural Foundation

### 1.1 Use XML Tags to Separate Structural Concerns

**Anthropic best practice:** [Use XML tags to structure prompts](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/use-xml-tags) — "XML tags help Claude distinguish between different parts of the prompt."

**Instruction:** Wrap top-level prompt sections in named XML tags. Use these tags consistently across all agent prompts:

```
<role>           — Who the agent is, pipeline position, constraints and key constraint
<inputs>         — Required user-supplied parameters + guard clause (e.g. - omit for batch agents)
<context>        — Background info, reference files, shared configs
<tools>          — Tool usage instructions using <tool> sub-tags (see §3.3.2)
<examples>       — Input/output examples in <example> sub-tags (see §3.4)
<outputs>        — Output format, schema, guidance, and file location (see §3.5)
<workflow>       — Step-by-step procedure using <step> sub-tags (see §3.6.1)
<validation>     — Pre-output self-check checklist (see §3.7)
```

**Sub-tags for structured sections:**
- `<role>` uses `<constraints>` sub-tag for non-key operating constraints (see [§3.1](#31-give-the-agent-a-pipeline-aware-role))
- `<workflow>` uses `<step n="N" parallel="true" depends_on="N">` sub-tags (see [§3.6.1](#361-use-step-xml-tags-for-workflow-steps))
- `<tools>` uses `<tool name="...">` sub-tags with `<usage>` (see [§3.3.2](#332-structure-the-tools-section-with-sub-tags))
- `<examples>` uses `<example>` sub-tags with `<description>`, `<inputs>`, `<output>`, `<note>`

Keep markdown inside XML tags for readability (headers, lists, code blocks).

**Example:**
```xml
<context>
## Input
- **JIRA_NUMBER**: The JIRA/LLD ID (e.g. "MER-74405")
- **user_name**, **repo_name**, **jira_number**: Provided in the user message
</context>

<role>
You are a pipeline list-extractor agent...
</role>

<workflow>
    <step n="1" parallel="true">
    Initialize context and discover files
    In a single parallel batch, make all three calls simultaneously:
    - Call ...
    </step>
</workflow>
```

---

## 2. Standard Prompt Template

Follow the structure provided below while creating / restructuring prompts. If you cannot map a section to the agent's needs, ask the user for guidance. Sections marked "optional" can be omitted when not applicable.

```xml
<role>
  You are a [SPECIFIC ROLE] in the [DOMAIN] pipeline.
  You sit [POSITION IN PIPELINE]: after [PREDECESSOR] and before [SUCCESSOR].
  You are [INVOCATION MODE: batch-invoked with single items / list-extractor with structured output / interactive coordinator].
<!-- Optional: include when the agent has hard rules beyond the single key constraint -->
<constraints>
  - Never write to the workspace before reading and validating the source file.
  - Do not invent field values when the source material is silent — use null.
  - Maximum 2 tool retries on transient failure; surface error after that.
</constraints>
Key constraint: [ONE SENTENCE about the most important operating constraint].
</role>

<!-- Omit <inputs> for batch-invoked agents where inputs come from the orchestrator -->
<inputs>
  Required parameters from the user's message:

  - **[PARAMETER NAME 1]** — [description] (e.g. `[example]`)
  - **[PARAMETER NAME 2]** — [description] (e.g. `[example]`)

  If any parameter is missing, ask the user to provide it before proceeding.
</inputs>

<context>

## Reference Files
- `docs/FBPAppMeta.md` — APP_NAME, APP_TYPE, SCHEMAS_DIR, etc.
- [OTHER REFERENCE FILES]

</context>

<tools>
<!-- Structured tool reference — one <tool> per tool -->
<tool name="set_context_tool">
  <usage>
  Call once in step 1 to initialize context. This will setup a record in the cache that will be used by other file tools
  </usage>
</tool>
</tools>

<examples>
<!-- Examples BEFORE workflow — they anchor understanding (see §3.4) -->
<!-- Every example should include input context -->

  <example>
    <description>Normal case</description>
    <inputs>[relevant section of input document]</inputs>
    <output>[sample output]</output>
  </example>

  <example>
    <description>Edge case: [description]</description>
    <inputs>[relevant section of input document]</inputs>
    <output>[sample output]</output>
  </example>

  <example>
    <description>Empty/error case</description>
    <inputs>[relevant section of input document]</inputs>
    <output>[sample output]</output>
    <note>[explanation of why this input produces this output]</note>
  </example>
</examples>


<outputs>
  <schema>
  <!-- Keep this as is when output_schema is set in agents.yaml. Injected by harness. -->
    {{output-schema}}
  </schema>

  <format>
    Single JSON object conforming to <outputs>.<schema>.
    No markdown fences, no preamble, no trailing commentary.
  </format>

  <!-- Include when agent has output_schema with x-fbp-pragmas -->
  <guidance>
    Follow x-fbp-pragmas embedded in each schema property
    as primary guidance for populating that field.

    Do not invent values when source material is silent — use null
    for optional fields, empty arrays for optional array fields.

    If extraction fails: {"extractionStatus": "FAILED", "reason": "..."}
  </guidance>

  <!-- Include when agent writes output files -->
  <location>
    Write to: {workspace}/{meta_subdir}/{jira_number}/{file}.json
    Tool: mer_write_file_tool
  </location>
</outputs>

<workflow>
<!-- Step attributes: parallel="true" means issue all tool calls in that step simultaneously.
     depends_on="N" means wait for step N to complete before starting this step. -->

  <step n="1" parallel="true">
    Initialize context and discover files

    - Call `set_context_tool` with `agent_name`, `user_name`, `repo_name`, `jira_number`
    - Call `mer_read_file_tool` with `file_name = "docs/FBPAppMeta.md"`
    - [other independent reads]
  </step>

  <step n="2" depends_on="1">
    [MAIN PROCESSING STEP]

    [Processing instructions with inline WHY annotations for non-obvious constraints]

    <!-- For agents with output_schema in agents.yaml: -->
    Extraction rules are defined in `<outputs>.<schema>` via `x-fbp-pragmas.[ROLE]` annotations.
    Follow those as the single source of truth for what to extract and how.

    <!-- For agents without output_schema: -->
    [Domain-specific processing instructions]
  </step>

  <step n="3" depends_on="2">
    Shape output

    Construct your response per `<outputs>.<format>`.
    <!-- When <guidance> is present: -->
    Apply the population rules in `<outputs>.<guidance>`.
  </step>

  <!-- Include step 4 when <validation> is present -->
  <step n="4" depends_on="3">
    Verify your output against every check in `<validation>`.
    If any check fails, fix the issue and re-verify before continuing.
  </step>

  <!-- Include step 5 when <location> is present in <outputs> -->
  <step n="5" depends_on="4">
    Write and respond

    Write the validated output per `<outputs>.<location>`.
    Send one final assistant message confirming the write.
  </step>
</workflow>

<validation>
  Before sending your final response, verify ALL of the following.
  If any check fails, fix the issue and re-verify.

  1. [CHECK 1]
  2. [CHECK 2]
  3. [CHECK 3]
  4. [Output format check — no markdown fences, no prose, etc.]
  5. You already wrote [output file]
</validation>
```
---

## 3. Section Details

### 3.1 Give the Agent a Pipeline-Aware Role

**Anthropic best practice:** [Give Claude a role](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/system-prompts#give-claude-a-role) — "Giving Claude a specific role or persona can improve performance."

**Instruction:** The role section must state three things:
1. **What** the agent does (one sentence)
2. **Where** it sits in the pipeline (predecessor/successor agents)
3. **Key operating constraint** (batch-invoked with single item? list-extractor with structured output?)
4. **Constraints** - list any non-key constraints

**Example:**
```xml
<role>
  You are a Java code generator for FBP behaviour handler classes.

  You sit in the behaviour pipeline AFTER behaviour-md-generator (which
  produces the behaviour requirement MD) and are the FINAL agent in the
  behaviour chain. You are batch-invoked: you receive ONE behaviour at a time
  and must produce ONE Java file.

  Key constraint: You are invoked via batch_invoker — there is no interactive
  user. Generate complete, compilable code without asking questions.
  <constraints>
    - Never write to the workspace before reading and validating the source file.
    - Do not invent field values when the source material is silent — use null.
    - Maximum 2 tool retries on transient failure; surface error after that.
  </constraints>
  Key constraint: [ONE SENTENCE about the most important operating constraint].
</role>
```

---

### 3.2 Declare Inputs Explicitly

**Anthropic best practice:** [Be clear and direct](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/be-clear-and-direct) — "Provide Claude with all relevant context so it knows exactly what you want."

**Instruction:** For interactive or coordinator agents, list every required parameter the agent expects from the user's message. Include the parameter name, a short description, and an example value. End with a guard clause instructing the agent to ask for missing parameters before proceeding. Omit `<inputs>` entirely for batch-invoked agents where the orchestrator supplies all inputs.

**Example:**
```xml
<inputs>
Required parameters from the user's message:

- **repo_name** — target repository (e.g. `oepy-services-party`)
- **jira_number** — JIRA ticket ID (e.g. `MER-74405`)
- **user_name** — workspace owner (e.g. `john.doe`)

If any parameter is missing, ask the user to provide it before proceeding.
</inputs>
```

---


### 3.3 Context: Reference Files

**Instruction:** The `<context>` section serves as the agent's reference shelf. Include:
1. **Reference files** — what exists in the workspace that the agent may need to read
2. **Injected content** — what the harness provides at prompt-build time
3. **Tools** - any special handling for the tools that the agent can call.

**Example:**
```xml
<context>

## Reference Files
- `docs/FBPAppMeta.md` — APP_NAME, APP_TYPE, SCHEMAS_DIR
- `docs/FeatureLLD/{task-name}.md` — the LLD document to extract from
- `kg-node-meta/node_registry.json` — cross-repo node type resolution

</context>
```

#### 3.3.2 Structure the `<tools>` Section with Sub-Tags

**Anthropic best practice:** [Tool use](https://docs.anthropic.com/en/docs/build-with-claude/tool-use) — "Provide clear descriptions of each tool's parameters and purpose."

**Problem:** Some tools might require non-obvious handling. This is to be mentioned under the `<context>` section.

**Instruction:** Structure the `<tools>` section with `<tool name="...">` sub-tags, each containing `<usage>` and optionally `<signature>` elements. This keeps each tool's guidance self-contained and easy to maintain.

**Example:**
```xml
<tools>
  <tool name="set_context_tool">
    <usage>
    Call once in step 1 (parallel batch) to initialize context. This is internally used by all other file tools to derive the file path.
    Use `agent_name = "model-list-extractor"` with all keys in snake_case.
    </usage>
  </tool>
</tools>
```

---

### 3.4 Provide 3–5 Diverse Examples Including Edge Cases

**Anthropic best practice:** [Use examples (few-shot prompting)](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/few-shot-examples) — "Examples are one of the most powerful tools... Include edge cases."

**Instruction:** Include 3–5 examples in `<example>` tags covering: normal (3+ items), minimal (1 item), empty/error, and at least one domain-specific edge case. Every example should include an `<inputs>` showing what input produces the output — even minimal and empty cases. This helps the model pattern-match input→output relationships rather than memorising outputs in isolation.

**Example:**
```xml
<examples>

<example>
<description>Normal case: 3 models found in Section 1</description>
<inputs>
## Section 1: Data Models
### 1.1 Party (Schema Type: Hybrid)
| Column Name | Data Type | Mandatory |
| ----------- | --------- | --------- |
| partyNumber | String    | Y         |

### 1.2 ContactDetails (Schema Type: DTO)
...

### 1.3 PartyProfileAttribute (Schema Type: Hybrid)
...
</inputs>
<output>
{"models": [{"name": "Party"}, {"name": "ContactDetails"}, {"name": "PartyProfileAttribute"}]}
</output>
</example>

<example>
<description>Minimal case: only 1 model</description>
<inputs>
## Section 1: Data Models
### 1.1 TransactionRecord (Schema Type: Hybrid)
...
</inputs>
<output>
{"models": [{"name": "TransactionRecord"}]}
</output>
</example>

<example>
<description>Edge case: models extracted from Section 8 Input/Output columns (no explicit model section)</description>
<inputs>
## Section 8: Behaviours
| Name            | Input *(from IDM)*          | Output *(to IDM)* |
| --------------- | --------------------------- | ----------------- |
| fetchParty      | DM Customer, ContactDetails | DM Customer       |
| validateRequest |                             |                   |
</inputs>
<output>
{"models": [{"name": "DM Customer"}, {"name": "ContactDetails"}]}
</output>
<note>Extracted unique values from Input/Output columns; "validateRequest" row contributed nothing because both columns were empty.</note>
</example>

</examples>
```

### 3.5 Output: Schema, Guidance, Location

Used to shape the output. Contains:
- **Schema** — Output structure; present when `output_schema` is set for the agent in `agents.yaml` (see §3.5.1)
- **Format** - Generic instructions & output format
- **Guidance** — Additional instructions for populating the output when x-fbp-pragmas are present.
- **Location** — Where to write the output files (typically via tool call)

**Example** -
```xml
<outputs>
  <schema>
    {{output-schema}}
  </schema>

  <format>
    Single JSON object conforming to <outputs>.<schema>.
    No markdown fences, no preamble, no trailing commentary.
  </format>

  <guidance>
    Follow x-fbp-pragmas embedded in each schema property
    as primary guidance for populating that field.

    Do not invent values when source material is silent — use null
    for optional fields, empty arrays for optional array fields.

    If extraction fails: {"extractionStatus": "FAILED", "reason": "..."}
  </guidance>

  <location>
    Write to: {workspace}/{meta_subdir}/{jira_number}/{file}.json
    Tool: mer_write_file_tool
  </location>
</outputs>
```

#### 3.5.1 Use Self-Describing Schemas with `x-fbp-pragmas`

**Anthropic best practice:** [Be clear and direct](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/be-clear-and-direct) — single source of truth reduces contradiction. Also: [Structured outputs](https://docs.anthropic.com/en/docs/build-with-claude/structured-outputs) — schemas guide output format.

**Instruction:** A JSON schema with `x-fbp-pragmas` annotations that tell the agent HOW to extract and populate each field will be available in `<outputs>.<schema>`. The pragma key should match the agent's role (e.g., `extractor` for list-extractors, `designer` for designers, `generator` for generators).

Add a single sentence in `<workflow>`→`<step>` referencing the schema: "Extraction rules are defined in the schema's `x-fbp-pragmas.extractor` annotations. Follow those rules as the single source of truth."

**Benefits:**
- Schema is the single source of truth for both structure and extraction logic
- Schema changes propagate to the agent automatically without prompt edits
- Consistent with the `x-fbp-pragmas` pattern used across the codebase

**Example:** - Assuming this agent has a `<output>`.`<schema>` available.
```xml
<workflow>
  <step n="2" depends_on="1">
    Extraction rules are defined in `<outputs>.<schema>` via `x-fbp-pragmas.[ROLE]` annotations.
    Follow those as the single source of truth for what to extract and how.
  </step>

  <step n="3" depends_on="2">
    Shape output

    Construct your response per `<outputs>.<format>`.
    Apply the population rules in `<outputs>.<guidance>`.
  </step>
</workflow>
```

### 3.6 Workflow: Step-by-Step Procedure

A list of steps to be executed, using `<step>` tags (see §3.6.1).

#### 3.6.1 Use `<step>` XML Tags for Workflow Steps

**Anthropic best practice:** [Use XML tags to structure prompts](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/use-xml-tags) — "XML tags help Claude distinguish between different parts of the prompt."

**Instruction:** Wrap each workflow step in a `<step>` tag with structured attributes:
- `n` — step number
- `parallel` — set to `"true"` for parallel steps (omit for sequential)
- `depends_on` — comma-separated step numbers this step depends on (omit for step 1)

The step title goes on the first line inside the tag. This makes dependencies machine-readable and consistent with the prompt's XML structure.

**Example:**
```xml
<step n="1" parallel="true">
Initialize context and discover files

In a single parallel batch, make all three calls simultaneously:
...
</step>

<step n="2" depends_on="1">
Read the LLD file

From the `mer_list_files_tool` result...
</step>
```


#### 3.6.2 Be Explicit About Tool Sequencing and Parallelism

**Anthropic best practice:** [Tool use](https://docs.anthropic.com/en/docs/build-with-claude/tool-use) — "Specify tool sequencing... Claude can make multiple tool calls in parallel."

**Instruction:** Use `<step>` attributes to declare parallelism and dependencies. Within a parallel step, list all calls that should execute simultaneously. After the step body, summarise what state is available for subsequent steps.

**Example:**
```xml
<workflow>

<step n="1" parallel="true">
Initialize context and discover files

In a single parallel batch, make all three calls simultaneously:

- Call `set_context_tool` with `agent_name = "model-list-extractor"`, `user_name`, `repo_name`,
  `jira_number` (use **snake_case** for all keys).
  WHY: `set_context_tool` matches keys by snake_case convention; mismatched casing causes lookup failures.
- Call `mer_read_file_tool` with `file_name = "docs/FBPAppMeta.md"`.
- Call `mer_list_files_tool` with `path = "docs/FeatureLLD"`.

After this step you have: context initialized, APP_NAME/APP_TYPE/FEATURE_LLD_DIR values from
`FBPAppMeta.md`, and the directory listing of `docs/FeatureLLD`.
</step>
</workflow>
```

---

### 3.7 Add a Self-Verification Step Before Final Output

**Anthropic best practice:** [Extended thinking / chain of thought](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/chain-of-thought) — "Ask Claude to verify its own work."

**Instruction:** Define a `<validation>` section as a **sibling** of `<workflow>`. It contains an imperative checklist the agent must satisfy before emitting output. Then, include a dedicated `<step>` inside `<workflow>` that references `<validation>` — e.g. "Verify your output against every check in `<validation>`. If any check fails, fix the issue and re-verify."

This separation means the validation criteria are easy to scan independently, while the workflow enforces that the check actually runs.

**Example:**
```xml
<workflow>
  ...
  <step n="4" depends_on="3">
    Verify your output against every check in `<validation>`.
    If any check fails, fix the issue and re-verify before continuing.
  </step>
  ...
</workflow>

<validation>
Before sending your final response, verify ALL of the following.
If any check fails, fix the issue and re-verify.

1. [CHECK 1]
2. [CHECK 2]
3. [CHECK 3]
4. [Output format check — no markdown fences, no prose, etc.]
5. You already wrote [output file]
</validation>
```

---

## 4. Best Practices

### 4.1 Eliminate Redundant Sections

**Anthropic best practice:** [Be clear and direct](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/be-clear-and-direct) — "Give Claude the minimum information it needs."

**Instruction:** State each concern exactly once. If a concept needs to be referenced from two places, define it once with a clear name and reference it. Every redundancy is an opportunity for contradiction and wasted context tokens.

### 4.2 Explain the WHY Behind Critical Rules

**Anthropic best practice:** [Give Claude context](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/be-clear-and-direct#provide-contextual-information) — "When instructions seem arbitrary, the model may not weigh them properly."

**Instruction:** For every non-obvious constraint, add a one-sentence explanation of WHY. Format: `RULE. WHY: explanation.`

**Example:**
```xml
<step n="1" parallel="true">
Initialize context and discover files

- Call `set_context_tool` with all keys in **snake_case**.
  WHY: The context store matches keys by snake_case convention; mismatched casing
  causes silent lookup failures in downstream agents.
</step>
```

### 4.3 Reframe Negative Instructions as Positive Directives

**Anthropic best practice:** [Be direct about what you want](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/be-clear-and-direct) — "Tell Claude what to do, not just what not to do."

**Instruction:** Rewrite "Do NOT X" as "Always do Y instead." Reserve negatives only for truly catastrophic actions where additional emphasis is warranted. Negative-only framing doesn't tell the model what the correct alternative is.

**Example:**
```xml
<validation>
## Source Fidelity
- When information is ambiguous, STOP and ask one clarification question.
  WHY: This agent is batch-invoked; clarification requests surface as
  batch failures that operators review.
</validation>
```

---


### 4.4 Extract Shared Boilerplate into Reusable Reference

**Anthropic best practice:** [Be clear and direct](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/be-clear-and-direct) — reduce noise so the model focuses on what matters.

**Instruction:** Extract shared boilerplate (workspace conventions, context-init patterns, common tool instructions) into a reference document or a shared prompt fragment loaded by the framework. Each agent prompt should contain only the agent-specific delta. Duplicated boilerplate wastes tokens per prompt and creates a maintenance burden — a change must be applied to every prompt that copies it.

**Example:**
If the framework does not yet support prompt includes, create a shared reference document and have each prompt say: "Follow the workspace_context and file server conventions described in `docs/shared-agent-conventions.md`. Use `agent_name = 'model-list-extractor'`."

---

### 4.5 Place Long-Form Reference Data at Top, Instructions After

**Anthropic best practice:** [Long context tips](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/long-context-tips) — "Put long-form data (documents to analyze) near the top, and instructions/queries near the bottom."

**Instruction:** If there are large files required include those in the <context> tag

```
<role> → <inputs> → <context> + <tools> + <ref data> → <examples> → <outputs> → <workflow> → <validation>
```


---

## 5. Applying These Instructions: Checklist

When writing or reviewing a prompt, use this checklist:

- [ ] **XML tags** — top-level sections use the standard tag set (`<role>`, `<inputs>`, `<context>`, `<tools>`, `<examples>`, `<outputs>`, `<workflow>`, `<validation>`)
- [ ] **Consistent section order** — role → inputs → context + tools → examples → outputs → workflow → validation
- [ ] **Pipeline-aware role** with position, predecessor/successor, and key constraint
- [ ] **`<inputs>` for user params** — required params + guard clause; omit for batch-invoked agents
- [ ] **Reference data at top** — `<context>` before `<workflow>`
- [ ] **3–5 examples** including edge cases, each with `<inputs>` context
- [ ] **Consistent output tag** — use `<outputs>`
- [ ] **Self-describing schema** — `x-fbp-pragmas` with role-appropriate key (extractor/designer/generator)
- [ ] **Self-verification** — `<validation>` section as sibling of `<workflow>`, referenced by a workflow `<step>`
- [ ] **`<tools>` is a sibling of `<context>`** — not nested inside it
- [ ] **Tool sequencing** via `<step>` attributes: `parallel="true"` / `depends_on="N"`
- [ ] **No redundancy** — each concept stated once; shared boilerplate extracted
- [ ] **WHY** explained for non-obvious rules (format: `RULE. WHY: explanation.`)
- [ ] **Positive framing** — "always do X" preferred over "don't do Y"
