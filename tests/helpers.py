from __future__ import annotations

from typing import Any, Callable

import httpx

from getapi import GetApi

Handler = Callable[[httpx.Request], httpx.Response]


class Recorder:
    """Een nepserver die alle verzoeken onthoudt en één vast antwoord geeft."""

    def __init__(
        self, status: int = 200, body: Any = None, headers: dict[str, str] | None = None, raw: str | None = None
    ) -> None:
        self.status = status
        self.body = {} if body is None else body
        self.headers = headers
        self.raw = raw
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.raw is not None:
            return httpx.Response(self.status, text=self.raw, headers=self.headers)
        return httpx.Response(self.status, json=self.body, headers=self.headers)

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]


def client_for(handler: Handler, **options: Any) -> GetApi:
    return GetApi("ga_live_test", http_client=httpx.Client(transport=httpx.MockTransport(handler)), **options)
