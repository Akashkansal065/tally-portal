from fastapi import Request
from starlette.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from app.core.config import settings
import ipaddress
import logging

logger = logging.getLogger(__name__)

def _trusted_proxies() -> list:
    """The proxies whose forwarding headers are believed (TRUSTED_PROXY_IPS: addresses or CIDRs)."""
    nets = []
    for part in (settings.TRUSTED_PROXY_IPS or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            nets.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            logger.warning(f"Ignoring invalid TRUSTED_PROXY_IPS entry: {part!r}")
    return nets


def _is_trusted(ip: str, nets: list) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in nets)


def get_client_ip(request: Request) -> str:
    """
    The address of whoever made the request. Forwarding headers are only believed when the request came straight
    from a trusted proxy (TRUSTED_PROXY_IPS): from anyone else they are whatever the caller chose to send. Of the
    X-Forwarded-For hops, the client is the right-most one that is not itself a trusted proxy; the left-most is
    the one a caller can forge.
    """
    peer = request.client.host if request.client and request.client.host else "127.0.0.1"
    nets = _trusted_proxies()
    if not _is_trusted(peer, nets):
        return peer

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        hops = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
        for hop in reversed(hops):
            if not _is_trusted(hop, nets):
                return hop
        if hops:
            return hops[0]

    for header in ("x-real-ip", "cf-connecting-ip"):
        value = (request.headers.get(header) or "").strip()
        if value:
            return value

    return peer


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
