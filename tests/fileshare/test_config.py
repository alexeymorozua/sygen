"""Tests for FileshareConfig model parsing."""

from __future__ import annotations

from sygen_bot.config import AgentConfig, FileshareConfig


class TestFileshareConfigDefaults:
    def test_default_values(self) -> None:
        cfg = FileshareConfig()
        assert cfg.enabled is False
        assert cfg.host == "127.0.0.1"
        assert cfg.port == 8090

    def test_agent_config_has_fileshare(self) -> None:
        cfg = AgentConfig()
        assert isinstance(cfg.fileshare, FileshareConfig)
        assert cfg.fileshare.enabled is False

    def test_custom_values(self) -> None:
        cfg = FileshareConfig(enabled=True, host="0.0.0.0", port=9090)
        assert cfg.enabled is True
        assert cfg.host == "0.0.0.0"
        assert cfg.port == 9090

    def test_from_dict(self) -> None:
        cfg = AgentConfig(**{"fileshare": {"enabled": True, "port": 7070}})
        assert cfg.fileshare.enabled is True
        assert cfg.fileshare.port == 7070
        assert cfg.fileshare.host == "127.0.0.1"  # default preserved
