"""Message complexity classifier using lightweight LLM API calls."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from sygen_bot.config import RoutingConfig

logger = logging.getLogger(__name__)

_CLASSIFIER_PROMPT = """\
You are a message complexity classifier. Rate the user message 1-3 and decide \
whether it should run as a background task (b) or inline (i).

1 = LIGHT: greetings, yes/no, thanks, simple factual questions, status checks, \
reminders, short confirmations, translations of short phrases, simple math, \
time/date/weather questions

2 = MEDIUM: explanations, summaries, moderate code (single function, small fix), \
writing emails/messages, data formatting, multi-step but straightforward tasks, \
config changes

3 = HEAVY: architecture design, complex debugging, multi-file code generation, \
deep analysis, research with reasoning, refactoring, planning, code review of \
large diffs, creative writing with complex requirements

Background (b) criteria — tasks that likely take >30 seconds:
- Web research, browsing, comparisons, data gathering
- File generation, document creation, report writing
- Multi-step analysis, deep code review, complex refactoring
- Any task involving multiple tool calls or external lookups

Inline (i) criteria — quick responses:
- Conversational replies, questions, confirmations
- Simple lookups, short answers, config changes
- Single-step operations, quick code fixes

Context matters: a short message can be complex ("refactor auth module") and a \
long message can be simple (pasting an error for quick lookup).

Reply with ONLY the number and letter: 1i, 2i, 2b, 3i, or 3b"""

_TIER_MAP: dict[str, str] = {"1": "light", "2": "medium", "3": "heavy"}
_DEFAULT_TIER = "medium"
_TIMEOUT_SECONDS = 3.0


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """Result of message classification: complexity tier + background flag."""

    tier: str
    background: bool


_DEFAULT_RESULT = ClassificationResult(tier=_DEFAULT_TIER, background=False)


class MessageClassifier:
    """Classify user messages into complexity tiers via a lightweight LLM call."""

    def __init__(self, config: RoutingConfig) -> None:
        self._config = config
        self._client = httpx.AsyncClient(timeout=_TIMEOUT_SECONDS)

    async def close(self) -> None:
        """Shut down the underlying HTTP client."""
        await self._client.aclose()

    async def classify(self, message: str) -> str:
        """Classify *message* as ``'light'``, ``'medium'``, or ``'heavy'``.

        Returns ``'medium'`` on any error or timeout (safe default).
        """
        result = await self.classify_full(message)
        return result.tier

    async def classify_full(self, message: str) -> ClassificationResult:
        """Classify *message* returning tier and background flag.

        Returns ``ClassificationResult('medium', False)`` on any error or timeout.
        """
        try:
            provider = self._config.classifier_provider
            if provider == "anthropic":
                raw = await self._call_anthropic(message)
            elif provider == "openai":
                raw = await self._call_openai(message)
            elif provider == "google":
                raw = await self._call_google(message)
            else:
                logger.warning("Unknown classifier provider: %s", provider)
                return _DEFAULT_RESULT
            return _parse_classification(raw)
        except httpx.TimeoutException:
            logger.warning("Classifier timed out, falling back to medium/inline")
            return _DEFAULT_RESULT
        except Exception:
            logger.warning("Classifier error, falling back to medium/inline", exc_info=True)
            return _DEFAULT_RESULT

    # -- Provider implementations --------------------------------------------

    async def _call_anthropic(self, message: str) -> str:
        resp = await self._client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self._config.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self._config.classifier_model,
                "max_tokens": 4,
                "system": _CLASSIFIER_PROMPT,
                "messages": [{"role": "user", "content": message}],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]

    async def _call_openai(self, message: str) -> str:
        resp = await self._client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._config.classifier_model,
                "max_tokens": 4,
                "messages": [
                    {"role": "system", "content": _CLASSIFIER_PROMPT},
                    {"role": "user", "content": message},
                ],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def _call_google(self, message: str) -> str:
        model = self._config.classifier_model
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
            f":generateContent?key={self._config.api_key}"
        )
        resp = await self._client.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "systemInstruction": {"parts": [{"text": _CLASSIFIER_PROMPT}]},
                "contents": [{"parts": [{"text": message}]}],
                "generationConfig": {"maxOutputTokens": 4},
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


def _parse_classification(raw: str) -> ClassificationResult:
    """Parse classifier response like '2b', '3i', or plain '2' into a result."""
    cleaned = raw.strip()[:2]
    if not cleaned:
        return _DEFAULT_RESULT

    digit = cleaned[0]
    tier = _TIER_MAP.get(digit, _DEFAULT_TIER)

    background = False
    if len(cleaned) >= 2:
        background = cleaned[1].lower() == "b"

    return ClassificationResult(tier=tier, background=background)
