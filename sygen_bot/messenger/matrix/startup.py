"""Matrix-specific startup sequence.

Reuses orchestrator creation from the core but skips Telegram-specific
parts (bot username lookup, command registration, group audit).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sygen_bot.i18n import t
from sygen_bot.infra.restart import consume_restart_marker

if TYPE_CHECKING:
    from sygen_bot.messenger.matrix.bot import MatrixBot

logger = logging.getLogger(__name__)


async def run_matrix_startup(bot: MatrixBot) -> None:
    """Matrix-specific startup: orchestrator, observers, recovery.

    When ``bot._orchestrator`` is already set (secondary transport mode),
    orchestrator creation and all primary-only steps are skipped.
    """
    primary = bot._orchestrator is None

    if primary:
        from sygen_bot.orchestrator.core import Orchestrator

        bot._orchestrator = await Orchestrator.create(bot._config, agent_name=bot._agent_name)

        # Wire all observers + injector to bus in one call
        bot._orchestrator.wire_observers_to_bus(bot._bus)

        # Handle restart sentinel
        restart_reason = _consume_restart_sentinel(bot)

        # Notify restart
        if restart_reason:
            await bot.notification_service.notify_all(
                t("startup.matrix_restart", reason=restart_reason)
            )

        # Update checker
        try:
            from sygen_bot.infra.install import is_upgradeable
            from sygen_bot.infra.updater import UpdateObserver
            from sygen_bot.infra.version import SystemUpdatesInfo, VersionInfo

            if is_upgradeable() and bot._config.update_check and bot._agent_name == "main":

                async def _on_update(info: VersionInfo) -> None:
                    await bot.notification_service.notify_all(
                        t("startup.matrix_update", version=info.latest)
                    )

                async def _on_system_update(info: SystemUpdatesInfo) -> None:
                    lines = [f"🔄 {t('upgrade_handler.system_updates_header')}"]
                    for upd in info.updates:
                        lines.append(f"• {upd.name}: {upd.current} → {upd.latest}")
                    await bot.notification_service.notify_all("\n".join(lines))

                bot._update_observer = UpdateObserver(
                    notify=_on_update, notify_system=_on_system_update,
                )
                bot._update_observer.start()
        except ImportError:
            pass

    logger.info(
        "Matrix bot online: %s on %s",
        bot._config.matrix.user_id,
        bot._config.matrix.homeserver,
    )

    # Run registered startup hooks (supervisor injection)
    for hook in bot._startup_hooks:
        await hook()


def _consume_restart_sentinel(bot: MatrixBot) -> str:
    """Check and consume restart marker."""
    paths_obj = bot._orchestrator.paths if bot._orchestrator else None
    if paths_obj is None:
        return ""
    marker_path = paths_obj.sygen_home / "restart-requested"
    if consume_restart_marker(marker_path=marker_path):
        return "restart marker"
    return ""
