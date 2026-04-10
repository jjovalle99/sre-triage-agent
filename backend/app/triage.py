import functools
import logging
import os
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, query
from claude_agent_sdk.types import ToolUseBlock
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes
from opentelemetry import trace

from app.prompts import wrap_user_input
from app.token_tracker import record_usage

_tracer = trace.get_tracer(__name__)

_log = logging.getLogger(__name__)

_ESHOP_DIR = os.environ.get("ESHOP_DIR", "/app/eshop")
_ESHOP_MAP_PATH = os.environ.get("ESHOP_MAP_PATH", "/app/eshop-map.md")
_ESHOP_README_PATH = os.environ.get("ESHOP_README_PATH", "/app/eshop/README.md")


@dataclass(frozen=True)
class TriageResult:
    root_cause_hypothesis: str
    investigation_steps: list[str]
    suggested_fix: str
    relevant_files: list[str]
    blast_radius: str
    confidence: float
    severity: str = "P2"
    affected_services: list[str] = field(default_factory=list)
    duration_ms: int = 0


@dataclass(frozen=True)
class TriageEvent:
    action: str
    tool: str
    file: str | None = None


@dataclass(frozen=True)
class TriageComplete:
    result: TriageResult


_TRIAGE_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "root_cause_hypothesis": {"type": "string"},
        "investigation_steps": {"type": "array", "items": {"type": "string"}},
        "suggested_fix": {"type": "string"},
        "relevant_files": {"type": "array", "items": {"type": "string"}},
        "blast_radius": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "severity": {"type": "string", "enum": ["P0", "P1", "P2", "P3"]},
        "affected_services": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "root_cause_hypothesis",
        "investigation_steps",
        "suggested_fix",
        "relevant_files",
        "blast_radius",
        "confidence",
        "severity",
        "affected_services",
    ],
}




@functools.lru_cache(maxsize=4)
def _read_file(path: str) -> str:
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        _log.warning("Could not read %s", path)
        return ""


def _format_prior_context(ctx: dict[str, str | float] | None) -> str:
    if not ctx:
        return ""
    similarity = ctx.get("similarity", 0)
    pct = f"{float(similarity):.0%}" if similarity else "unknown"
    return f"""## Prior Incident Context
A similar incident was matched (similarity: {pct}).
Prior root cause: {ctx.get("root_cause", "unknown")}
Prior suggested fix: {ctx.get("suggested_fix", "unknown")}

TREAT THIS AS AN UNVERIFIED HYPOTHESIS, NOT A CONCLUSION.
Before adopting it, you MUST:
- Search the current codebase to confirm the pattern still exists.
- Explicitly state whether the prior root cause was confirmed or ruled out.
- If a different root cause is found, report it — do not force-fit the prior.

"""


def _build_triage_prompt(
    *,
    title: str,
    description: str,
    search_paths: list[str],
    affected_services: list[str],
    severity: str,
    category: str,
    eshop_map_path: str,
    eshop_readme_path: str,
    attachment_summaries: str = "",
    prior_context: dict[str, str | float] | None = None,
) -> str:
    eshop_map = _read_file(eshop_map_path)
    eshop_readme = _read_file(eshop_readme_path)
    paths_str = ", ".join(search_paths) if search_paths else "(all)"
    services_str = ", ".join(affected_services) if affected_services else "unknown"

    return f"""You are an expert SRE triaging an incident for the dotnet/eShop e-commerce platform.

## eShop Service Map
{eshop_map}

## eShop Architecture
{eshop_readme}

## Pre-Classification
Severity: {severity}
Category: {category}
Affected services: {services_str}

## Search Scope
Search ONLY within these directories: {paths_str}
Do not read files outside them unless you find an explicit cross-service dependency.

{_format_prior_context(prior_context)}## Your Task
1. Grep for specific symbols, error patterns, or class names within the scoped directories FIRST
2. Read only the files that Grep identifies as relevant (maximum 5 Read calls)
3. Identify the likely root cause based on the code structure and the incident description
4. Assess the blast radius — which other services could be affected
5. Provide ordered investigation steps (what to check first)
6. Suggest a concrete fix referencing specific code locations

## CRITICAL RULES
- Every file path you reference MUST exist in the codebase. Use Glob and Grep to verify.
- Do NOT guess file paths. Search first, then reference.
- Lead with Grep for specific patterns, then Read only relevant files.
- Do NOT use Glob("**/*.cs") to list all files. Always scope your searches.
- If you cannot determine root cause with confidence, say so explicitly.

## Incident Report
{wrap_user_input(title, description)}

## Attachments Analyzed
{attachment_summaries or "None"}"""


