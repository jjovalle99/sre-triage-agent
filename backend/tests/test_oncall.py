import pytest

from app.oncall import get_oncall_engineer


def test_returns_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ON_CALL_ENGINEER", "Alice")
    assert get_oncall_engineer() == "Alice"


def test_returns_default_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ON_CALL_ENGINEER", raising=False)
    assert get_oncall_engineer() == "On-Call Engineer"
