from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


async def handle_value_error(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ValueError, handle_value_error)

