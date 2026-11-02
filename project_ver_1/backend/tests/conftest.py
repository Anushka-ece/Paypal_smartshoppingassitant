import os
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_paypal_family.db")
os.environ.setdefault("APP_JWT_SECRET", "test-jwt-secret-for-unit-tests-only-32bytes")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "test-token-encryption-key-for-unit-tests-32bytes")
os.environ.setdefault("PAYPAL_CLIENT_ID", "")
os.environ.setdefault("PAYPAL_CLIENT_SECRET", "")
os.environ.setdefault("PAYPAL_WEBHOOK_ID", "")


@pytest.fixture(autouse=True)
def authenticate_legacy_route_tests(request):
    """Keep legacy endpoint tests authenticated without bypassing production code."""
    if request.node.get_closest_marker("auth_security"):
        yield
        return

    from app.main import app
    from app.models.user import User, UserRole
    from app.security.auth import get_current_user

    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: User(
        id=1,
        family_id=1,
        email="test-parent@example.invalid",
        name="Test Parent",
        hashed_password="not-a-login-credential",
        role=UserRole.PARENT.value,
        auth_token_version=0,
    )
    try:
        yield
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = previous
os.environ.setdefault("GEMINI_API_KEY", "")
