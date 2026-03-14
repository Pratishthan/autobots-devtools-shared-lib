# MER Prompt Evaluation Architecture

## Design Decisions (from discussion)

| Decision | Choice | Rationale |
|---|---|---|
| Eval scope | All pipeline stages | Quality pain is uniform across extractors and generators |
| Current validation | Manual review + Maven build | Two signals exist: human judgment + compilation |
| Eval execution | Offline (dev) + Inline (production) | Offline for prompt iteration, inline for quality gates |
| Eval dataset size | 1–3 LLDs with reviewed outputs | Enough to bootstrap; grows over time |
| Tooling | Langfuse now, Phoenix later | Abstract the backend so swapping is a config change |
| Eval target | Single agent invocation (not batch) | Batch is just parallelized single calls — test the atom |
| Eval criteria | Faithfulness + Completeness | Does the output capture everything the LLD specified? |
| Judge input | Scoped input only | Each stage evaluated against what it received, not full LLD |
| Trigger | `make eval` + CI on PR | Manual during dev, automated on prompt changes |

---

## Trace Validation Summary

Architecture validated against a real production trace (`trace-6ad1af17`, `model-list-extractor`, user `khushboo_123`, 2026-02-27).

### Trace Profile

| Metric | Value |
|---|---|
| Agent | `model-list-extractor` |
| Model | `gemini-2.0-flash` |
| LLM Calls | 5 (agent loop iterations) |
| Tool Calls | 4 (`mer_read_file` ×2, `mer_list_files` ×1, `set_sdlc_context` ×1) |
| Input Tokens | 11,352 |
| Output Tokens | 161 |
| Cost | $0.0012 |
| Latency | 10.1s |
| Middleware | `SummarizationMiddleware.before_model` ×5 |
| Scores | `[]` (empty — no eval wired yet) |
| Structured Response | `false` (schema not validated at runtime) |

### Findings

| Finding | Impact on Architecture |
|---|---|
| `scores: []` empty in Langfuse trace | Confirms `EvalBackend.log_score()` integration point exists but is unwired |
| `has_structured_response: false` | Schema validation not happening at runtime — Schema Validator gate is critical |
| 5 LLM calls for a list extraction | **NEW**: Need Trajectory Evaluator to catch prompt regressions causing extra loops |
| 11K tokens / $0.0012 per extraction | **NEW**: Need Cost Evaluator to flag token usage regressions across prompt versions |
| SummarizationMiddleware runs 5× | Middleware is transparent to evaluators but could affect quality if lossy on later iterations |

---

## Architecture Overview

The evaluation system has three layers, all tool-agnostic:

```
┌─────────────────────────────────────────────────────────────────┐
│                    OFFLINE EVAL HARNESS                          │
│  (make eval / CI on PR — prompt iteration workflow)              │
│                                                                  │
│  Eval Dataset ──→ Eval Runner ──→ Evaluators ──→ EvalBackend    │
│  (LLD + expected)  (single agent)  (schema/compile/LLM-judge/   │
│                                     trajectory/cost)             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                 INLINE PRODUCTION GATES                          │
│  (inside Nurture pipeline — quality checkpoints)                 │
│                                                                  │
│  List Extractor ──→ Schema Gate + Trajectory Gate                │
│  Generator ──→ LLM Judge Gate (faithfulness) + Cost Gate         │
│  All Artifacts ──→ Maven Build Gate                              │
│  ──→ EvalBackend.log_score()                                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              dynagent.eval (shared-lib)                          │
│  Evaluators + EvalBackend (abstract) + EvalRunner               │
│  Adapters: Langfuse | Phoenix | File-based                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Eval Dataset

Curated input→output pairs stored as files in the repo. No tool dependency.

### Structure

```
eval_datasets/
└── nurture/
    ├── datasets.yaml                    # Dataset manifest
    └── cases/
        ├── party-profile/
        │   ├── input.md                 # The LLD (or relevant section)
        │   ├── model-list.expected.json # Expected model list extractor output
        │   ├── behaviour-list.expected.json
        │   ├── scenario-list.expected.json
        │   └── items/
        │       ├── PartyBehaviour.expected.java
        │       ├── party-search.expected.feature
        │       └── Party.expected.json  # Expected OAS
        └── account-transfer/
            ├── input.md
            └── ...
