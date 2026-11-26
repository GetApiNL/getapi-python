from __future__ import annotations

import httpx
import pytest

from getapi import (
    ApiError,
    AuthError,
    CreditsExhaustedError,
    NotFoundError,
    RateLimitError,
    UpstreamUnavailableError,
    ValidationError,
)
from getapi._transport import Request, build_headers, build_response, clean_params, to_error


def response(status: int, body: object = None, headers: dict[str, str] | None = None, raw: str | None = None) -> httpx.Response:
    if raw is not None:
        return httpx.Response(status, text=raw, headers=headers)
    return httpx.Response(status, json=body, headers=headers)


class TestCleanParams:
    def test_laat_lege_waarden_weg(self) -> None:
        assert clean_params({"a": None, "b": "", "c": "x"}) == [("c", "x")]

    def test_nul_en_false_blijven_staan(self) -> None:
        assert clean_params({"a": 0, "b": False}) == [("a", "0"), ("b", "false")]

    def test_booleans_worden_true_false(self) -> None:
        assert clean_params({"a": True}) == [("a", "true")]

    def test_lijsten_worden_herhaald(self) -> None:
        assert clean_params({"t[]": ["a", "b"]}) == [("t[]", "a"), ("t[]", "b")]
        assert clean_params({"t": ("a",)}) == [("t", "a")]

    def test_lege_lijst_geeft_niets(self) -> None:
        assert clean_params({"t": []}) == []


class TestBuildHeaders:
    def test_basisheaders(self) -> None:
        headers = build_headers("key", "client/1", "agent/1", Request("GET", "/x"))
        assert headers == {
            "Accept": "application/json",
            "X-Api-Key": "key",
            "X-GetAPI-Client": "client/1",
            "User-Agent": "agent/1",
        }

    def test_json_body_en_idempotency_key(self) -> None:
        headers = build_headers("k", "c", "u", Request("POST", "/x", body={}, idempotency_key="abc"))
        assert headers["Content-Type"] == "application/json"
        assert headers["Idempotency-Key"] == "abc"


class TestBuildResponse:
    def test_succes(self) -> None:
        res = build_response(response(200, {"a": 1}, {"X-Credits-Remaining": "7"}), False)
        assert (res.data, res.status_code, res.credits_remaining) == ({"a": 1}, 200, 7)

    def test_zonder_credits_header(self) -> None:
        assert build_response(response(200, {}), False).credits_remaining is None

    def test_ongeldige_credits_header_geeft_none(self) -> None:
        assert build_response(response(200, {}, {"X-Credits-Remaining": "veel"}), False).credits_remaining is None

    def test_lege_body_is_none(self) -> None:
        assert build_response(response(204, raw=""), False).data is None

    def test_ongeldige_json_bij_succes_is_api_error(self) -> None:
        with pytest.raises(ApiError, match="geen geldige JSON"):
            build_response(response(200, raw="<html>"), False)

    def test_ongeldige_json_bij_fout_geeft_gewone_fout(self) -> None:
        with pytest.raises(UpstreamUnavailableError):
            build_response(response(503, raw="<html>"), False)

    def test_422_met_valid_is_antwoord_als_toegestaan(self) -> None:
        res = build_response(response(422, {"valid": False}), True)
        assert res.status_code == 422
        assert res.data == {"valid": False}

    def test_422_zonder_valid_is_altijd_een_fout(self) -> None:
        body = {"message": "ongeldig", "errors": {"vat_number": ["fout"]}}
        with pytest.raises(ValidationError):
            build_response(response(422, body), True)

    def test_422_is_fout_als_niet_toegestaan(self) -> None:
        with pytest.raises(ValidationError):
            build_response(response(422, {"valid": False}), False)

    def test_422_met_niet_object_body_is_fout(self) -> None:
        with pytest.raises(ValidationError):
            build_response(response(422, ["x"]), True)


class TestToError:
    @pytest.mark.parametrize(
        ("status", "cls"),
        [
            (401, AuthError),
            (403, AuthError),
            (404, NotFoundError),
            (422, ValidationError),
            (503, UpstreamUnavailableError),
            (400, ApiError),
            (500, ApiError),
            (302, ApiError),
        ],
    )
    def test_status_naar_klasse(self, status: int, cls: type[ApiError]) -> None:
        err = to_error(response(status, {}), {})
        assert type(err) is cls
        assert err.status_code == status

    def test_gebruikt_bericht_en_code_uit_body(self) -> None:
        err = to_error(response(404, {}), {"message": "Weg", "error": "not_found"})
        assert (str(err), err.code) == ("Weg", "not_found")

    def test_code_valt_terug_op_code_veld(self) -> None:
        err = to_error(response(500, {}), {"code": "x"})
        assert isinstance(err, ApiError)
        assert err.code == "x"

    def test_standaardberichten_zonder_body(self) -> None:
        assert "HTTP 500" in str(to_error(response(500, {}), None))
        assert str(to_error(response(404, {}), None)) == "Niet gevonden."
        assert "API-key" in str(to_error(response(401, {}), None))
        assert "ongeldig" in str(to_error(response(422, {}), None))
        assert "niet beschikbaar" in str(to_error(response(503, {}), None))

    def test_402_met_topup_url(self) -> None:
        err = to_error(response(402, {}), {"error": "insufficient_credits", "topup_url": "https://getapi.nl/topup"})
        assert isinstance(err, CreditsExhaustedError)
        assert err.topup_url == "https://getapi.nl/topup"
        assert err.code == "insufficient_credits"

    def test_402_zonder_topup_url(self) -> None:
        err = to_error(response(402, {}), {"topup_url": 5})
        assert isinstance(err, CreditsExhaustedError)
        assert err.topup_url is None

    def test_422_leest_errors_per_veld(self) -> None:
        err = to_error(response(422, {}), {"errors": {"q": ["te kort"]}})
        assert isinstance(err, ValidationError)
        assert err.errors == {"q": ["te kort"]}

    def test_422_met_errors_als_lijst_geeft_lege_dict(self) -> None:
        err = to_error(response(422, {}), {"errors": []})
        assert isinstance(err, ValidationError)
        assert err.errors == {}

    def test_429_header_wint_van_body(self) -> None:
        res = response(429, {}, {"Retry-After": "30", "X-RateLimit-Reset": "1700000000"})
        err = to_error(res, {"retry_after": 9})
        assert isinstance(err, RateLimitError)
        assert (err.retry_after, err.reset_at) == (30, 1700000000)

    def test_429_valt_terug_op_body(self) -> None:
        err = to_error(response(429, {}), {"retry_after": 9})
        assert isinstance(err, RateLimitError)
        assert (err.retry_after, err.reset_at) == (9, None)

    def test_429_negeert_ongeldige_waarden(self) -> None:
        err = to_error(response(429, {}, {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}), {"retry_after": True})
        assert isinstance(err, RateLimitError)
        assert err.retry_after is None
