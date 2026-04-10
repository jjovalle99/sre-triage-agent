from collections import defaultdict
from threading import Lock
from typing import TypedDict

_lock = Lock()
_usage: dict[str, dict[str, int]] = defaultdict(lambda: {"prompt_tokens": 0, "completion_tokens": 0})

_COST_PER_M_TOKENS: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6": (3.00, 15.00),
    "mistral-medium-latest": (0.40, 2.00),
    "mistral-small-latest": (0.15, 0.60),
    "voxtral-mini-latest": (0.04, 0.04),
    "mistral-moderation-2603": (0.0, 0.0),
}


class ModelUsage(TypedDict):
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float


class TokenSummary(TypedDict):
    by_model: dict[str, ModelUsage]
    total_prompt_tokens: int
    total_completion_tokens: int
    estimated_cost_usd: float


def record_usage(*, model: str, prompt_tokens: int, completion_tokens: int) -> None:
    with _lock:
        _usage[model]["prompt_tokens"] += prompt_tokens
        _usage[model]["completion_tokens"] += completion_tokens


def get_summary() -> TokenSummary:
    with _lock:
        by_model: dict[str, ModelUsage] = {}
        total_prompt = 0
        total_completion = 0
        total_cost = 0.0

        for model, counts in _usage.items():
            p = counts["prompt_tokens"]
            c = counts["completion_tokens"]
            total_prompt += p
            total_completion += c

            input_rate, output_rate = _COST_PER_M_TOKENS.get(model, (1.0, 1.0))
            cost = (p / 1_000_000 * input_rate) + (c / 1_000_000 * output_rate)
            total_cost += cost

            by_model[model] = ModelUsage(
                prompt_tokens=p,
                completion_tokens=c,
                estimated_cost_usd=round(cost, 6),
            )

        return TokenSummary(
            by_model=by_model,
            total_prompt_tokens=total_prompt,
            total_completion_tokens=total_completion,
            estimated_cost_usd=round(total_cost, 6),
        )


def reset() -> None:
    with _lock:
        _usage.clear()
