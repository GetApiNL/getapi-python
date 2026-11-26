from __future__ import annotations

import httpx
import pytest

from getapi import Response


def make(data: object) -> Response:
    return Response(data=data, status_code=200, credits_remaining=None, headers={})


def test_getitem_leest_uit_data() -> None:
    assert make({"naam": "X"})["naam"] == "X"


def test_getitem_ontbrekende_sleutel_geeft_keyerror() -> None:
    with pytest.raises(KeyError):
        make({})["naam"]


def test_get_met_default() -> None:
    res = make({"naam": "X"})
    assert res.get("naam") == "X"
    assert res.get("ontbreekt") is None
    assert res.get("ontbreekt", 5) == 5


def test_get_geeft_default_als_body_geen_object_is() -> None:
    assert make([1, 2]).get("naam", "x") == "x"
    assert make(None).get("naam") is None


def test_response_is_onveranderlijk() -> None:
    res = make({})
    with pytest.raises(AttributeError):
        res.status_code = 500  # type: ignore[misc]


def test_headers_zijn_niet_hoofdlettergevoelig() -> None:
    res = Response(data=None, status_code=200, credits_remaining=3, headers=httpx.Headers({"X-Credits-Remaining": "3"}))
    assert res.headers["x-credits-remaining"] == "3"
