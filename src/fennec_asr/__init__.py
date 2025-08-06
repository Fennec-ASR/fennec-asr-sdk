from ._version import __version__
from .client import FennecASRClient, DEFAULT_BASE_URL
from .streaming import Realtime, StreamingSession  # StreamingSession kept as alias for back-compat
from .shortcuts import transcribe, get_default_client
from .exceptions import (
    FennecASRError,
    AuthenticationError,
    NotFoundError,
    APIError,
)
from .types import TranscriptionStatus

__all__ = [
    "__version__",
    "DEFAULT_BASE_URL",
    # HTTP client
    "FennecASRClient",
    # Realtime WS client
    "Realtime",
    "StreamingSession",
    # One-liner helpers
    "transcribe",
    "get_default_client",
    # Types / Exceptions
    "TranscriptionStatus",
    "FennecASRError",
    "AuthenticationError",
    "NotFoundError",
    "APIError",
]
