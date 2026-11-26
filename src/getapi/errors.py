"""Fouten van de GetAPI-client."""

from __future__ import annotations

from typing import Any


class GetApiError(Exception):
    """Basisklasse voor alle fouten van de GetAPI-client. Vang deze om alles af te handelen."""


class InvalidArgumentError(GetApiError, ValueError):
    """Je gaf een ongeldige waarde mee. Er is nog geen verzoek verstuurd en er zijn geen credits gebruikt."""


class ConnectionError(GetApiError):
    """De API is niet bereikt: netwerkfout, time-out of een verbroken verbinding."""


class ApiError(GetApiError):
    """De API gaf een foutstatus.

    Attributes:
        status_code: HTTP-statuscode van het antwoord.
        data: De (geparste) body van het antwoord, als die er was.
        code: Foutcode uit de body, bijvoorbeeld ``insufficient_credits``.
    """

    def __init__(self, message: str, status_code: int, data: Any = None, code: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.data = data
        self.code = code


class AuthError(ApiError):
    """401 of 403: de API-key ontbreekt, is ongeldig of heeft geen toegang."""


class CreditsExhaustedError(ApiError):
    """402: je credits zijn op. Stuur de gebruiker naar ``topup_url`` om bij te vullen."""

    def __init__(self, message: str, status_code: int, data: Any, code: str | None, topup_url: str | None) -> None:
        super().__init__(message, status_code, data, code)
        self.topup_url = topup_url


class NotFoundError(ApiError):
    """404: het gevraagde item bestaat niet (bijvoorbeeld een onbekend KVK-nummer)."""


class ValidationError(ApiError):
    """422: de invoer is ongeldig. ``errors`` bevat de fouten per veld."""

    def __init__(self, message: str, status_code: int, data: Any, code: str | None, errors: dict[str, list[str]]) -> None:
        super().__init__(message, status_code, data, code)
        self.errors = errors


class RateLimitError(ApiError):
    """429: te veel verzoeken. Probeer opnieuw na ``retry_after`` seconden."""

    def __init__(
        self,
        message: str,
        status_code: int,
        data: Any,
        code: str | None,
        retry_after: float | None,
        reset_at: int | None,
    ) -> None:
        super().__init__(message, status_code, data, code)
        self.retry_after = retry_after
        self.reset_at = reset_at


class UpstreamUnavailableError(ApiError):
    """503: een bron achter de API (bijvoorbeeld KVK of VIES) is tijdelijk niet beschikbaar."""
