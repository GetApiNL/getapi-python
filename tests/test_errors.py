from __future__ import annotations

import pytest

from getapi import (
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


@pytest.mark.parametrize(
    "cls", [ApiError, AuthError, CreditsExhaustedError, NotFoundError, ValidationError, RateLimitError, UpstreamUnavailableError]
)
def test_api_fouten_erven_van_api_error(cls: type[Exception]) -> None:
    assert issubclass(cls, ApiError)
    assert issubclass(cls, GetApiError)


def test_alle_fouten_erven_van_getapi_error() -> None:
    assert issubclass(ConnectionError, GetApiError)
    assert issubclass(InvalidArgumentError, GetApiError)


def test_invalid_argument_error_is_ook_een_value_error() -> None:
    assert issubclass(InvalidArgumentError, ValueError)


def test_connection_error_is_niet_de_ingebouwde() -> None:
    assert not issubclass(ConnectionError, OSError)


def test_api_error_velden() -> None:
    err = ApiError("boem", 500, {"a": 1}, "code")
    assert (str(err), err.status_code, err.data, err.code) == ("boem", 500, {"a": 1}, "code")
    assert ApiError("x", 500).data is None


def test_specifieke_fout_velden() -> None:
    assert CreditsExhaustedError("m", 402, None, None, "https://x").topup_url == "https://x"
    assert ValidationError("m", 422, None, None, {"q": ["fout"]}).errors == {"q": ["fout"]}
    rate = RateLimitError("m", 429, None, None, 3.0, 17)
    assert (rate.retry_after, rate.reset_at) == (3.0, 17)