```

### datasets.yaml

```yaml
datasets:
  - id: party-profile
    lld_path: cases/party-profile/input.md
    stages:
      model-list-extractor:
        expected: cases/party-profile/model-list.expected.json
      behaviour-list-extractor:
        expected: cases/party-profile/behaviour-list.expected.json
      scenario-list-extractor:
        expected: cases/party-profile/scenario-list.expected.json
      behaviour-java:
        items:
          - scoped_input: "PartyBehaviour"  # What the agent receives
            expected: cases/party-profile/items/PartyBehaviour.expected.java
      scenario-feature-generator:
        items:
          - scoped_input: "party-search"
            expected: cases/party-profile/items/party-search.expected.feature
      model-oas-generator:
        items:
          - scoped_input: "Party"
            expected: cases/party-profile/items/Party.expected.json
```

---

## Layer 2: Evaluators

Pure Python functions. Each takes `(input, output, expected?)` and returns a score. No tool dependency.

### Evaluator Types

#### 1. Schema Validator (heuristic)
**Applies to:** List extractors (model-list, behaviour-list, scenario-list)
**Checks:** Output conforms to the JSON schema defined in `agents.yaml`

```python
# In dynagent.eval.evaluators.schema
from autobots_devtools_shared_lib.dynagent.eval import EvalResult

def schema_evaluator(output: str, schema_path: str) -> EvalResult:
    """Validate structured output against JSON schema."""
    # Parse output as JSON
    # Validate against schema
    # Return EvalResult(score=1.0 if valid, 0.0 if not, details=errors)
```

#### 2. Completeness Checker (heuristic)
**Applies to:** List extractors
**Checks:** Expected items are all present in the extracted list

```python
# In dynagent.eval.evaluators.completeness
def completeness_evaluator(
    output: str,
    expected: str,
    key_field: str = "name"
) -> EvalResult:
    """Check if all expected items appear in the output list."""
    # Parse both as JSON lists
    # Compare key fields
    # Return EvalResult(score=matched/total, details=missing_items)
```

#### 3. LLM-as-Judge (faithfulness + completeness)
**Applies to:** All generators (behaviour-java, scenario-feature, model-oas)
**Checks:** Output faithfully and completely addresses the scoped input

```python
# In dynagent.eval.evaluators.llm_judge
def faithfulness_evaluator(
    scoped_input: str,
    output: str,
    judge_model: str = "gemini-2.0-flash"  # Cheap, fast judge
) -> EvalResult:
    """LLM judges whether output is faithful and complete vs scoped input."""
    # Construct judge prompt (see below)
    # Invoke judge LLM
    # Parse structured score (1-5) + reasoning
    # Return EvalResult(score=normalized, reasoning=text)
```

#### LLM Judge Prompt Template

```markdown
You are evaluating the output of a code generation agent.

## Input (what the agent was given):
{scoped_input}

## Output (what the agent produced):
{output}

## Evaluation Criteria:

1. **Faithfulness** (1-5): Does the output accurately reflect ALL requirements
   from the input? No hallucinated features, no contradictions.

2. **Completeness** (1-5): Are ALL requirements from the input addressed?
   No missing methods, edge cases, or scenarios.

Respond in JSON:
{
  "faithfulness": { "score": <1-5>, "reasoning": "<brief>" },
  "completeness": { "score": <1-5>, "reasoning": "<brief>" },
  "overall": <1-5>,
  "issues": ["<issue1>", "<issue2>"]
}
```

#### 4. Compilation Check (heuristic)
**Applies to:** End-to-end pipeline output
**Checks:** Maven build succeeds

```python
# In dynagent.eval.evaluators.compilation
def maven_build_evaluator(workspace_path: str) -> EvalResult:
    """Run Maven build and check for compilation errors."""
    # Execute mvn compile
    # Return EvalResult(score=1.0 if success, 0.0 if fail, details=errors)
