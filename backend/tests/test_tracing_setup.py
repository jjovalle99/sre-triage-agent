from unittest.mock import AsyncMock, patch

from asgi_lifespan import LifespanManager

from app.main import app


async def test_lifespan_calls_register_when_endpoint_set() -> None:
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.main.register") as mock_register,
        patch("app.main.setup_logging") as mock_setup,
        patch("app.main.httpx.AsyncClient", return_value=mock_client),
        patch("app.main.init_db", new=AsyncMock()),
        patch.dict("os.environ", {"PHOENIX_COLLECTOR_ENDPOINT": "http://phoenix:6006"}),
    ):
        async with LifespanManager(app):
            pass

    mock_register.assert_called_once()
    call_kwargs = mock_register.call_args.kwargs
    assert call_kwargs["project_name"] == "sre-triage"
    assert call_kwargs["endpoint"] == "http://phoenix:6006"
    assert call_kwargs["batch"] is True
    assert call_kwargs["verbose"] is False
    mock_setup.assert_called_once()


async def test_lifespan_skips_register_when_no_endpoint() -> None:
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.main.register") as mock_register,
        patch("app.main.setup_logging"),
        patch("app.main.httpx.AsyncClient", return_value=mock_client),
        patch("app.main.init_db", new=AsyncMock()),
        patch.dict("os.environ", {"PHOENIX_COLLECTOR_ENDPOINT": ""}, clear=False),
    ):
        async with LifespanManager(app):
            pass

    mock_register.assert_not_called()
