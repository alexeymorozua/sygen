"""CLI layer: provider abstraction, process tracking, streaming."""

from sygen_bot.cli.auth import AuthResult as AuthResult
from sygen_bot.cli.auth import AuthStatus as AuthStatus
from sygen_bot.cli.auth import check_all_auth as check_all_auth
from sygen_bot.cli.base import BaseCLI as BaseCLI
from sygen_bot.cli.base import CLIConfig as CLIConfig
from sygen_bot.cli.coalescer import CoalesceConfig as CoalesceConfig
from sygen_bot.cli.coalescer import StreamCoalescer as StreamCoalescer
from sygen_bot.cli.factory import create_cli as create_cli
from sygen_bot.cli.process_registry import ProcessRegistry as ProcessRegistry
from sygen_bot.cli.service import CLIService as CLIService
from sygen_bot.cli.service import CLIServiceConfig as CLIServiceConfig
from sygen_bot.cli.types import AgentRequest as AgentRequest
from sygen_bot.cli.types import AgentResponse as AgentResponse
from sygen_bot.cli.types import CLIResponse as CLIResponse

__all__ = [
    "AgentRequest",
    "AgentResponse",
    "AuthResult",
    "AuthStatus",
    "BaseCLI",
    "CLIConfig",
    "CLIResponse",
    "CLIService",
    "CLIServiceConfig",
    "CoalesceConfig",
    "ProcessRegistry",
    "StreamCoalescer",
    "check_all_auth",
    "create_cli",
]
