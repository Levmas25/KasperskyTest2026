from fastapi import FastAPI

from app.api.handlers import register_exception_handlers
from app.api.public.health.router import router as health_public_router
from app.api.public.report.router import router as report_public_router
from app.infra.logging_setup import configure_logging


configure_logging()
app = FastAPI()

register_exception_handlers(app)
app.include_router(health_public_router)
app.include_router(report_public_router)
