"""Automatic model routing based on message complexity."""

from sygen_bot.routing.classifier import MessageClassifier
from sygen_bot.routing.router import ModelRouter

__all__ = ["MessageClassifier", "ModelRouter"]
