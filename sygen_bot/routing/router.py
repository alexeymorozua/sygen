"""Model router: maps complexity tier + provider to a concrete model name."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sygen_bot.config import RoutingConfig
    from sygen_bot.routing.classifier import MessageClassifier

logger = logging.getLogger(__name__)


class ModelRouter:
    """Resolve the optimal model for a message based on its complexity."""

    def __init__(self, config: RoutingConfig, classifier: MessageClassifier) -> None:
        self._config = config
        self._classifier = classifier

    @property
    def classifier(self) -> MessageClassifier:
        """Public access to the underlying classifier."""
        return self._classifier

    async def resolve_model(self, message: str, provider: str) -> str | None:
        """Classify *message* and return the model name for *provider*.

        Returns ``None`` when routing is disabled, unconfigured, or the
        provider has no tier mapping — the caller should use its default.
        """
        if not self._config.enabled:
            return None
        if not self._config.api_key:
            return None

        tier = await self._classifier.classify(message)

        tier_config = self._config.tiers.get(provider)
        if tier_config is None:
            logger.debug("No routing tiers for provider=%s", provider)
            return None

        model = getattr(tier_config, tier, "") or ""
        if not model:
            logger.debug("No model for tier=%s provider=%s", tier, provider)
            return None

        logger.info("Routing: message classified as %s, using model %s", tier, model)
        return model

    async def close(self) -> None:
        """Shut down the classifier's HTTP client."""
        await self._classifier.close()
