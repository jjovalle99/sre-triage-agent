from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.triage import TriageComplete, TriageEvent, TriageResult, triage_incident
from tests.conftest import collect_async


def _mock_result_message(structured_output: dict[str, Any]) -> MagicMock:
    from claude_agent_sdk import ResultMessage

    msg = MagicMock(spec=ResultMessage)
    msg.is_error = False
    msg.structured_output = structured_output
    msg.duration_ms = 1234
    msg.total_cost_usd = 0.04
    msg.content = []
    return msg


_VALID_TRIAGE_OUTPUT: dict[str, Any] = {
    "root_cause_hypothesis": "Payment gateway timeout due to connection pool exhaustion",
    "investigation_steps": ["Check PaymentProcessor logs", "Verify connection pool config"],
    "suggested_fix": "Increase connection pool size in appsettings.json",
    "relevant_files": ["src/PaymentProcessor/Program.cs"],
    "blast_radius": "PaymentProcessor and downstream Ordering.API",
    "confidence": 0.85,
    "severity": "P1",
    "affected_services": ["PaymentProcessor", "Ordering.API"],
}


def _make_fake_query(
    result_msg: MagicMock,
) -> tuple[Any, dict[str, Any]]:
    captured: dict[str, Any] = {}

    async def fake_query(**kwargs: Any) -> Any:
        captured.update(kwargs)
        yield result_msg

    return fake_query, captured


async def test_triage_result_dataclass_has_expected_fields() -> None:
    result = TriageResult(
        root_cause_hypothesis="test",
        investigation_steps=["step1"],
        suggested_fix="fix",
        relevant_files=["file.cs"],
        blast_radius="limited",
        confidence=0.9,
    )
    assert result.root_cause_hypothesis == "test"
    assert result.confidence == 0.9
    assert result.severity == "P2"
    assert result.affected_services == []
    assert result.duration_ms == 0


async def test_triage_incident_calls_query_with_correct_options() -> None:
    result_msg = _mock_result_message(_VALID_TRIAGE_OUTPUT)
    fake_query, captured = _make_fake_query(result_msg)

    with patch("app.triage.query", fake_query):
        items = await collect_async(
            triage_incident(
                title="Payment timeout",
                description="Checkout fails with 504",
                search_paths=["src/PaymentProcessor/"],
                affected_services=["PaymentProcessor"],
                severity="P1",
                category="payment",
                eshop_dir="/app/eshop",
            )
        )

    assert "prompt" in captured
    assert "options" in captured
    opts = captured["options"]

    assert "Read" in opts.allowed_tools
    assert "Glob" in opts.allowed_tools
    assert "Grep" in opts.allowed_tools
    assert opts.model == "claude-sonnet-4-6"
    assert opts.env.get("CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS") == "1"
    assert str(opts.cwd) == "/app/eshop"
    assert opts.output_format is not None
    assert opts.output_format["type"] == "json_schema"
    assert "root_cause_hypothesis" in str(opts.output_format["schema"])

    assert len(items) == 1
    assert isinstance(items[0], TriageComplete)
    result = items[0].result
    assert result.root_cause_hypothesis == _VALID_TRIAGE_OUTPUT["root_cause_hypothesis"]
    assert result.severity == "P1"
    assert result.confidence == 0.85
    assert result.duration_ms == 1234


async def test_triage_prompt_contains_map_readme_markers_scope() -> None:
    result_msg = _mock_result_message(_VALID_TRIAGE_OUTPUT)
    fake_query, captured = _make_fake_query(result_msg)

    fake_map = "| Service | Path |\n| Basket.API | src/Basket.API/ |"
    fake_readme = "eShop is a reference .NET application"

    from app.triage import _read_file
    _read_file.cache_clear()

    with (
        patch("app.triage.query", fake_query),
        patch(
            "builtins.open",
            side_effect=lambda path, *a, **kw: __import__("io").StringIO(
                fake_map if "eshop-map" in str(path) else fake_readme
            ),
        ),
    ):
        await collect_async(
            triage_incident(
                title="Payment timeout",
                description="Checkout fails with 504",
                search_paths=["src/PaymentProcessor/"],
                affected_services=["PaymentProcessor"],
                severity="P1",
                category="payment",
                eshop_dir="/app/eshop",
            )
        )

    prompt = captured["prompt"]
    assert fake_map in prompt
    assert fake_readme in prompt
    assert "[USER_INPUT_START]" in prompt
    assert "[USER_INPUT_END]" in prompt
    assert "Checkout fails with 504" in prompt
    assert "Search ONLY within" in prompt
    assert "src/PaymentProcessor/" in prompt
    assert "P1" in prompt
    assert "payment" in prompt


