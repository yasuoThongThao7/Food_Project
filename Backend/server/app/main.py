from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.core.errors import (
    ApiError,
    api_error_handler,
    http_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from app.routers.api import router

app = FastAPI(title="Da Nang Food Guide API", redirect_slashes=False)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(StarletteHTTPException, http_error_handler)
app.add_exception_handler(400, http_error_handler)
app.add_exception_handler(401, http_error_handler)
app.add_exception_handler(403, http_error_handler)
app.add_exception_handler(404, http_error_handler)
app.add_exception_handler(409, http_error_handler)
app.add_exception_handler(422, http_error_handler)
app.add_exception_handler(429, http_error_handler)
app.add_exception_handler(503, http_error_handler)
app.add_exception_handler(Exception, unexpected_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.include_router(router)
