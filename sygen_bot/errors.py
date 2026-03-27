"""Project-level exception hierarchy."""


class SygenError(Exception):
    """Base for all sygen exceptions."""


class CLIError(SygenError):
    """CLI execution failed."""


class WorkspaceError(SygenError):
    """Workspace initialization or access failed."""


class SessionError(SygenError):
    """Session persistence or lifecycle failed."""


class CronError(SygenError):
    """Cron job scheduling or execution failed."""


class StreamError(SygenError):
    """Streaming output failed."""


class SecurityError(SygenError):
    """Security violation detected."""


class PathValidationError(SecurityError):
    """File path failed validation."""


class WebhookError(SygenError):
    """Webhook server or dispatch failed."""
