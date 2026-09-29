import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from app.core.config import settings

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")

def get_request_id() -> str:
    """Returns the current request correlation ID, or an empty string if outside request scope."""
    return request_id_ctx.get() or ""


class CorrelationIdFilter(logging.Filter):
    """Injects the current request correlation ID into every log record."""
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get() or "-"
        return True


class JsonLogFormatter(logging.Formatter):
    """Outputs structured JSON log records for production log aggregation."""
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt or "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "request_id": getattr(record, "request_id", "-"),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)


class StructuredTextFormatter(logging.Formatter):
    """Clean, readable structured text formatter for development and console output."""
    def __init__(self):
        super().__init__(
            fmt="%(asctime)s | %(levelname)-7s | [%(request_id)s] | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )


def setup_logging(log_level: Optional[str] = None, log_format: Optional[str] = None):
    """
    Initializes structured application logging.
    Harmonizes uvicorn and app loggers with unified formatting and correlation ID tracking.
    """
    level_str = log_level or settings.LOG_LEVEL or "INFO"
    level = getattr(logging, level_str.upper(), logging.INFO)
    fmt_type = log_format or settings.LOG_FORMAT or "text"

    formatter = JsonLogFormatter() if fmt_type.lower() == "json" else StructuredTextFormatter()
    correlation_filter = CorrelationIdFilter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.addFilter(correlation_filter)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    # Clear existing handlers to prevent duplicate output
    root_logger.handlers = [handler]

    # Harmonize common framework loggers
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        l = logging.getLogger(logger_name)
        l.handlers = [handler]
        l.propagate = False

    # Suppress verbose 3rd party debug logs
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Helper to retrieve a named logger with structured context."""
    return logging.getLogger(name)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    FastAPI / Starlette middleware that:
    1. Extracts or generates a unique X-Request-ID for distributed tracing.
    2. Binds it to the request async contextvar for logger auto-correlation.
    3. Emits structured access logs with HTTP method, path, status, and duration in ms.
    4. Sets the X-Request-ID header on outgoing HTTP responses.
    """
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        req_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:8]
        token = request_id_ctx.set(req_id)
        
        logger = logging.getLogger("app.access")
        start_time = time.perf_counter()
        is_silent = request.url.path in ("/health", "/healthz", "/")

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            response.headers["X-Request-ID"] = req_id

            if not is_silent:
                client_ip = request.client.host if request.client else "unknown"
                forwarded = request.headers.get("x-forwarded-for")
                if forwarded:
                    client_ip = forwarded.split(",")[0].strip()

                logger.info(
                    f"{request.method} {request.url.path} -> {response.status_code} [{duration_ms}ms] (ip: {client_ip})"
                )
            return response
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                f"{request.method} {request.url.path} FAILED [{duration_ms}ms]: {exc}",
                exc_info=True
            )
            raise
        finally:
            request_id_ctx.reset(token)
