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
    from fastapi.responses import JSONResponse as JR

    @app.exception_handler(404)
    async def _404(request, exc):
        return JR({"detail": "not found"}, 404)

    @app.exception_handler(500)
    async def _500(request, exc):
        return JR({"detail": "internal error (logged)"}, 500)

    app.middleware("http")(edge_middleware)
