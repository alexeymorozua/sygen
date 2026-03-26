"""Multi-agent architecture: supervisor, bus, and inter-agent communication."""

from sygen_bot.multiagent.bus import InterAgentBus
from sygen_bot.multiagent.health import AgentHealth
from sygen_bot.multiagent.models import SubAgentConfig
from sygen_bot.multiagent.supervisor import AgentSupervisor

__all__ = ["AgentHealth", "AgentSupervisor", "InterAgentBus", "SubAgentConfig"]
