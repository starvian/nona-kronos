from fastapi import FastAPI

from .config import get_settings
from .logging_utils import configure_logging, get_logger
from .middleware import request_context_middleware
from .routes import PredictorManagerRegistry, router


settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)

app = FastAPI(title=settings.app_name)
app.middleware("http")(request_context_middleware)
app.include_router(router)


@app.on_event("startup")
async def startup_event() -> None:
    manager = PredictorManagerRegistry.get(settings)
    if not manager.ready:
        logger.info("initializing predictor manager")
        manager.load()
        logger.info("predictor manager ready")


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"message": settings.app_name}
