import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app, limiter


@pytest.mark.asyncio
async def test_rate_limit_returns_429_after_threshold() -> None:
    limiter.enabled = True
    try:
        limiter.reset()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            responses = []
            for _ in range(12):
                resp = await client.get("/health")
                responses.append(resp)

            status_codes = [r.status_code for r in responses]
            assert 429 in status_codes
    finally:
        limiter.enabled = False
