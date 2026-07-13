import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.schemas.common import ApiError, ApiErrorResponse, ResponseMeta
from ironforgedcore.services.member_service import MemberNotFoundException

logger = logging.getLogger(__name__)


_STATUS_CODE_TO_ERROR: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
}


def _code_for(status_code: int) -> str:
    return _STATUS_CODE_TO_ERROR.get(status_code, "internal_error")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Error"
        body = ApiErrorResponse(
            error=ApiError(code=_code_for(exc.status_code), message=message),
            meta=ResponseMeta(request_id=request.state.request_id),
        )
        headers = getattr(exc, "headers", None)
        return JSONResponse(
            status_code=exc.status_code,
            content=body.model_dump(mode="json"),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        body = ApiErrorResponse(
            error=ApiError(
                code="validation_error",
                message="Invalid request parameters",
            ),
            meta=ResponseMeta(request_id=request.state.request_id),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=body.model_dump(mode="json"),
        )

    @app.exception_handler(MemberNotFoundException)
    async def member_not_found_handler(
        request: Request, exc: MemberNotFoundException
    ) -> JSONResponse:
        body = ApiErrorResponse(
            error=ApiError(code="not_found", message=str(exc)),
            meta=ResponseMeta(request_id=request.state.request_id),
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=body.model_dump(mode="json"),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled API exception", exc_info=exc)
        body = ApiErrorResponse(
            error=ApiError(code="internal_error", message="Internal server error"),
            meta=ResponseMeta(request_id=request.state.request_id),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=body.model_dump(mode="json"),
        )
