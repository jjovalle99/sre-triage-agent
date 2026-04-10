from unittest.mock import MagicMock, patch

from app.triage import triage_incident


async def test_query_generator_closed_on_cancellation() -> None:
    closed = False

    async def fake_query_gen():  # type: ignore[no-untyped-def]
        nonlocal closed
        try:
            while True:
                from claude_agent_sdk import AssistantMessage
                from claude_agent_sdk.types import ToolUseBlock

                msg = MagicMock(spec=AssistantMessage)
                tool_block = MagicMock(spec=ToolUseBlock)
                tool_block.name = "Grep"
                tool_block.input = {"pattern": "test"}
                msg.content = [tool_block]
                msg.usage = None
                msg.model = "test"
                yield msg
        finally:
            closed = True

    def fake_query(**kwargs):  # type: ignore[no-untyped-def]
        return fake_query_gen()

    with patch("app.triage.query", fake_query):
        triage_gen = triage_incident(
            title="test",
            description="test",
            search_paths=[],
            affected_services=[],
            severity="P1",
            category="payment",
        )
        async for _ in triage_gen:
            break

        await triage_gen.aclose()

    assert closed, "query() generator was not closed on cancellation"
