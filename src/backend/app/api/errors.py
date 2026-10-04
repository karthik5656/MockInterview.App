from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.schemas.common import ErrorResponse, ErrorDetail


class AppException(Exception):
    def __init__(self, code: str, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(code="NOT_FOUND", message=message, status_code=status.HTTP_404_NOT_FOUND)


class ConflictException(AppException):
    def __init__(self, message: str = "Resource conflict"):
        super().__init__(code="CONFLICT", message=message, status_code=status.HTTP_409_CONFLICT)


class BadInputException(AppException):
    def __init__(self, message: str = "Invalid input provided"):
        super().__init__(code="BAD_INPUT", message=message, status_code=status.HTTP_400_BAD_REQUEST)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    content = ErrorResponse(error=ErrorDetail(code=exc.code, message=exc.message)).model_dump()
    return JSONResponse(status_code=exc.status_code, content=content)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    first_error = exc.errors()[0] if exc.errors() else {}
    msg = first_error.get("msg", "Validation error")
    loc = " -> ".join(str(l) for l in first_error.get("loc", []))
    content = ErrorResponse(
        error=ErrorDetail(code="BAD_INPUT", message=f"{loc}: {msg}" if loc else msg)
    ).model_dump()
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=content)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    content = ErrorResponse(
        error=ErrorDetail(code="INTERNAL_SERVER_ERROR", message="An unexpected error occurred.")
    ).model_dump()
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=content)