```

#### 5. Trajectory Evaluator (heuristic — from trace validation)

**Discovered from:** Real trace showed 5 LLM calls for a single list extraction. A prompt regression could easily push this to 8-10 calls without anyone noticing.

**Applies to:** All agent invocations (extractors and generators)
**Checks:** Agent completed in a reasonable number of LLM iterations and tool calls

```python
# In dynagent.eval.evaluators.trajectory
@dataclass
class TrajectoryLimits:
    """Per-stage expected iteration bounds."""
    max_llm_calls: int
    max_tool_calls: int
    max_latency_seconds: float

# Baseline from trace analysis — calibrate per stage
TRAJECTORY_BASELINES: dict[str, TrajectoryLimits] = {
    "model-list-extractor": TrajectoryLimits(
        max_llm_calls=6,        # Observed: 5 (allow small buffer)
        max_tool_calls=5,       # Observed: 4
        max_latency_seconds=15, # Observed: 10.1s
    ),
    "behaviour-list-extractor": TrajectoryLimits(
        max_llm_calls=6,
        max_tool_calls=5,
        max_latency_seconds=15,
    ),
    "behaviour-java": TrajectoryLimits(
        max_llm_calls=8,        # Generators may need more iterations
        max_tool_calls=6,
        max_latency_seconds=30,
    ),
    # ... other stages
}

def trajectory_evaluator(
    stage: str,
    trace_data: TraceData,  # Extracted from Langfuse trace or agent callback
) -> EvalResult:
    """Evaluate whether the agent took an efficient execution path.

    Catches:
    - Prompt regressions that cause unnecessary looping
    - Tool call storms (agent calling same tool repeatedly)
    - Latency regressions from added complexity
    """
    limits = TRAJECTORY_BASELINES.get(stage)
    if not limits:
        return EvalResult(score=1.0, details={"reason": "no baseline defined"})

    penalties = []
    score = 1.0

    if trace_data.llm_call_count > limits.max_llm_calls:
        overshoot = trace_data.llm_call_count - limits.max_llm_calls
        penalty = min(overshoot * 0.15, 0.5)  # Max 50% penalty
        score -= penalty
        penalties.append(
            f"LLM calls: {trace_data.llm_call_count} "
            f"(max {limits.max_llm_calls}, -{penalty:.0%})"
        )

    if trace_data.tool_call_count > limits.max_tool_calls:
        overshoot = trace_data.tool_call_count - limits.max_tool_calls
        penalty = min(overshoot * 0.1, 0.3)
        score -= penalty
        penalties.append(
            f"Tool calls: {trace_data.tool_call_count} "
            f"(max {limits.max_tool_calls}, -{penalty:.0%})"
        )

    if trace_data.latency_seconds > limits.max_latency_seconds:
        penalty = 0.2
        score -= penalty
        penalties.append(
            f"Latency: {trace_data.latency_seconds:.1f}s "
            f"(max {limits.max_latency_seconds}s, -{penalty:.0%})"
        )

    # Detect repeated tool calls (same tool called >2× with identical args)
    repeated = trace_data.detect_repeated_tool_calls()
    if repeated:
        score -= 0.2
        penalties.append(f"Repeated tool calls: {repeated}")

    return EvalResult(
        score=max(score, 0.0),
        details={
            "llm_calls": trace_data.llm_call_count,
            "tool_calls": trace_data.tool_call_count,
            "latency_s": trace_data.latency_seconds,
            "penalties": penalties,
        },
    )
