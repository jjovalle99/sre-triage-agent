import json
import logging
from dataclasses import dataclass, field

from mistralai.client import Mistral

from app.prompts import wrap_user_input
from mistralai.client.errors import SDKError
from mistralai.client.models.guardrailconfig import GuardrailConfig
from mistralai.client.models.moderationllmv2config import ModerationLlmv2Config
from mistralai.client.models.moderationllmv2categorythresholds import (
    ModerationLlmv2CategoryThresholds,
)

_log = logging.getLogger(__name__)

_MODEL = "mistral-medium-latest"
_JAILBREAK_THRESHOLD = 0.8

_GUARDRAILS = [
    GuardrailConfig(
        moderation_llm_v2=ModerationLlmv2Config(
            custom_category_thresholds=ModerationLlmv2CategoryThresholds(
                jailbreaking=_JAILBREAK_THRESHOLD,
            ),
            action="block",
        )
    )
]

_SYSTEM_PROMPT = """\
You are an SRE triage classifier for an e-commerce platform (dotnet/eShop).
Given an incident report, output a JSON object with these exact fields:
- severity: one of P0, P1, P2, P3
- category: one of payment, catalog, orders, auth, infrastructure, other
- affected_services: list of service names (e.g. ["Basket.API", "PaymentProcessor"])
- search_paths: list of source paths to investigate (e.g. ["src/PaymentProcessor/"])
- urgency_reasoning: one sentence explaining the severity choice
- requires_deep_analysis: boolean, true if codebase investigation is needed"""


@dataclass(frozen=True)
class ClassificationResult:
    severity: str
    category: str
    affected_services: list[str] = field(default_factory=list)
    search_paths: list[str] = field(default_factory=list)
    urgency_reasoning: str = ""
    requires_deep_analysis: bool = False
    guardrails_blocked: bool = False


def _build_prompt(title: str, description: str) -> str:
    return f"""{_SYSTEM_PROMPT}

{wrap_user_input(title, description)}"""


def _fallback_result(*, guardrails_blocked: bool = False) -> ClassificationResult:
    return ClassificationResult(
        severity="P2",
        category="other",
        guardrails_blocked=guardrails_blocked,
    )


_LLM_FIELDS = frozenset(
    f.name
    for f in __import__("dataclasses").fields(ClassificationResult)
    if f.name != "guardrails_blocked"
)


async def classify_incident(
    client: Mistral, *, title: str, description: str
) -> ClassificationResult:
    """Classify an incident via Mistral Medium with inline guardrails."""
    prompt = _build_prompt(title, description)
    try:
        response = await client.chat.complete_async(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            guardrails=_GUARDRAILS,
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        return ClassificationResult(
            **{k: data[k] for k in _LLM_FIELDS if k in data}
        )
    except SDKError as exc:
        if exc.raw_response.status_code == 403:
            _log.warning("Classification blocked by guardrails")
            return _fallback_result(guardrails_blocked=True)
        _log.warning("Classification SDK error: %s", exc)
        return _fallback_result()
    except Exception:
        _log.warning("Classification failed", exc_info=True)
        return _fallback_result()
