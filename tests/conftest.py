from __future__ import annotations

import httpx
import pytest

from getapi import AsyncGetApi, GetApi

from .helpers import Recorder


@pytest.fixture
def server() -> Recorder:
    return Recorder()


@pytest.fixture
def client(server: Recorder) -> GetApi:
    return GetApi("ga_live_test", http_client=httpx.Client(transport=httpx.MockTransport(server)))


@pytest.fixture
def async_client(server: Recorder) -> AsyncGetApi:
    return AsyncGetApi("ga_live_test", http_client=httpx.AsyncClient(transport=httpx.MockTransport(server)))
