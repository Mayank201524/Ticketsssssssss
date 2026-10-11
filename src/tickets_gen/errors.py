class TicketsGenError(Exception):
    """Base exception for application-level errors."""


class ConfigurationError(TicketsGenError):
    """Raised when required local configuration is missing or invalid."""


class GitHubAPIError(TicketsGenError):
    """Raised when GitHub returns an unexpected API response."""
