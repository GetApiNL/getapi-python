from __future__ import annotations

import json
from typing import Awaitable

import httpx
import pytest

import getapi
from getapi import (
    ApiError,
    AsyncGetApi,
    AuthError,
    ConnectionError,
    CreditsExhaustedError,
    GetApi,
    InvalidArgumentError,
    NotFoundError,
    RateLimitError,
    Response,
    UpstreamUnavailableError,
    ValidationError,
)

from .helpers import Recorder, client_for

VERSION = getapi.__version__


class TestConstructor:
    @pytest.mark.parametrize("key", ["", " ", "\n"])
    def test_lege_key_wordt_geweigerd(self, key: str) -> None:
        with pytest.raises(InvalidArgumentError, match="API-key"):
            GetApi(key)
        with pytest.raises(InvalidArgumentError, match="API-key"):
            AsyncGetApi(key)

    def test_key_van_verkeerd_type_wordt_geweigerd(self) -> None:
        with pytest.raises(InvalidArgumentError):
            GetApi(None)  # type: ignore[arg-type]

    def test_key_wordt_getrimd(self, server: Recorder) -> None:
        GetApi(" k ", http_client=httpx.Client(transport=httpx.MockTransport(server))).lookup.ip("1.1.1.1")
        assert server.last.headers["X-Api-Key"] == "k"

    @pytest.mark.parametrize("url", ["http://api.getapi.nl", "ftp://x", "api.getapi.nl", "https://", ""])
    def test_onveilige_of_ongeldige_base_url_wordt_geweigerd(self, url: str) -> None:
        with pytest.raises(InvalidArgumentError, match="https"):
            GetApi("k", base_url=url)

    @pytest.mark.parametrize("url", ["http://localhost:8000", "http://127.0.0.1", "https://api.getapi.nl/"])
    def test_lokale_http_en_https_zijn_toegestaan(self, url: str) -> None:
        GetApi("k", base_url=url)

    def test_slash_aan_het_eind_van_base_url_wordt_weggehaald(self, server: Recorder) -> None:
        http = httpx.Client(transport=httpx.MockTransport(server))
        GetApi("k", base_url="https://example.test/", http_client=http).lookup.ip("1.1.1.1")
        assert str(server.last.url).startswith("https://example.test/v1/lookup/ip")

    def test_alle_resources_zijn_beschikbaar(self, client: GetApi) -> None:
        for name in ("kvk", "address", "property", "validation", "lookup", "vehicle", "sbi", "dso", "ndw", "scraping"):
            assert getattr(client, name) is not None

    def test_versie(self) -> None:
        assert VERSION.count(".") == 2


class TestRequests:
    def test_stuurt_key_en_client_headers_mee(self, client: GetApi, server: Recorder) -> None:
        server.headers = {"X-Credits-Remaining": "248"}
        server.body = {"naam": "X"}
        res = client.kvk.get("53743792")
        assert isinstance(res, Response)
        assert res["naam"] == "X"
        assert res.credits_remaining == 248
        req = server.last
        assert str(req.url) == "https://api.getapi.nl/v1/kvk/53743792"
        assert req.headers["X-Api-Key"] == "ga_live_test"
        assert req.headers["Accept"] == "application/json"
        assert req.headers["X-GetAPI-Client"] == f"getapi-python/{VERSION}"
        assert req.headers["User-Agent"].startswith(f"getapi-python/{VERSION} (python/")

    def test_eigen_client_name(self, server: Recorder) -> None:
        client_for(server, client_name="mijn-app/2.1").lookup.ip("1.1.1.1")
        assert server.last.headers["X-GetAPI-Client"] == "mijn-app/2.1"

    def test_get_heeft_geen_body(self, client: GetApi, server: Recorder) -> None:
        client.lookup.ip("1.1.1.1")
        assert server.last.method == "GET"
        assert server.last.content == b""
        assert "Content-Type" not in server.last.headers

    def test_post_stuurt_json(self, client: GetApi, server: Recorder) -> None:
        client.validation.email("a@b.nl")
        assert server.last.method == "POST"
        assert json.loads(server.last.content) == {"email": "a@b.nl"}
        assert server.last.headers["Content-Type"] == "application/json"

    def test_lege_parameters_worden_weggelaten(self, client: GetApi, server: Recorder) -> None:
        client.kvk.search(naam=" bol ", page=2)
        assert str(server.last.url) == "https://api.getapi.nl/v1/kvk/search?naam=bol&page=2"

    def test_idempotency_key(self, client: GetApi, server: Recorder) -> None:
        client.property.woz_value("3023KN", 161, idempotency_key="abc")
        assert server.last.headers["Idempotency-Key"] == "abc"

    def test_geen_idempotency_key_header_als_niet_opgegeven(self, client: GetApi, server: Recorder) -> None:
        client.property.woz_value("3023KN", 161)
        assert "Idempotency-Key" not in server.last.headers


