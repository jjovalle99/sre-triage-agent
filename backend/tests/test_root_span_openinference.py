from collections.abc import Callable
from unittest.mock import patch

import pytest
from opentelemetry.sdk.trace import TracerProvider

from app.moderation import ModerationResult
from tests.conftest import CollectingExporter, _DEFAULT_FORM

_F = _DEFAULT_FORM


async def test_root_span_has_chain_kind(
    make_client: Callable,
    otel_collector: tuple[CollectingExporter, TracerProvider],
) -> None:
    exporter, provider = otel_collector

    with patch("app.routes.incidents._tracer", provider.get_tracer("test")):
        async with make_client() as c:
            resp = await c.post("/api/incidents", data=_F)
            assert resp.status_code == 200

    provider.force_flush()
    root_spans = [s for s in exporter.spans if s.name == "incident.pipeline"]
    assert len(root_spans) == 1
    attrs = dict(root_spans[0].attributes or {})
    assert attrs["openinference.span.kind"] == "CHAIN"


async def test_root_span_has_input_attributes(
    make_client: Callable,
    otel_collector: tuple[CollectingExporter, TracerProvider],
) -> None:
    exporter, provider = otel_collector

    with patch("app.routes.incidents._tracer", provider.get_tracer("test")):
        async with make_client() as c:
            resp = await c.post("/api/incidents", data=_F)
            assert resp.status_code == 200

    provider.force_flush()
    root_spans = [s for s in exporter.spans if s.name == "incident.pipeline"]
    assert len(root_spans) == 1
    attrs = dict(root_spans[0].attributes or {})
    import json

    input_val = json.loads(attrs["input.value"])
    assert input_val["title"] == _F["title"]
    assert input_val["description"] == _F["description"]
    assert attrs["input.mime_type"] == "application/json"


async def test_root_span_has_output_and_ok_status(
    make_client: Callable,
    otel_collector: tuple[CollectingExporter, TracerProvider],
) -> None:
    exporter, provider = otel_collector

    with patch("app.routes.incidents._tracer", provider.get_tracer("test")):
        async with make_client() as c:
            resp = await c.post("/api/incidents", data=_F)
            assert resp.status_code == 200

    provider.force_flush()
    root_spans = [s for s in exporter.spans if s.name == "incident.pipeline"]
    assert len(root_spans) == 1
    span = root_spans[0]
    attrs = dict(span.attributes or {})
    import json

    output_val = json.loads(attrs["output.value"])
    assert output_val["title"] == _F["title"]
    assert attrs["output.mime_type"] == "application/json"

    from opentelemetry.trace import StatusCode

    assert span.status.status_code == StatusCode.OK
    assert attrs["pipeline.outcome"] == "success"


async def test_root_span_has_error_status_on_failure(
    make_client: Callable,
    otel_collector: tuple[CollectingExporter, TracerProvider],
) -> None:
    exporter, provider = otel_collector

    async with make_client() as c:
        with (
            patch("app.routes.incidents._tracer", provider.get_tracer("test")),
            patch(
                "app.routes.incidents.classify_incident",
                side_effect=RuntimeError("boom"),
            ),
            pytest.raises(ExceptionGroup),
        ):
            await c.post("/api/incidents", data=_F)

    provider.force_flush()
    root_spans = [s for s in exporter.spans if s.name == "incident.pipeline"]
    assert len(root_spans) == 1
    span = root_spans[0]

    from opentelemetry.trace import StatusCode

    assert span.status.status_code == StatusCode.ERROR
    assert "boom" in (span.status.description or "")


async def test_root_span_partial_failure_on_triage_error(
    make_client: Callable,
    otel_collector: tuple[CollectingExporter, TracerProvider],
) -> None:
    exporter, provider = otel_collector

    with patch("app.routes.incidents._tracer", provider.get_tracer("test")):
        async with make_client(triage=RuntimeError("agent crashed")) as c:
            resp = await c.post("/api/incidents", data=_F)
            assert resp.status_code == 200

    provider.force_flush()
    root_spans = [s for s in exporter.spans if s.name == "incident.pipeline"]
    assert len(root_spans) == 1
    span = root_spans[0]
    attrs = dict(span.attributes or {})

    from opentelemetry.trace import StatusCode

    assert span.status.status_code == StatusCode.OK
    assert attrs["pipeline.outcome"] == "partial_failure"

    event_names = [e.name for e in span.events]
    assert "stage_failed" in event_names
    failed_event = next(e for e in span.events if e.name == "stage_failed")
    assert failed_event.attributes is not None
    assert failed_event.attributes["stage"] == "triage"


async def test_root_span_on_moderation_block(
    make_client: Callable,
    otel_collector: tuple[CollectingExporter, TracerProvider],
) -> None:
    exporter, provider = otel_collector
    blocked_mod = ModerationResult(passed=False, scores={}, flagged_categories=["error"])

    with patch("app.routes.incidents._tracer", provider.get_tracer("test")):
        async with make_client(mod=blocked_mod) as c:
            resp = await c.post("/api/incidents", data=_F)
            assert resp.status_code == 200

    provider.force_flush()
    root_spans = [s for s in exporter.spans if s.name == "incident.pipeline"]
    assert len(root_spans) == 1
    span = root_spans[0]
    attrs = dict(span.attributes or {})
    import json

    from opentelemetry.trace import StatusCode

    assert span.status.status_code == StatusCode.OK
    assert attrs["pipeline.outcome"] == "blocked"
    output_val = json.loads(attrs["output.value"])
    assert output_val["status"] == "triage_failed"
