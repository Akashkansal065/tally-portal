from fastapi import Request
from starlette.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

def get_client_ip(request: Request) -> str:
    """
    Extract client IP address, respecting reverse proxy headers (Cloudflare, Nginx, ALB, Vercel).
    Falls back to request.client.host if headers are absent.
    """
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()

    x_real_ip = request.headers.get("x-real-ip")
    if x_real_ip:
        return x_real_ip.strip()

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    if request.client and request.client.host:
        return request.client.host

    return "127.0.0.1"


# Initialize the Limiter with client IP resolution and environment toggle
limiter = Limiter(
    key_func=get_client_ip,
    enabled=settings.RATE_LIMIT_ENABLED,
    headers_enabled=True,
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Custom 429 response handler returning both 'detail' and 'error' keys for broad compatibility
    with standard FastAPI exceptions and UI notification frameworks.
    """
    logger.warning(
        f"Rate limit exceeded on {request.method} {request.url.path} from IP {get_client_ip(request)}: {exc.detail}"
    )
    response = JSONResponse(
        {
            "detail": f"Too many requests. Rate limit exceeded: {exc.detail}. Please wait before trying again.",
            "error": f"Rate limit exceeded: {exc.detail}",
        },
        status_code=429,
    )
    if hasattr(request.app.state, "limiter") and hasattr(request.state, "view_rate_limit"):
        response = request.app.state.limiter._inject_headers(
            response, request.state.view_rate_limit
        )
    return response
