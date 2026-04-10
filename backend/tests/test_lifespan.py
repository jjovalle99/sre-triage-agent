from asgi_lifespan import LifespanManager

from app.main import app


async def test_app_boots():
    async with LifespanManager(app):
        pass