```

**TraceData extraction** — the evaluator needs structured trace data. Two sources:

1. **Offline eval:** Parse from Langfuse API response (the trace JSON you already have)
2. **Inline gate:** Capture from LangGraph agent callbacks during execution

```python
# In dynagent.eval.evaluators.trajectory
@dataclass
class TraceData:
    """Structured execution metrics extracted from a trace."""
    llm_call_count: int
    tool_call_count: int
    latency_seconds: float
    tool_calls: list[ToolCallRecord]  # name + args + latency

    @classmethod
    def from_langfuse_trace(cls, trace_json: dict) -> "TraceData":
        """Parse from Langfuse trace export (as seen in the real trace)."""
        observations = trace_json.get("observations", [])
        return cls(
            llm_call_count=sum(
                1 for o in observations if o["type"] == "GENERATION"
            ),
            tool_call_count=sum(
                1 for o in observations if o["type"] == "TOOL"
            ),
            latency_seconds=trace_json["trace"].get("latency", 0),
            tool_calls=[
                ToolCallRecord(
                    name=o["name"],
                    latency=o.get("latency", 0),
                )
                for o in observations
                if o["type"] == "TOOL"
            ],
        )

    @classmethod
    def from_agent_callback(cls, callback_data: dict) -> "TraceData":
        """Parse from LangGraph agent execution callbacks (inline mode)."""
        # Extract from agent's internal step tracking
        ...

    def detect_repeated_tool_calls(self) -> list[str]:
        """Find tools called more than 2× (potential infinite loop signal)."""
        from collections import Counter
        counts = Counter(tc.name for tc in self.tool_calls)
        return [f"{name} ×{count}" for name, count in counts.items() if count > 2]
```

#### 6. Cost Evaluator (heuristic — from trace validation)

**Discovered from:** Real trace showed 11,352 input tokens at $0.0012 per extraction. A prompt change that doubles context or adds few-shot examples could silently 3× costs across the pipeline.

**Applies to:** All agent invocations
**Checks:** Token usage and cost are within expected bounds per stage

```python
# In dynagent.eval.evaluators.cost
@dataclass
class CostBaseline:
    """Per-stage expected cost bounds."""
    max_input_tokens: int
    max_output_tokens: int
    max_cost_usd: float

# Baseline from trace analysis
COST_BASELINES: dict[str, CostBaseline] = {
    "model-list-extractor": CostBaseline(
        max_input_tokens=15_000,   # Observed: 11,352 (allow ~30% buffer)
        max_output_tokens=500,     # Observed: 161
        max_cost_usd=0.002,        # Observed: $0.0012
    ),
    "behaviour-java": CostBaseline(
        max_input_tokens=25_000,   # Generators consume more context
        max_output_tokens=5_000,   # Code output is longer
        max_cost_usd=0.01,
    ),
    # ... other stages
}

def cost_evaluator(
    stage: str,
    trace_data: TraceData,
) -> EvalResult:
    """Evaluate whether token usage and cost are within expected bounds.

    Catches:
    - Prompt bloat (added instructions/examples inflating input tokens)
    - Verbose output regressions (model generating too much boilerplate)
    - Cost regressions when switching models or adding few-shot examples
    """
    baseline = COST_BASELINES.get(stage)
    if not baseline:
        return EvalResult(score=1.0, details={"reason": "no baseline defined"})

    score = 1.0
    warnings = []

    # Input token check
    if trace_data.total_input_tokens > baseline.max_input_tokens:
        ratio = trace_data.total_input_tokens / baseline.max_input_tokens
        penalty = min((ratio - 1.0) * 0.3, 0.5)
        score -= penalty
        warnings.append(
            f"Input tokens: {trace_data.total_input_tokens:,} "
            f"(max {baseline.max_input_tokens:,}, {ratio:.1f}× baseline)"
        )

    # Output token check
    if trace_data.total_output_tokens > baseline.max_output_tokens:
        ratio = trace_data.total_output_tokens / baseline.max_output_tokens
        penalty = min((ratio - 1.0) * 0.2, 0.3)
        score -= penalty
        warnings.append(
            f"Output tokens: {trace_data.total_output_tokens:,} "
            f"(max {baseline.max_output_tokens:,}, {ratio:.1f}× baseline)"
        )

    # Cost check
    if trace_data.total_cost_usd > baseline.max_cost_usd:
        ratio = trace_data.total_cost_usd / baseline.max_cost_usd
        penalty = min((ratio - 1.0) * 0.3, 0.5)
        score -= penalty
        warnings.append(
            f"Cost: ${trace_data.total_cost_usd:.4f} "
            f"(max ${baseline.max_cost_usd:.4f}, {ratio:.1f}× baseline)"
        )

    return EvalResult(
        score=max(score, 0.0),
        details={
            "input_tokens": trace_data.total_input_tokens,
            "output_tokens": trace_data.total_output_tokens,
            "cost_usd": trace_data.total_cost_usd,
            "warnings": warnings,
        },
    )
