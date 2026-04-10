import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from opentelemetry import trace

_tracer = trace.get_tracer(__name__)
_log = structlog.get_logger()


@asynccontextmanager
async def stage_span(
    stage: str, *, model: str = ""
) -> AsyncIterator[dict[str, object]]:
    extras: dict[str, object] = {}
    start = time.monotonic()
    error_msg: str | None = None
    with _tracer.start_as_current_span(f"pipeline.{stage}") as span:
        span.set_attribute("pipeline.stage", stage)
        try:
            yield extras
        except Exception as exc:
            error_msg = str(exc)
            span.set_attribute("error", True)
            span.set_attribute("error.message", error_msg)
            raise
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            kwargs: dict[str, object] = {
                "stage": stage,
                "duration_ms": duration_ms,
                "model": model,
                **extras,
            }
            if error_msg is not None:
                kwargs["error"] = error_msg
            _log.info("stage_complete", **kwargs)
