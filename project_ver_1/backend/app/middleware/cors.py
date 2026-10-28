from fastapi.middleware.cors import CORSMiddleware

from app.config import ALLOWED_ORIGINS


def configure_cors(app):
    """Enable local frontend origins; production must configure explicit trusted origins."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