def _validate_files(files: list[str], eshop_dir: str) -> list[str]:
    resolved_base = os.path.realpath(eshop_dir)
    validated = []
    for path in files:
        full = os.path.join(eshop_dir, path.lstrip("/"))
        resolved = os.path.realpath(full)
        if not resolved.startswith(resolved_base + os.sep):
            _log.warning("Path traversal rejected: %s → %s", path, resolved)
            continue
        if not os.path.exists(resolved):
            _log.warning("Hallucinated path removed: %s", path)
            continue
        validated.append(path)
    return validated


def _emit_llm_span(model: str, usage: dict[str, int | None]) -> None:
    input_tokens = usage.get("input_tokens") or 0
    output_tokens = usage.get("output_tokens") or 0
    span = _tracer.start_span("llm.call")
    span.set_attributes({
        SpanAttributes.OPENINFERENCE_SPAN_KIND: OpenInferenceSpanKindValues.LLM.value,
        SpanAttributes.LLM_MODEL_NAME: model,
        SpanAttributes.LLM_TOKEN_COUNT_PROMPT: input_tokens,
        SpanAttributes.LLM_TOKEN_COUNT_COMPLETION: output_tokens,
        SpanAttributes.LLM_TOKEN_COUNT_TOTAL: input_tokens + output_tokens,
    })
    span.end()
    record_usage(model=model, prompt_tokens=input_tokens, completion_tokens=output_tokens)


def _tool_use_to_event(block: ToolUseBlock) -> TriageEvent:
    tool_input: dict[str, Any] = block.input
    name = block.name
    if name == "Grep":
        pattern = tool_input.get("pattern", "")
        return TriageEvent(action=f"Searching for {pattern}...", tool="Grep")
    if name == "Read":
        file_path = tool_input.get("file_path", "")
        return TriageEvent(action=f"Reading {file_path}...", tool="Read", file=file_path)
    if name == "Glob":
        pattern = tool_input.get("pattern", "")
        return TriageEvent(action=f"Listing {pattern}...", tool="Glob")
    if name == "Bash":
        command = tool_input.get("command", "")
        short = command[:80] + ("..." if len(command) > 80 else "")
        return TriageEvent(action=f"$ {short}", tool="Bash")
    return TriageEvent(action=f"Running {name}...", tool=name)


async def triage_incident(
    *,
    title: str,
    description: str,
    search_paths: list[str],
    affected_services: list[str],
    severity: str,
    category: str,
    attachment_summaries: str = "",
    prior_context: dict[str, str | float] | None = None,
    eshop_dir: str = _ESHOP_DIR,
    eshop_map_path: str = _ESHOP_MAP_PATH,
    eshop_readme_path: str = _ESHOP_README_PATH,
) -> AsyncGenerator[TriageEvent | TriageComplete, None]:
    opts = ClaudeAgentOptions(
        allowed_tools=["Read", "Glob", "Grep"],
        model="claude-sonnet-4-6",
        cwd=eshop_dir,
        env={"CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1"},
        permission_mode="bypassPermissions",
        output_format={
            "type": "json_schema",
            "schema": _TRIAGE_RESULT_SCHEMA,
        },
        max_turns=15,
    )

    prompt = _build_triage_prompt(
        title=title,
        description=description,
        search_paths=search_paths,
        affected_services=affected_services,
        severity=severity,
        category=category,
        eshop_map_path=eshop_map_path,
        eshop_readme_path=eshop_readme_path,
        attachment_summaries=attachment_summaries,
        prior_context=prior_context,
    )

    result_msg: ResultMessage | None = None
    gen = query(prompt=prompt, options=opts)
    try:
        async for message in gen:
            if isinstance(message, AssistantMessage):
                if message.usage:
                    _emit_llm_span(message.model, message.usage)
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        yield _tool_use_to_event(block)
            elif isinstance(message, ResultMessage):
                result_msg = message
    finally:
        if isinstance(gen, AsyncGenerator):
            await gen.aclose()

    if result_msg is None:
        raise RuntimeError("No ResultMessage received from Claude Agent SDK")

    if result_msg.is_error:
        errors = getattr(result_msg, "errors", None) or ["Unknown error"]
        raise RuntimeError("; ".join(errors))

    output: dict[str, Any] = result_msg.structured_output or {}
    raw_files: list[str] = output.get("relevant_files", [])
    validated_files = _validate_files(raw_files, eshop_dir)
    triage = TriageResult(
        root_cause_hypothesis=output.get("root_cause_hypothesis", ""),
        investigation_steps=output.get("investigation_steps", []),
        suggested_fix=output.get("suggested_fix", ""),
        relevant_files=validated_files,
        blast_radius=output.get("blast_radius", ""),
        confidence=output.get("confidence", 0.0),
        severity=output.get("severity", "P2"),
        affected_services=output.get("affected_services", []),
        duration_ms=getattr(result_msg, "duration_ms", 0),
    )
    yield TriageComplete(result=triage)
