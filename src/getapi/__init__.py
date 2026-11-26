"""Python-client voor GetAPI.nl: KVK, BTW/VAT, BAG-adres, WOZ, energielabel en meer Nederlandse data."""

from ._version import __version__
from .client import DEFAULT_BASE_URL, AsyncGetApi, GetApi
from .errors import (
    ApiError,
    AuthError,
    ConnectionError,
    CreditsExhaustedError,
    GetApiError,
    InvalidArgumentError,
    NotFoundError,
    RateLimitError,
    UpstreamUnavailableError,
    ValidationError,
)
from .response import Response

__all__ = [
    "DEFAULT_BASE_URL",
    "ApiError",
    "AsyncGetApi",
    "AuthError",
    "ConnectionError",
    "CreditsExhaustedError",
    "GetApi",
    "GetApiError",
    "InvalidArgumentError",
    "NotFoundError",
    "RateLimitError",
    "Response",
    "UpstreamUnavailableError",
    "ValidationError",
    "__version__",
]
