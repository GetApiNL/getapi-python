"""Het antwoord van een aanroep."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Response:
    """Een antwoord van de API.

    Attributes:
        data: De geparste JSON-body.
        status_code: HTTP-statuscode.
        credits_remaining: Resterende credits volgens de header ``X-Credits-Remaining``,
            alleen gevuld als de API die meestuurt.
        headers: Alle responseheaders. Namen zijn niet hoofdlettergevoelig.
    """

    data: Any
    status_code: int
    credits_remaining: int | None
    headers: Mapping[str, str]

    def __getitem__(self, key: str) -> Any:
        """Afkorting voor ``response.data[key]``."""
        return self.data[key]

    def get(self, key: str, default: Any = None) -> Any:
        """Afkorting voor ``response.data.get(key, default)``. Geeft ``default`` als de body geen object is."""
        if isinstance(self.data, dict):
            return self.data.get(key, default)
        return default
