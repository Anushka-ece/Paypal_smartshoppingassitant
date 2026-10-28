import logging
from typing import Any

logger = logging.getLogger(__name__)


def send_parent_transaction_alert(parent_id: int, transaction_id: int, summary: str, risk_level: str) -> None:
    """Notification adapter placeholder; production push delivery is not configured yet."""
    logger.info(
        "Parent alert queued for app integration",
        extra={"parent_id": parent_id, "transaction_id": transaction_id, "risk_level": risk_level, "summary": summary},
    )


def send_family_invitation(email: str, invite_token: str, invite_url: str) -> None:
    """Email provider adapter placeholder; do not log invite tokens or URLs."""
    # Intentionally do not log invite_token. Configure a reviewed provider before production.
    logger.info("Family invitation email provider is not configured", extra={"recipient": email, "delivery": "not_sent"})
