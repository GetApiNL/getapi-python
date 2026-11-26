"""De GetAPI-clients: ``GetApi`` (synchroon) en ``AsyncGetApi`` (asynchroon)."""

from __future__ import annotations

import platform
from abc import ABC, abstractmethod
from types import TracebackType
from typing import Any, Awaitable, Generic, TypeVar
from urllib.parse import urlsplit

import httpx

from . import resources
from ._transport import Request, build_headers, build_response, clean_params
from ._version import __version__
from .errors import ConnectionError, InvalidArgumentError
from .response import Response

DEFAULT_BASE_URL = "https://api.getapi.nl"
DEFAULT_TIMEOUT = 15.0

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

R = TypeVar("R")


def _check_base_url(base_url: str) -> str:
    parts = urlsplit(base_url)
    if parts.scheme == "https" and parts.hostname:
        return base_url.rstrip("/")
    if parts.scheme == "http" and parts.hostname in _LOCAL_HOSTS:
        return base_url.rstrip("/")
    raise InvalidArgumentError("De base_url moet met https:// beginnen, anders gaat je API-key onversleuteld over het netwerk.")


class _Base(ABC, Generic[R]):
    """Gemeenschappelijke basis. ``R`` is het resultaat van een aanroep: ``Response`` of een awaitable daarvan."""

    def __init__(self, api_key: str, *, base_url: str, timeout: float, client_name: str | None) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise InvalidArgumentError("De API-key ontbreekt. Maak gratis een key aan op https://getapi.nl/register.")
        self._api_key = api_key.strip()
        self._base_url = _check_base_url(base_url)
        self._timeout = timeout
        self._client_header = client_name or f"getapi-python/{__version__}"
        self._user_agent = f"getapi-python/{__version__} (python/{platform.python_version()})"

        self.kvk: resources.Kvk[R] = resources.Kvk(self._call)
        self.address: resources.Address[R] = resources.Address(self._call)
        self.property: resources.Property[R] = resources.Property(self._call)
        self.validation: resources.Validation[R] = resources.Validation(self._call)
        self.lookup: resources.Lookup[R] = resources.Lookup(self._call)
        self.vehicle: resources.Vehicle[R] = resources.Vehicle(self._call)
        self.sbi: resources.Sbi[R] = resources.Sbi(self._call)
        self.dso: resources.Dso[R] = resources.Dso(self._call)
        self.ndw: resources.Ndw[R] = resources.Ndw(self._call)
        self.scraping: resources.Scraping[R] = resources.Scraping(self._call)

    @abstractmethod
    def _call(self, request: Request) -> R: ...

    def _kwargs(self, request: Request) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "headers": build_headers(self._api_key, self._client_header, self._user_agent, request),
            "params": clean_params(request.params),
        }
        if request.body is not None:
            kwargs["json"] = request.body
        return kwargs

    def _url(self, request: Request) -> str:
        return self._base_url + request.path


_TIMEOUT_MESSAGE = "De GetAPI-server gaf geen antwoord binnen de time-out."
_NETWORK_MESSAGE = "Kan GetAPI niet bereiken. Controleer je internetverbinding."


class GetApi(_Base[Response]):
    """Synchrone GetAPI-client.

    >>> from getapi import GetApi
    >>> getapi = GetApi("ga_live_...")
    >>> bedrijf = getapi.kvk.get("53743792")
    >>> bedrijf.data["naam"]

    Args:
        api_key: Je API-key (begint met ``ga_live_``). Zet hem nooit in code die bij anderen terechtkomt.
        base_url: Basis-URL van de API. Standaard ``https://api.getapi.nl``. Moet ``https`` zijn.
        timeout: Time-out in seconden, standaard 15. Wordt genegeerd als je zelf een ``http_client`` meegeeft.
        client_name: Naam van het kanaal waarmee je aanroept, bijvoorbeeld ``mijn-app/2.1``.
            Alleen voor je eigen herkenning in de logs.
        http_client: Eigen ``httpx.Client``, bijvoorbeeld voor proxy-instellingen of tests.
            Jij blijft verantwoordelijk voor het sluiten ervan.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        client_name: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        super().__init__(api_key, base_url=base_url, timeout=timeout, client_name=client_name)
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(timeout=timeout)

    def _call(self, request: Request) -> Response:
        try:
            res = self._http.request(request.method, self._url(request), **self._kwargs(request))
        except httpx.TimeoutException as e:
            raise ConnectionError(_TIMEOUT_MESSAGE) from e
        except httpx.TransportError as e:
            raise ConnectionError(_NETWORK_MESSAGE) from e
        return build_response(res, request.invalid_is_answer)

    def close(self) -> None:
        """Sluit de onderliggende verbinding (alleen als de client hem zelf heeft gemaakt)."""
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> GetApi:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        self.close()


class AsyncGetApi(_Base[Awaitable[Response]]):
    """Asynchrone GetAPI-client. Dezelfde methodes als ``GetApi``, maar gebruik ``await``.

    >>> async with AsyncGetApi("ga_live_...") as getapi:
    ...     bedrijf = await getapi.kvk.get("53743792")

    Ongeldige invoer (``InvalidArgumentError``) wordt al bij de aanroep gemeld, niet pas bij ``await``.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        client_name: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(api_key, base_url=base_url, timeout=timeout, client_name=client_name)
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=timeout)

    async def _call(self, request: Request) -> Response:
        try:
            res = await self._http.request(request.method, self._url(request), **self._kwargs(request))
        except httpx.TimeoutException as e:
            raise ConnectionError(_TIMEOUT_MESSAGE) from e
        except httpx.TransportError as e:
            raise ConnectionError(_NETWORK_MESSAGE) from e
        return build_response(res, request.invalid_is_answer)

    async def aclose(self) -> None:
        """Sluit de onderliggende verbinding (alleen als de client hem zelf heeft gemaakt)."""
        if self._owns_client:
            await self._http.aclose()

    async def __aenter__(self) -> AsyncGetApi:
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        await self.aclose()