```

**Extending TraceData for cost metrics:**

```python
# Added fields to TraceData
@dataclass
class TraceData:
    llm_call_count: int
    tool_call_count: int
    latency_seconds: float
    tool_calls: list[ToolCallRecord]
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0

    @classmethod
    def from_langfuse_trace(cls, trace_json: dict) -> "TraceData":
        observations = trace_json.get("observations", [])
        return cls(
            llm_call_count=sum(1 for o in observations if o["type"] == "GENERATION"),
            tool_call_count=sum(1 for o in observations if o["type"] == "TOOL"),
            latency_seconds=trace_json["trace"].get("latency", 0),
            total_input_tokens=sum(
                int(o.get("inputUsage") or 0) for o in observations
            ),
            total_output_tokens=sum(
                int(o.get("outputUsage") or 0) for o in observations
            ),
            total_cost_usd=sum(
                float(o.get("totalCost") or 0) for o in observations
            ),
            tool_calls=[
                ToolCallRecord(name=o["name"], latency=o.get("latency", 0))
                for o in observations if o["type"] == "TOOL"
            ],
        )
```

---

## Layer 3: EvalBackend (Abstraction Layer)

This is the key to tool independence. Define an abstract interface; implement adapters.

### Interface

```python
# In dynagent.eval.backend.base
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass
class EvalScore:
    dataset_id: str
    stage: str              # e.g. "behaviour-java"
    item_id: str            # e.g. "PartyBehaviour"
    evaluator: str          # e.g. "faithfulness_evaluator"
    score: float            # 0.0 - 1.0 normalized
    details: dict[str, Any] # Evaluator-specific metadata
    prompt_version: str     # Git commit hash or tag
    trace_id: str | None    # Link to observability trace
    # Trace-validated additions (from real trace analysis)
    llm_calls: int | None = None       # Number of LLM iterations
    tool_calls: int | None = None      # Number of tool executions
    input_tokens: int | None = None    # Total input token usage
    output_tokens: int | None = None   # Total output token usage
    cost_usd: float | None = None      # Total cost in USD
    latency_seconds: float | None = None  # End-to-end latency

class EvalBackend(ABC):
    """Abstract backend for storing and querying eval scores."""

    @abstractmethod
    def log_score(self, score: EvalScore) -> None:
        """Record a single evaluation score."""

    @abstractmethod
    def get_scores(
        self,
        dataset_id: str,
        stage: str | None = None,
        prompt_version: str | None = None,
    ) -> list[EvalScore]:
        """Query scores for comparison."""

    @abstractmethod
    def compare_versions(
        self,
        dataset_id: str,
        version_a: str,
        version_b: str,
    ) -> dict[str, Any]:
        """Compare scores between two prompt versions."""
```

### Adapters

```python
# Langfuse adapter (current)
# In dynagent.eval.backend.langfuse_adapter
class LangfuseEvalBackend(EvalBackend):
    """Stores scores as Langfuse scores attached to traces."""

    def log_score(self, score: EvalScore) -> None:
        self.langfuse.score(
            trace_id=score.trace_id,
            name=f"{score.stage}/{score.evaluator}",
            value=score.score,
            comment=json.dumps(score.details),
        )

    def get_scores(self, ...) -> list[EvalScore]:
        # Query Langfuse API for scores
        ...

# Phoenix adapter (future swap)
# In dynagent.eval.backend.phoenix_adapter
class PhoenixEvalBackend(EvalBackend):
    """Stores scores via Phoenix experiments API."""

    def log_score(self, score: EvalScore) -> None:
        # Use phoenix.evals experiment tracking
        ...

