from fastapi import FastAPI, Request
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import ALLOWED_HOSTS, APP_ENV


def configure_security_headers(app: FastAPI) -> None:
    # Production deployments must set ALLOWED_HOSTS to actual API hostnames.
    if APP_ENV == "production" and ALLOWED_HOSTS == ["localhost", "127.0.0.1", "testserver"]:
        raise RuntimeError("Set ALLOWED_HOSTS to the production API host before starting in production.")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        if APP_ENV == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
