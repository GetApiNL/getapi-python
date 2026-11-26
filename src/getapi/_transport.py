"""Gedeelde logica voor het bouwen van verzoeken en het vertalen van antwoorden."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx

from .errors import (
    ApiError,
    AuthError,
    CreditsExhaustedError,
    NotFoundError,
    RateLimitError,
    UpstreamUnavailableError,
    ValidationError,
)
from .response import Response


@dataclass
class Request:
    """Een voorbereid verzoek, los van sync of async uitvoeren."""

    method: str
    path: str
    params: dict[str, Any] = field(default_factory=dict)
    body: Any = None
    invalid_is_answer: bool = False
    idempotency_key: str | None = None


def clean_params(params: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Laat lege waarden weg en maak er een lijst (naam, tekst) van."""
    out: list[tuple[str, str]] = []
    for key, value in params.items():
        if value is None or value == "":
            continue
        values = value if isinstance(value, (list, tuple)) else [value]
        for item in values:
            out.append((key, ("true" if item else "false") if isinstance(item, bool) else str(item)))
    return out


def _to_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _is_validity_answer(data: Any) -> bool:
    """Een 422 met een ``valid``-veld is het antwoord van een controle, geen invoerfout."""
    return isinstance(data, dict) and "valid" in data


def build_response(res: httpx.Response, invalid_is_answer: bool) -> Response:
    """Zet een httpx-antwoord om in een ``Response`` of gooi de passende fout."""
    status = res.status_code
    text = res.text
    data: Any = None
    if text != "":
        try:
            data = json.loads(text)
        except ValueError:
            if res.is_success:
                raise ApiError("GetAPI gaf een antwoord dat geen geldige JSON is.", status, text) from None

    if res.is_success or (status == 422 and invalid_is_answer and _is_validity_answer(data)):
        remaining = _to_float(res.headers.get("X-Credits-Remaining"))
        return Response(
            data=data,
            status_code=status,
            credits_remaining=int(remaining) if remaining is not None else None,
            headers=res.headers,
        )

    raise to_error(res, data)


def _string(body: Mapping[str, Any], key: str) -> str | None:
    value = body.get(key)
    return value if isinstance(value, str) else None


def to_error(res: httpx.Response, data: Any) -> ApiError:
    """Vertaal een foutantwoord naar de passende uitzondering."""
    status = res.status_code
    body: Mapping[str, Any] = data if isinstance(data, dict) else {}
    code = _string(body, "error") or _string(body, "code")
    api_message = _string(body, "message")

    if status in (401, 403):
        return AuthError(api_message or "De API-key is ongeldig of heeft geen toegang tot dit endpoint.", status, data, code)
    if status == 402:
        return CreditsExhaustedError(
            "Je credits zijn op. Vul je saldo aan om door te gaan.", status, data, code, _string(body, "topup_url")
        )
    if status == 404:
        return NotFoundError(api_message or "Niet gevonden.", status, data, code)
    if status == 422:
        raw_errors = body.get("errors")
        errors: dict[str, list[str]] = raw_errors if isinstance(raw_errors, dict) else {}
        return ValidationError(api_message or "De invoer is ongeldig.", status, data, code, errors)
    if status == 429:
        retry = _to_float(res.headers.get("Retry-After"))
        body_retry = body.get("retry_after")
        if retry is None and isinstance(body_retry, (int, float)) and not isinstance(body_retry, bool):
            retry = float(body_retry)
        reset = _to_float(res.headers.get("X-RateLimit-Reset"))
        message = "Te veel verzoeken. Probeer het later opnieuw."
        return RateLimitError(message, status, data, code, retry, int(reset) if reset is not None else None)
    if status == 503:
        message = api_message or "De bron achter deze API is tijdelijk niet beschikbaar."
        return UpstreamUnavailableError(message, status, data, code)
    return ApiError(api_message or f"GetAPI gaf een onverwachte fout (HTTP {status}).", status, data, code)


def build_headers(api_key: str, client_header: str, user_agent: str, request: Request) -> dict[str, str]:
    """Bouw de headers voor een verzoek."""
    headers = {
        "Accept": "application/json",
        "X-Api-Key": api_key,
        "X-GetAPI-Client": client_header,
        "User-Agent": user_agent,
    }
    if request.body is not None:
        headers["Content-Type"] = "application/json"
    if request.idempotency_key:
        headers["Idempotency-Key"] = request.idempotency_key
    return headers