# File adapter (local dev, no infra needed)
# In dynagent.eval.backend.file_adapter
class FileEvalBackend(EvalBackend):
    """Stores scores as JSON files for local development."""

    def log_score(self, score: EvalScore) -> None:
        # Append to eval_results/{dataset_id}/{prompt_version}.jsonl
        ...
```

### Configuration

```python
# In dynagent.eval.backend
def get_eval_backend() -> EvalBackend:
    """Factory — reads EVAL_BACKEND env var."""
    backend = os.getenv("EVAL_BACKEND", "file")
    match backend:
        case "langfuse":
            return LangfuseEvalBackend()
        case "phoenix":
            return PhoenixEvalBackend()
        case "file":
            return FileEvalBackend()
```

**To swap from Langfuse to Phoenix later:** change `EVAL_BACKEND=phoenix` in your env. That's it.

---

## Eval Runner

Orchestrates dataset loading, agent invocation, evaluation, and score logging.

```python
# In dynagent.eval.runner
class EvalRunner:
    """Runs evaluations for a given dataset and stage."""

    def __init__(
        self,
        dataset_path: str,
        backend: EvalBackend,
        prompt_version: str,  # from git
    ):
        self.dataset = load_dataset(dataset_path)
        self.backend = backend
        self.prompt_version = prompt_version

    def eval_stage(self, stage: str) -> list[EvalScore]:
        """Evaluate a single pipeline stage across all dataset cases."""
        scores = []
        for case in self.dataset.cases:
            stage_config = case.stages.get(stage)
            if not stage_config:
                continue

            if stage_config.items:
                # Generator stage — eval each item
                for item in stage_config.items:
                    output = invoke_agent(
                        agent_name=stage,
                        user_message=item.scoped_input,
                        session_id=f"eval-{case.id}-{item.scoped_input}",
                    )
                    score = self._evaluate_generator(
                        stage, item, output, case.id
                    )
                    scores.append(score)
            else:
                # List extractor stage — eval single output
                output = invoke_agent(
                    agent_name=stage,
                    user_message=case.lld_content,
                    session_id=f"eval-{case.id}",
                )
                score = self._evaluate_extractor(
                    stage, stage_config, output, case.id
                )
                scores.append(score)

        return scores

    def eval_all(self) -> dict[str, list[EvalScore]]:
        """Evaluate all stages."""
        results = {}
        for stage in self.dataset.all_stages():
            results[stage] = self.eval_stage(stage)
        return results
```

---

## Inline Production Gates

Lightweight checks inside the Nurture pipeline. Uses the same evaluators but with pass/fail thresholds.

### Integration Points in Orchestrators

```python
# In nurture/services/behaviour_orch.py (conceptual)
from autobots_devtools_shared_lib.dynagent.eval import (
    faithfulness_evaluator,
    trajectory_evaluator,
    cost_evaluator,
    get_eval_backend,
    TraceData,
)

