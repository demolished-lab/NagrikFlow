"""Edge hardening: security headers, body-size guard, JSON error shape.

No new deps. 1 MB body cap (our largest legit payload is a 5-URL build form).
"""
from fastapi.responses import JSONResponse

MAX_BODY = 1024 * 1024

HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


async def edge_middleware(request, call_next):
    if request.method in ("POST", "PUT", "PATCH"):
        try:
            length = int(request.headers.get("content-length", "0") or 0)
        except ValueError:
            length = 0
        if length > MAX_BODY:
            return JSONResponse({"detail": "body too large (1 MB max)"}, 413)
    resp = await call_next(request)
    for k, v in HEADERS.items():
        resp.headers.setdefault(k, v)
    return resp


def install(app):
    from fastapi import HTTPException as FHTTPException
    from fastapi.responses import JSONResponse as JR

    @app.exception_handler(404)
    async def _404(request, exc):
        # keep the specific reason ("unknown or unverified map", ...) so the
        # citizen sees WHY; only the bare router 404 normalises to "not found"
        detail = getattr(exc, "detail", None)
        if not isinstance(detail, str) or not detail.strip() or detail == "Not Found":
            detail = "not found"
        return JR({"detail": detail}, 404,
                  headers=getattr(exc, "headers", None))

    @app.exception_handler(500)
    async def _500(request, exc):
        if isinstance(exc, FHTTPException) and isinstance(exc.detail, str) and exc.detail:
            return JR({"detail": exc.detail}, 500)
        # name the failure class so logs and users point at the same cause
        return JR({"detail": "internal error (logged)",
                   "error": type(exc).__name__}, 500)

    app.middleware("http")(edge_middleware)
