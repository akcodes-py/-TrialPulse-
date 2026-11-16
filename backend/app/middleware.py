"""Cross-cutting request protection: correlation, limits, headers, and cheap rate control."""

import logging
import time
from collections import defaultdict, deque
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.app.observability import access_logger, request_id

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token = request_id.set(uuid4().hex)
        current_id = request_id.get()
        start = time.perf_counter()
        response: Response | None = None
        try:
            content_length = request.headers.get("content-length")
            from backend.app.settings import get_settings

            limit = get_settings().max_request_bytes
            # Enforce the declared size before reading the body; streaming uploads are also checked in the endpoint.
            if content_length and int(content_length) > limit:
                response = JSONResponse({"detail": "Request body too large"}, status_code=413)
            else:
                response = await call_next(request)
        finally:
            access_logger().info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code if response else 500,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                    "client": request.client.host if request.client else None,
                },
            )
            request_id.reset(token)
        response.headers["X-Request-ID"] = current_id
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-client fixed-window limiter for a single process; use an edge limiter when scaled out."""

    def __init__(self, app, limit: int):
        super().__init__(app)
        self.limit = limit
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if not self.limit or request.url.path in {"/api/health", "/api/ready"}:
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        now = time.time()
        window = self.hits[client]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self.limit:
            logging.getLogger("trialpulse.access").warning(
                "rate_limited", extra={"path": request.url.path, "client": client}
            )
            return JSONResponse(
                {"detail": "Rate limit exceeded. Retry shortly."},
                status_code=429,
                headers={"Retry-After": "60"},
            )
        window.append(now)
        return await call_next(request)