class TestErrors:
    @pytest.mark.parametrize(
        ("status", "cls"),
        [
            (401, AuthError),
            (403, AuthError),
            (404, NotFoundError),
            (422, ValidationError),
            (503, UpstreamUnavailableError),
            (500, ApiError),
        ],
    )
    def test_statussen_geven_de_juiste_fout(self, client: GetApi, server: Recorder, status: int, cls: type[ApiError]) -> None:
        server.status = status
        server.body = {"message": "x"}
        with pytest.raises(cls):
            client.kvk.get("53743792")

    def test_402_geeft_topup_url(self, client: GetApi, server: Recorder) -> None:
        server.status = 402
        server.body = {"error": "insufficient_credits", "topup_url": "https://getapi.nl/topup"}
        with pytest.raises(CreditsExhaustedError) as e:
            client.kvk.get("53743792")
        assert e.value.topup_url == "https://getapi.nl/topup"

    def test_429(self, client: GetApi, server: Recorder) -> None:
        server.status = 429
        server.headers = {"Retry-After": "30"}
        with pytest.raises(RateLimitError) as e:
            client.kvk.get("53743792")
        assert e.value.retry_after == 30

    def test_422_bij_controle_is_een_antwoord(self, client: GetApi, server: Recorder) -> None:
        server.status = 422
        server.body = {"valid": False}
        res = client.validation.vat("NL000")
        assert res["valid"] is False
        assert res.status_code == 422

    def test_422_invoerfout_bij_controle_is_een_fout(self, client: GetApi, server: Recorder) -> None:
        server.status = 422
        server.body = {"message": "ongeldig", "errors": {"vat_number": ["fout"]}}
        with pytest.raises(ValidationError):
            client.validation.vat("NL000")

    def test_netwerkfout_wordt_connection_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boem", request=request)

        with pytest.raises(ConnectionError, match="niet bereiken") as e:
            client_for(handler).kvk.get("53743792")
        assert isinstance(e.value.__cause__, httpx.ConnectError)

    def test_timeout_wordt_connection_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("traag", request=request)

        with pytest.raises(ConnectionError, match="geen antwoord"):
            client_for(handler).kvk.get("53743792")

    def test_ongeldige_json_bij_200_is_api_error(self, client: GetApi, server: Recorder) -> None:
        server.raw = "geen json"
        with pytest.raises(ApiError):
            client.kvk.get("53743792")

    def test_ongeldige_invoer_verstuurt_niets(self, client: GetApi, server: Recorder) -> None:
        with pytest.raises(InvalidArgumentError):
            client.kvk.get("123")
        assert server.requests == []


class TestLifecycle:
    def test_close_sluit_eigen_client(self) -> None:
        client = GetApi("k")
        client.close()
        assert client._http.is_closed

    def test_close_laat_meegegeven_client_open(self) -> None:
        http = httpx.Client(transport=httpx.MockTransport(Recorder()))
        GetApi("k", http_client=http).close()
        assert not http.is_closed
        http.close()

    def test_context_manager(self) -> None:
        with GetApi("k") as client:
            assert isinstance(client, GetApi)
        assert client._http.is_closed

    def test_timeout_wordt_aan_eigen_client_doorgegeven(self) -> None:
        with GetApi("k", timeout=3.0) as client:
            assert client._http.timeout == httpx.Timeout(3.0)

    def test_context_manager_sluit_ook_bij_fout(self) -> None:
        with pytest.raises(RuntimeError), GetApi("k") as client:
            raise RuntimeError
        assert client._http.is_closed


class TestAsync:
    async def test_basis(self, async_client: AsyncGetApi, server: Recorder) -> None:
        server.body = {"naam": "X"}
        server.headers = {"X-Credits-Remaining": "5"}
        pending = async_client.kvk.get("53743792")
        assert isinstance(pending, Awaitable)
        res = await pending
        assert res["naam"] == "X"
        assert res.credits_remaining == 5
        assert server.last.headers["X-GetAPI-Client"] == f"getapi-python/{VERSION}"
        await async_client.aclose()

    async def test_post(self, async_client: AsyncGetApi, server: Recorder) -> None:
        await async_client.validation.vat("nl 820646660 b01")
        assert json.loads(server.last.content) == {"vat_number": "NL820646660B01"}

    async def test_fout_wordt_bij_await_gegooid(self, async_client: AsyncGetApi, server: Recorder) -> None:
        server.status = 404
        with pytest.raises(NotFoundError):
            await async_client.kvk.get("53743792")

    async def test_ongeldige_invoer_wordt_direct_gemeld(self, async_client: AsyncGetApi, server: Recorder) -> None:
        with pytest.raises(InvalidArgumentError):
            async_client.kvk.get("123")
        assert server.requests == []

    async def test_netwerkfout_en_timeout(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("slow"):
                raise httpx.ReadTimeout("traag", request=request)
            raise httpx.ConnectError("boem", request=request)

        async with AsyncGetApi("k", http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))) as client:
            with pytest.raises(ConnectionError, match="niet bereiken"):
                await client.kvk.get("53743792")
            with pytest.raises(ConnectionError, match="geen antwoord"):
                await client.sbi.get("slow")

    async def test_context_manager_sluit_eigen_client(self) -> None:
        async with AsyncGetApi("k") as client:
            assert isinstance(client, AsyncGetApi)
        assert client._http.is_closed

    async def test_aclose_laat_meegegeven_client_open(self) -> None:
        http = httpx.AsyncClient(transport=httpx.MockTransport(Recorder()))
        await AsyncGetApi("k", http_client=http).aclose()
        assert not http.is_closed
        await http.aclose()
