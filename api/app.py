import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.audit import ApiAuditMiddleware
from api.config import API_CONFIG
from api.database_init import initialize_database
from api.errors import install_error_handlers
from api.routers import ingots, members, meta, scores
from ironforgedbot.logging_config import get_logger_instance

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_logger_instance()
    if API_CONFIG.API_ENABLED:
        await initialize_database()
    yield


def create_app() -> FastAPI:
    get_logger_instance()

    app = FastAPI(
        title="IronForgedBot API",
        version=API_CONFIG.api_version,
        docs_url="/docs" if API_CONFIG.API_DOCS_ENABLED else None,
        redoc_url=None,
        openapi_url="/openapi.json" if API_CONFIG.API_DOCS_ENABLED else None,
        lifespan=lifespan,
    )

    app.add_middleware(ApiAuditMiddleware)
    install_error_handlers(app)

    if API_CONFIG.API_CORS_ORIGINS:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=API_CONFIG.API_CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(meta.router)
    app.include_router(members.router)
    app.include_router(ingots.router)
    app.include_router(scores.router)

    return app


app = create_app()
