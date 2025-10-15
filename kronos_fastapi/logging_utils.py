import json
import logging
import sys
from typing import Any, Dict, Optional


REQUEST_ID_HEADER = "X-Request-ID"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Enhanced context fields (Phase 4)
        context_fields = (
            # Request tracking
            "request_id", "container", "client_host",
            # Request details
            "path", "method", "status_code",
            # Performance metrics
            "latency_ms", "model_inference_ms", "queue_time_ms",
            # Prediction details
            "series_id", "rows", "pred_len", "series_count",
            # Input/output sizes
            "request_size_bytes", "response_size_bytes",
            # Error context
            "error_type", "error_message", "timeout_seconds",
        )

        for key in context_fields:
            value = getattr(record, key, None)
            if value is not None:
                log_record[key] = value

        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(log_record, ensure_ascii=False)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level, logging.INFO))
    root_logger.handlers = [handler]


def get_logger(name: Optional[str] = None) -> logging.Logger:
    return logging.getLogger(name if name else "kronos.service")
