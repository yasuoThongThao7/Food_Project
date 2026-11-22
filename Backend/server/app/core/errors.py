from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"ok": False, "error": {"code": code, "message": message}}
    )


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message)


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    mapping = {
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        429: "RATE_LIMIT",
        503: "AI_UNAVAILABLE",
    }
    return error_response(
        exc.status_code, mapping.get(exc.status_code, "VALIDATION"), str(exc.detail)
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(400, "VALIDATION", "Dữ liệu không hợp lệ")


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return error_response(500, "INTERNAL", "Đã xảy ra lỗi máy chủ")
