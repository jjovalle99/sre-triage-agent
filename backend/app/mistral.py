import os
from functools import lru_cache

from mistralai.client import Mistral
from mistralai.client.utils.retries import BackoffStrategy, RetryConfig

_RETRY = RetryConfig(
    strategy="backoff",
    backoff=BackoffStrategy(
        initial_interval=500,
        max_interval=10000,
        exponent=1.5,
        max_elapsed_time=30000,
    ),
    retry_connection_errors=True,
)


@lru_cache(maxsize=1)
def get_mistral_client() -> Mistral:
    return Mistral(api_key=os.environ["MISTRAL_API_KEY"], retry_config=_RETRY)
