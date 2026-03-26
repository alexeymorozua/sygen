"""Messenger abstraction layer — transport-agnostic protocols and registry."""

from sygen_bot.messenger.capabilities import MessengerCapabilities
from sygen_bot.messenger.commands import (
    DIRECT_COMMANDS,
    MULTIAGENT_COMMANDS,
    ORCHESTRATOR_COMMANDS,
    classify_command,
)
from sygen_bot.messenger.multi import MultiBotAdapter
from sygen_bot.messenger.notifications import CompositeNotificationService, NotificationService
from sygen_bot.messenger.protocol import BotProtocol
from sygen_bot.messenger.registry import create_bot
from sygen_bot.messenger.send_opts import BaseSendOpts

__all__ = [
    "DIRECT_COMMANDS",
    "MULTIAGENT_COMMANDS",
    "ORCHESTRATOR_COMMANDS",
    "BaseSendOpts",
    "BotProtocol",
    "CompositeNotificationService",
    "MessengerCapabilities",
    "MultiBotAdapter",
    "NotificationService",
    "classify_command",
    "create_bot",
]
