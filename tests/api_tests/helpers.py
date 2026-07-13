import os

os.environ.setdefault("ENVIRONMENT", "dev")
os.environ.setdefault("GUILD_ID", "1")
os.environ.setdefault("BOT_TOKEN", "x")
os.environ.setdefault("WOM_GROUP_ID", "1")
os.environ.setdefault("WOM_API_KEY", "x")
os.environ.setdefault("AUTOMATION_CHANNEL_ID", "1")
os.environ.setdefault("RAFFLE_CHANNEL_ID", "1")
os.environ.setdefault("INGOT_SHOP_CHANNEL_ID", "1")
os.environ.setdefault("RULES_CHANNEL_ID", "1")
os.environ.setdefault("RANKINGS_CHANNEL_ID", "1")
os.environ.setdefault("BOT_COMMANDS_CHANNEL_ID", "1")
os.environ.setdefault("BOT_CHANGELOG_CHANNEL_ID", "1")
os.environ.setdefault("CREATE_TICKET_CHANNEL_ID", "1")
os.environ.setdefault("DATABASE_URL", "mysql+aiomysql://test:test@localhost:3306/test")

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import ApiConsumer


def make_consumer(
    name: str = "tester",
    perms: list[str] | None = None,
    enabled: bool = True,
) -> MagicMock:
    c = MagicMock(spec=ApiConsumer)
    c.id = 1
    c.name = name
    c.perms = perms if perms is not None else []
    c.enabled = enabled
    return c


def build_test_app(include_routers: list | None = None) -> FastAPI:
    from api.audit import ApiAuditMiddleware
    from api.errors import install_error_handlers

    app = FastAPI()
    app.add_middleware(ApiAuditMiddleware)
    install_error_handlers(app)

    if include_routers:
        for r in include_routers:
            app.include_router(r)
    return app


def build_test_client(
    app: FastAPI,
    session: AsyncMock | None = None,
    consumer: MagicMock | None = None,
) -> TestClient:
    from api.deps import get_current_consumer, get_db_session

    if session is None:
        session = AsyncMock(spec=AsyncSession)
    if consumer is None:
        consumer = make_consumer()

    async def override_db():
        yield session

    async def override_consumer():
        return consumer

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_current_consumer] = override_consumer

    with patch("api.audit.db"):
        return TestClient(app)
