"""Model router: maps complexity tier + provider to a concrete model name."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sygen_bot.config import RoutingConfig
    from sygen_bot.routing.classifier import MessageClassifier

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """Full routing result: model override + background delegation flag."""

    model: str | None
    background: bool
    tier: str = "medium"


class ModelRouter:
    """Resolve the optimal model for a message based on its complexity."""

    def __init__(self, config: RoutingConfig, classifier: MessageClassifier) -> None:
        self._config = config
        self._classifier = classifier

    @property
    def classifier(self) -> MessageClassifier:
        """Public access to the underlying classifier."""
        return self._classifier

    @property
    def can_classify(self) -> bool:
        """Return True when the classifier has an API key and at least one feature is on."""
        return bool(self._config.api_key) and (
            self._config.enabled or self._config.auto_delegate
        )

    async def resolve(self, message: str, provider: str) -> RoutingDecision:
        """Classify *message* and return full routing decision.

        Model routing and auto-delegation are independent:
        - ``enabled=True``  → classifier picks the model tier
        - ``auto_delegate=True`` → classifier decides background vs inline
        - Both can be on/off independently (they share one classifier call)
        """
        if not self.can_classify:
            return RoutingDecision(model=None, background=False)

        result = await self._classifier.classify_full(message)

        # Model selection — only when routing.enabled
        model: str | None = None
        if self._config.enabled:
            tier_config = self._config.tiers.get(provider)
            if tier_config is not None:
                model = getattr(tier_config, result.tier, "") or None

        # Background delegation — only when auto_delegate is on
        background = result.background and self._config.auto_delegate

        logger.info(
            "Routing: tier=%s bg=%s model=%s (routing=%s delegate=%s)",
            result.tier,
            background,
            model or "(default)",
            self._config.enabled,
            self._config.auto_delegate,
        )

        return RoutingDecision(model=model, background=background, tier=result.tier)

    async def resolve_model(self, message: str, provider: str) -> str | None:
        """Classify *message* and return the model name for *provider*.

        Returns ``None`` when routing is disabled, unconfigured, or the
        provider has no tier mapping — the caller should use its default.
        """
        decision = await self.resolve(message, provider)
        return decision.model

    async def close(self) -> None:
        """Shut down the classifier's HTTP client."""
        await self._classifier.close()