async def test_tool_use_blocks_yield_triage_events() -> None:
    from claude_agent_sdk import AssistantMessage

    grep_block = MagicMock()
    grep_block.name = "Grep"
    grep_block.input = {"pattern": "PaymentException", "path": "src/PaymentProcessor/"}

    read_block = MagicMock()
    read_block.name = "Read"
    read_block.input = {"file_path": "src/PaymentProcessor/Program.cs"}

    from claude_agent_sdk.types import ToolUseBlock

    assistant_msg = MagicMock(spec=AssistantMessage)
    assistant_msg.usage = None
    assistant_msg.content = [
        MagicMock(spec=ToolUseBlock, name="Grep", input=grep_block.input),
        MagicMock(spec=ToolUseBlock, name="Read", input=read_block.input),
    ]
    assistant_msg.content[0].name = "Grep"
    assistant_msg.content[1].name = "Read"

    result_msg = _mock_result_message(_VALID_TRIAGE_OUTPUT)

    async def fake_query(**kwargs: Any) -> Any:
        yield assistant_msg
        yield result_msg

    with patch("app.triage.query", fake_query):
        items = await collect_async(
            triage_incident(
                title="Payment timeout",
                description="Checkout fails",
                search_paths=["src/PaymentProcessor/"],
                affected_services=["PaymentProcessor"],
                severity="P1",
                category="payment",
                eshop_dir="/app/eshop",
            )
        )

    events = [i for i in items if isinstance(i, TriageEvent)]
    completes = [i for i in items if isinstance(i, TriageComplete)]

    assert len(events) == 2
    assert events[0].tool == "Grep"
    assert "PaymentException" in events[0].action
    assert events[1].tool == "Read"
    assert "Program.cs" in events[1].action
    assert events[1].file == "src/PaymentProcessor/Program.cs"
    assert len(completes) == 1


async def test_post_triage_validates_and_strips_invalid_paths() -> None:
    output_with_bad_paths = {
        **_VALID_TRIAGE_OUTPUT,
        "relevant_files": [
            "src/PaymentProcessor/Program.cs",
            "src/FAKE/Nonexistent.cs",
            "../../etc/passwd",
        ],
    }
    result_msg = _mock_result_message(output_with_bad_paths)
    fake_query, _ = _make_fake_query(result_msg)

    def fake_realpath(path: str) -> str:
        if "../../" in path:
            return "/etc/passwd"
        return path

    def fake_exists(path: str) -> bool:
        return "Program.cs" in path

    with (
        patch("app.triage.query", fake_query),
        patch("app.triage.os.path.realpath", side_effect=fake_realpath),
        patch("app.triage.os.path.exists", side_effect=fake_exists),
    ):
        items = await collect_async(
            triage_incident(
                title="t",
                description="d",
                search_paths=["src/PaymentProcessor/"],
                affected_services=["PaymentProcessor"],
                severity="P1",
                category="payment",
                eshop_dir="/app/eshop",
            )
        )

    complete = next(i for i in items if isinstance(i, TriageComplete))
    assert complete.result.relevant_files == ["src/PaymentProcessor/Program.cs"]


async def test_query_error_raises_runtime_error() -> None:
    from claude_agent_sdk import ResultMessage

    error_msg = MagicMock(spec=ResultMessage)
    error_msg.is_error = True
    error_msg.errors = ["CLI process exited unexpectedly"]
    error_msg.content = []
    error_msg.structured_output = None

    async def fake_query(**kwargs: Any) -> Any:
        yield error_msg

    with (
        patch("app.triage.query", fake_query),
        pytest.raises(RuntimeError, match="CLI process exited"),
    ):
        await collect_async(
            triage_incident(
                title="t",
                description="d",
                search_paths=[],
                affected_services=[],
                severity="P2",
                category="other",
                eshop_dir="/app/eshop",
            )
        )
