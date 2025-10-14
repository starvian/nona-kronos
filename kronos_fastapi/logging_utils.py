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
            "name": record.name,
            "message": record.getMessage(),
        }

        for key in ("request_id", "latency_ms", "path", "method", "status_code", "rows", "pred_len", "series_count"):
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
