import hashlib
import hmac
import time

import pytest

from app.webhook import InvalidSignature, ReplayedRequest, verify_signature


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class TestReplayProtection:
    def test_recent_timestamp_passes(self):
        from app.webhook import check_replay

        now_ms = int(time.time() * 1000)
        check_replay(now_ms)

    def test_old_timestamp_raises(self):
        from app.webhook import check_replay

        old_ms = int((time.time() - 120) * 1000)
        with pytest.raises(ReplayedRequest):
            check_replay(old_ms)

    def test_future_timestamp_raises(self):
        from app.webhook import check_replay

        future_ms = int((time.time() + 120) * 1000)
        with pytest.raises(ReplayedRequest):
            check_replay(future_ms)


class TestParseResolution:
    def test_completed_issue_returns_resolution(self):
        from app.webhook import ResolutionInfo, parse_resolution

        payload = {
            "action": "update",
            "type": "Issue",
            "actor": {"name": "Alice", "email": "alice@co.com"},
            "data": {
                "identifier": "ENG-42",
                "state": {"type": "completed", "name": "Done"},
            },
            "updatedFrom": {"stateId": "old-state-id"},
            "webhookTimestamp": int(time.time() * 1000),
        }
        result = parse_resolution(payload)
        assert isinstance(result, ResolutionInfo)
        assert result.identifier == "ENG-42"
        assert result.resolver_name == "Alice"
        assert result.state_type == "completed"

    def test_cancelled_issue_returns_resolution(self):
        from app.webhook import parse_resolution

        payload = {
            "action": "update",
            "type": "Issue",
            "actor": {"name": "Bob"},
            "data": {
                "identifier": "ENG-99",
                "state": {"type": "cancelled", "name": "Canceled"},
            },
            "updatedFrom": {"stateId": "old-state-id"},
        }
        result = parse_resolution(payload)
        assert result is not None
        assert result.state_type == "cancelled"

    def test_non_update_action_returns_none(self):
        from app.webhook import parse_resolution

        payload = {
            "action": "create",
            "type": "Issue",
            "data": {"state": {"type": "completed"}},
        }
        assert parse_resolution(payload) is None

    def test_non_issue_type_returns_none(self):
        from app.webhook import parse_resolution

        payload = {
            "action": "update",
            "type": "Comment",
            "data": {"state": {"type": "completed"}},
        }
        assert parse_resolution(payload) is None

    def test_started_state_returns_none(self):
        from app.webhook import parse_resolution

        payload = {
            "action": "update",
            "type": "Issue",
            "data": {
                "identifier": "ENG-1",
                "state": {"type": "started", "name": "In Progress"},
            },
            "updatedFrom": {"stateId": "old-state-id"},
        }
        assert parse_resolution(payload) is None

    def test_missing_updated_from_returns_none(self):
        from app.webhook import parse_resolution

        payload = {
            "action": "update",
            "type": "Issue",
            "data": {
                "identifier": "ENG-1",
                "state": {"type": "completed"},
            },
        }
        assert parse_resolution(payload) is None

    def test_missing_state_object_returns_none(self):
        from app.webhook import parse_resolution

        payload = {
            "action": "update",
            "type": "Issue",
            "data": {"identifier": "ENG-1", "stateId": "some-id"},
            "updatedFrom": {"stateId": "old-state-id"},
        }
        assert parse_resolution(payload) is None


class TestVerifySignature:
    def test_valid_signature_passes(self):
        secret = "whsec_test123"
        body = b'{"action":"update"}'
        sig = _sign(body, secret)
        verify_signature(body=body, signature=sig, secret=secret)

    def test_invalid_signature_raises(self):
        secret = "whsec_test123"
        body = b'{"action":"update"}'
        with pytest.raises(InvalidSignature):
            verify_signature(body=body, signature="bad", secret=secret)

    def test_tampered_body_raises(self):
        secret = "whsec_test123"
        body = b'{"action":"update"}'
        sig = _sign(body, secret)
        with pytest.raises(InvalidSignature):
            verify_signature(body=b'{"action":"remove"}', signature=sig, secret=secret)
