"""HTTPS enforcement middleware for production deployments.
Redirect HTTP to HTTPS when running behind a reverse proxy with SSL termination.
"""
import os

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Force HTTPS in production by redirecting HTTP requests."""

    async def dispatch(self, request: Request, call_next):
        # Only enforce in production (check env var)
        if os.environ.get("FORCE_HTTPS", "").lower() != "true":
            return await call_next(request)

        # If request is HTTP and we're not behind a proxy, redirect
        if request.headers.get("x-forwarded-proto", "http") == "http":
            url = request.url.replace(scheme="https")
            return RedirectResponse(url=str(url), status_code=301)

        return await call_next(request)
