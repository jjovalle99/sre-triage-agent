import structlog

from app.logging import setup_logging, add_otel_context


async def test_setup_logging_configures_structlog() -> None:
    setup_logging(json_logs=True)
    log = structlog.get_logger()
    assert log is not None


async def test_add_otel_context_without_active_span() -> None:
    event_dict: dict[str, object] = {"event": "test"}
    result = add_otel_context(None, "", event_dict)
    assert "trace_id" not in result


async def test_add_otel_context_with_active_span() -> None:
    from opentelemetry.sdk.trace import TracerProvider

    provider = TracerProvider()
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("test-span") as span:
        ctx = span.get_span_context()
        event_dict: dict[str, object] = {"event": "test"}
        result = add_otel_context(None, "", event_dict)
        assert result["trace_id"] == format(ctx.trace_id, "032x")
        assert result["span_id"] == format(ctx.span_id, "016x")
    provider.shutdown()