async def behaviour_orch(session_id: str, supervised: bool = False):
    # 1. Extract behaviour list
    behaviour_list, trace_data = await trigger_list_generator(...)

    # GATE 1: Schema validation (already exists via output_schema)
    # If it parsed, it passed. Log the score.
    backend = get_eval_backend()
    backend.log_score(EvalScore(
        stage="behaviour-list-extractor",
        evaluator="schema",
        score=1.0,
        ...
    ))

    # GATE 2 (NEW): Trajectory check — did the extractor loop too much?
    traj_result = trajectory_evaluator(
        stage="behaviour-list-extractor",
        trace_data=trace_data,
    )
    backend.log_score(EvalScore(
        stage="behaviour-list-extractor",
        evaluator="trajectory",
        score=traj_result.score,
        llm_calls=trace_data.llm_call_count,
        tool_calls=trace_data.tool_call_count,
        latency_seconds=trace_data.latency_seconds,
        ...
    ))
    if traj_result.score < 0.7:
        logger.warning(
            f"Trajectory regression in behaviour-list-extractor: "
            f"{trace_data.llm_call_count} LLM calls, "
            f"{trace_data.tool_call_count} tool calls"
        )

    # 2. Generate each behaviour
    for behaviour in behaviour_list:
        result, gen_trace = await invoke_agent("behaviour-java", behaviour.name, ...)

        # GATE 3: LLM faithfulness check (lightweight, single call)
        eval_result = faithfulness_evaluator(
            scoped_input=behaviour.to_prompt(),
            output=result.output,
        )
        backend.log_score(EvalScore(
            stage="behaviour-java",
            evaluator="faithfulness",
            score=eval_result.score,
            details=eval_result.details,
            ...
        ))

        # GATE 4 (NEW): Cost check — did token usage spike?
        cost_result = cost_evaluator(
            stage="behaviour-java",
            trace_data=gen_trace,
        )
        backend.log_score(EvalScore(
            stage="behaviour-java",
            evaluator="cost",
            score=cost_result.score,
            input_tokens=gen_trace.total_input_tokens,
            output_tokens=gen_trace.total_output_tokens,
            cost_usd=gen_trace.total_cost_usd,
            ...
        ))

        if eval_result.score < 0.6:  # Configurable threshold
            logger.warning(
                f"Low quality output for {behaviour.name}: "
                f"{eval_result.score}"
            )
            # Optionally: retry, flag for human review, or continue

    # 3. Post-pipeline: Maven build gate (existing)
```

### Gate Thresholds (configurable)

```yaml
# eval_config.yaml
inline_gates:
  schema_validation:
    threshold: 1.0       # Must pass — binary
    action: fail          # Block pipeline

  faithfulness_judge:
    threshold: 0.6        # 3/5 minimum
    action: warn          # Log warning, continue
    retry_on_fail: false  # Could enable retry later

  trajectory:                # NEW — from trace validation
    threshold: 0.7           # Allow minor overruns
    action: warn             # Log warning, continue
    # Per-stage baselines defined in TRAJECTORY_BASELINES

  cost:                      # NEW — from trace validation
    threshold: 0.7           # Allow ~30% buffer over baseline
    action: warn             # Log warning, continue
    # Per-stage baselines defined in COST_BASELINES

  maven_build:
    threshold: 1.0        # Must compile
    action: fail          # Block PR submission
```

---

## Package Structure in Shared Lib

```
autobots-devtools-shared-lib/
└── src/autobots_devtools_shared_lib/
    └── dynagent/
        └── eval/
            ├── __init__.py           # Public API exports
            ├── models.py             # EvalResult, EvalScore, TraceData dataclasses
            ├── runner.py             # EvalRunner
            ├── dataset.py            # Dataset loading from YAML
            ├── evaluators/
            │   ├── __init__.py
            │   ├── schema.py         # schema_evaluator
            │   ├── completeness.py   # completeness_evaluator
            │   ├── llm_judge.py      # faithfulness_evaluator
            │   ├── compilation.py    # maven_build_evaluator
            │   ├── trajectory.py     # trajectory_evaluator + TraceData (from trace validation)
            │   └── cost.py           # cost_evaluator (from trace validation)
            └── backend/
                ├── __init__.py       # get_eval_backend() factory
                ├── base.py           # EvalBackend ABC
                ├── langfuse_adapter.py
                ├── phoenix_adapter.py
                └── file_adapter.py
```

---

## Developer Workflow

### During Development (offline)

```bash
# 1. Edit a prompt
vim agent_configs/nurture/prompts/behaviour-java.md

# 2. Run eval against dataset
make eval STAGE=behaviour-java
# → Invokes EvalRunner for behaviour-java stage
# → Scores logged to file backend (local)
# → Prints comparison vs last run

# 3. Run full eval
make eval
# → All stages evaluated
# → Summary table printed

# 4. Compare versions
make eval-compare V1=abc123 V2=def456
# → Side-by-side score comparison
```

### On PR (CI)

```yaml
# .github/workflows/eval.yml (conceptual)
on:
  pull_request:
    paths:
      - 'agent_configs/nurture/prompts/**'
      - 'agent_configs/nurture/schemas/**'

