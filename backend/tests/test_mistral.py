from app.mistral import get_mistral_client


def test_get_mistral_client_returns_client(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key-123")
    get_mistral_client.cache_clear()
    client = get_mistral_client()
    assert client is not None
    get_mistral_client.cache_clear()
