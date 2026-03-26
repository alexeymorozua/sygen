"""Webhook system: HTTP ingress for external event triggers."""

from sygen_bot.webhook.manager import WebhookManager
from sygen_bot.webhook.models import WebhookEntry, WebhookResult

__all__ = ["WebhookEntry", "WebhookManager", "WebhookResult"]