jobs:
  prompt-eval:
    steps:
      - run: make eval
      - run: make eval-compare V1=${{ github.event.before }} V2=${{ github.sha }}
      # Posts score comparison as PR comment
```

### Makefile Targets

```makefile
# In autobots-agents-mer/Makefile
eval:                              ## Run prompt evaluation
	EVAL_BACKEND=file python -m autobots_agents_mer.eval.cli \
		--dataset eval_datasets/nurture/datasets.yaml \
		$(if $(STAGE),--stage $(STAGE),)

eval-compare:                      ## Compare two prompt versions
	python -m autobots_agents_mer.eval.cli compare \
		--v1 $(V1) --v2 $(V2)
```

---

## Evaluation Matrix (per stage)

| Stage | Quality Evaluators | Efficiency Evaluators | Inline Gate | Offline Eval |
|---|---|---|---|---|
| `model-list-extractor` | Schema + Completeness | Trajectory + Cost | Schema (block), Trajectory (warn) | All |
| `model-oas-generator` | LLM Judge (faithfulness) | Trajectory + Cost | LLM Judge (warn), Cost (warn) | All |
| `behaviour-list-extractor` | Schema + Completeness | Trajectory + Cost | Schema (block), Trajectory (warn) | All |
| `behaviour-md-generator` | LLM Judge | Trajectory + Cost | LLM Judge (warn) | All |
| `behaviour-java` | LLM Judge + Compilation | Trajectory + Cost | LLM Judge (warn), Cost (warn) | All |
| `scenario-list-extractor` | Schema + Completeness | Trajectory + Cost | Schema (block), Trajectory (warn) | All |
| `scenario-md-generator` | LLM Judge | Trajectory + Cost | LLM Judge (warn) | All |
| `scenario-feature-generator` | LLM Judge | Trajectory + Cost | LLM Judge (warn) | All |
| End-to-end | Maven Build | — | Maven Build (block) | Maven Build |

---

## Migration Path: Langfuse → Phoenix

When you're ready to switch:

1. Implement `PhoenixEvalBackend` (the adapter)
2. Set `EVAL_BACKEND=phoenix` in env
3. Done. All evaluators, datasets, and runner logic remain unchanged.

What changes: where scores are stored and how you visualize comparisons.
What doesn't change: evaluators, datasets, runner, inline gates, CI pipeline.

---

## Implementation Order

1. **Phase 1 — Foundation** (shared-lib)
   - `EvalResult`, `EvalScore`, `TraceData` models
   - `EvalBackend` ABC + `FileEvalBackend`
   - `schema_evaluator` and `completeness_evaluator`
   - `EvalRunner` (basic — dataset loading + single agent invocation)

2. **Phase 2 — Efficiency Evaluators** (shared-lib, from trace validation)
   - `trajectory_evaluator` with `TraceData` extraction from Langfuse traces
   - `cost_evaluator` with token/cost baselines
   - Baseline calibration from existing production traces
   - `TraceData.from_langfuse_trace()` parser

3. **Phase 3 — LLM Judge** (shared-lib)
   - `faithfulness_evaluator` with judge prompt
   - Judge prompt iteration (use the eval system to eval the judge!)

4. **Phase 4 — Offline Harness** (MER repo)
   - Curate 1–3 eval datasets
   - `make eval` target + CLI
   - `LangfuseEvalBackend` adapter
   - Baseline capture script: run existing traces through trajectory/cost evaluators to establish initial baselines

5. **Phase 5 — Inline Gates** (MER repo)
   - Wire schema gates into list extractor orchestrators
   - Wire trajectory + cost gates into all orchestrators
   - Wire LLM judge gates into generator orchestrators
   - Configurable thresholds via `eval_config.yaml`
   - `TraceData.from_agent_callback()` for inline capture

6. **Phase 6 — CI Integration**
   - PR workflow that runs eval on prompt changes
   - Score comparison posted as PR comment
   - Trajectory + cost regression detection in PR checks
