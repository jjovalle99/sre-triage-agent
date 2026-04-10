from dataclasses import dataclass, field

import structlog
from mistralai.client import Mistral
from opentelemetry import trace

_log = structlog.get_logger()
_tracer = trace.get_tracer(__name__)

_JAILBREAK_THRESHOLD = 0.8
_MODEL = "mistral-moderation-2603"


@dataclass(frozen=True)
class ModerationResult:
    passed: bool
    scores: dict[str, float]
    flagged_categories: list[str] = field(default_factory=list)


async def moderate_text(
    client: Mistral,
    *,
    title: str,
    description: str,
) -> ModerationResult:
    with _tracer.start_as_current_span("mistral.moderation") as span:
        span.set_attribute("llm.provider", "mistralai")
        span.set_attribute("llm.model", _MODEL)
        try:
            response = await client.classifiers.moderate_chat_async(
                model=_MODEL,
                inputs=[{"role": "user", "content": f"{title}\n{description}"}],
            )
            scores: dict[str, float] = dict(response.results[0].category_scores)
            flagged = [k for k, v in scores.items() if v > _JAILBREAK_THRESHOLD]
            result = ModerationResult(
                passed=len(flagged) == 0,
                scores=scores,
                flagged_categories=flagged,
            )
            span.set_attribute("moderation.passed", result.passed)
            span.set_attribute("moderation.flagged_count", len(flagged))
            return result
        except Exception:
            _log.warning("moderation_api_failed")
            span.set_attribute("moderation.error", True)
            return ModerationResult(passed=False, scores={}, flagged_categories=["error"])
