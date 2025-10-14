import time
import uuid
from typing import Callable

from fastapi import Request, Response

from .logging_utils import REQUEST_ID_HEADER, get_logger


logger = get_logger(__name__)


async def request_context_middleware(request: Request, call_next: Callable) -> Response:
    start_time = time.perf_counter()

    request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid.uuid4()))
    request.state.request_id = request_id

    response = await call_next(request)

    process_time = (time.perf_counter() - start_time) * 1000

    response.headers[REQUEST_ID_HEADER] = request_id

    logger.info(
        "request completed",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "latency_ms": round(process_time, 2),
        },
    )

    return response
