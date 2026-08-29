"""Shared error envelope — `{"error": {"code": ..., "message": ...}}` per
Plan Part 15 (e.g. its own worked example uses this exact shape for
GEOFENCE_DENIED). Any domain exception that should reach the client as a
structured error subclasses AppError; register_exception_handlers() wires
the single handler that renders all of them the same way.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code: int = 400

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )
