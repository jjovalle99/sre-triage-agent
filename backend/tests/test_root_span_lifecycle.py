from collections.abc import Callable
from unittest.mock import patch

import pytest
from opentelemetry.sdk.trace import TracerProvider

from tests.conftest import CollectingExporter, _DEFAULT_FORM

_F = _DEFAULT_FORM


async def test_root_span_ends_on_classification_crash(
    make_client: Callable,
    otel_collector: tuple[CollectingExporter, TracerProvider],
) -> None:
    exporter, provider = otel_collector

    async with make_client() as c:
        with (
            patch("app.routes.incidents._tracer", provider.get_tracer("test")),
            patch(
                "app.routes.incidents.classify_incident",
                side_effect=RuntimeError("mistral exploded"),
            ),
            pytest.raises(ExceptionGroup),
        ):
            await c.post("/api/incidents", data=_F)

    provider.force_flush()
    root_spans = [s for s in exporter.spans if s.name == "incident.pipeline"]
    assert len(root_spans) == 1, f"Expected root span to be ended; got {len(root_spans)}"


async def test_root_span_ends_on_happy_path(
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
