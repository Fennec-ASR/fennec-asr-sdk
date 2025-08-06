class FennecASRError(Exception):
    """Base SDK error."""

class AuthenticationError(FennecASRError):
    """401/403 auth failures."""

class NotFoundError(FennecASRError):
    """404 not found."""

class APIError(FennecASRError):
    """Non-success responses or network errors."""
