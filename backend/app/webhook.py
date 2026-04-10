import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any

_MAX_AGE_S = 60
_RESOLVED_TYPES = frozenset({"completed", "cancelled"})


class InvalidSignature(Exception):
    pass


class ReplayedRequest(Exception):
    pass


def verify_signature(*, body: bytes, signature: str, secret: str) -> None:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise InvalidSignature


def check_replay(webhook_timestamp_ms: int) -> None:
    now_ms = int(time.time() * 1000)
    age_s = abs(now_ms - webhook_timestamp_ms) / 1000
    if age_s > _MAX_AGE_S:
        raise ReplayedRequest


@dataclass(frozen=True)
class ResolutionInfo:
    identifier: str
    resolver_name: str
    state_type: str


def parse_resolution(payload: dict[str, Any]) -> ResolutionInfo | None:
    if payload.get("action") != "update" or payload.get("type") != "Issue":
        return None

    data = payload.get("data", {})
    state = data.get("state")
    if not isinstance(state, dict):
        return None

    state_type = state.get("type", "")
    if state_type not in _RESOLVED_TYPES:
        return None

    if "updatedFrom" not in payload or "stateId" not in payload.get("updatedFrom", {}):
        return None

    actor = payload.get("actor", {})
    return ResolutionInfo(
        identifier=data.get("identifier", ""),
        resolver_name=actor.get("name", "Unknown"),
        state_type=state_type,
    )
