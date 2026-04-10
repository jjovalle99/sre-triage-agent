from app.mistral import get_mistral_client
from mistralai.client.utils.retries import RetryConfig


def test_mistral_client_has_retry_config() -> None:
    get_mistral_client.cache_clear()
    client = get_mistral_client()
    assert isinstance(client.sdk_configuration.retry_config, RetryConfig)
    get_mistral_client.cache_clear()
