from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .config import get_settings
from .logging_utils import configure_logging, get_logger
from .middleware import request_context_middleware
from .routes import PredictorManagerRegistry, router
from .security import ContainerWhitelistMiddleware


settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


# Custom key function for rate limiting by container
def get_container_identifier(request: Request) -> str:
    """Get container name or IP for rate limiting."""
    # Try to get container name from header
    container_name = request.headers.get("X-Container-Name")
    if container_name:
        return container_name
    # Fall back to IP address
    return get_remote_address(request)


# Initialize rate limiter
limiter = Limiter(
    key_func=get_container_identifier,
    enabled=settings.rate_limit_enabled,
)

app = FastAPI(title=settings.app_name)

# Add security middleware
app.add_middleware(ContainerWhitelistMiddleware, settings=settings)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add request context middleware
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
