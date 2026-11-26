"""De resources van de GetAPI-client.

Elke methode bouwt een verzoek en geeft het door aan de client. Bij ``GetApi`` krijg je meteen
een ``Response`` terug, bij ``AsyncGetApi`` een awaitable (gebruik ``await``).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, Callable, Generic, TypeVar
from urllib.parse import quote

from ._transport import Request
from .errors import InvalidArgumentError

R = TypeVar("R")
Call = Callable[[Request], R]

_POSTCODE = re.compile(r"[1-9][0-9]{3}\s?[A-Za-z]{2}")
_HOUSE_LETTER = re.compile(r"[A-Za-z]")
_HOUSE_ADDITION = re.compile(r"[A-Za-z0-9]{1,4}")
_BAG_ID = re.compile(r"[0-9]{16}")
_KVK_NUMBER = re.compile(r"[0-9]{8}")
_SBI_CODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.]{0,11}")
_LICENSE_PLATE = re.compile(r"[A-Z0-9]{4,9}")
_WEB_URL = re.compile(r"https?://\S+", re.IGNORECASE)

_KVK_PAGE_SIZES = (5, 10, 25, 50, 75)
_DNS_RECORD_TYPES = ("A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "PTR", "SRV", "ALL")
_EMISSION_ZONE_TYPES = ("low_emission", "zero_emission")
_TRUCK_PARKING_STATUSES = ("available", "full", "closed", "unknown")
_MAX_BATCH_EMAILS = 25


def _text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise InvalidArgumentError(f"{name} moet tekst zijn.")
    return value.strip()


def _integer(value: object, name: str, minimum: int, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or (maximum is not None and value > maximum):
        upper = f" tot {maximum}" if maximum is not None else " of hoger"
        raise InvalidArgumentError(f"{name} moet een geheel getal van {minimum}{upper} zijn.")
    return value


def _optional_integer(value: object, name: str, minimum: int, maximum: int | None = None) -> int | None:
    return None if value is None else _integer(value, name, minimum, maximum)


def _postcode(value: object) -> str:
    postcode = _text(value, "De postcode")
    if not _POSTCODE.fullmatch(postcode):
        raise InvalidArgumentError("Een postcode bestaat uit 4 cijfers en 2 letters, bijvoorbeeld 3023KN.")
    return postcode.replace(" ", "").upper()


def _house_number(value: object) -> int:
    return _integer(value, "Het huisnummer", 1, 99999)


def _house_letter(value: object) -> str | None:
    if value is None:
        return None
    letter = _text(value, "De huisletter")
    if not _HOUSE_LETTER.fullmatch(letter):
        raise InvalidArgumentError("De huisletter moet precies één letter zijn.")
    return letter


def _house_addition(value: object) -> str | None:
    if value is None:
        return None
    addition = _text(value, "De toevoeging")
    if not _HOUSE_ADDITION.fullmatch(addition):
        raise InvalidArgumentError("De toevoeging mag maximaal 4 letters of cijfers bevatten, zonder koppelteken.")
    return addition


def _address(
    postcode: object,
    house_number: object,
    house_letter: object,
    house_number_addition: object,
    *,
    postcode_key: str = "postcode",
) -> dict[str, Any]:
    return {
        postcode_key: _postcode(postcode),
        "house_number": _house_number(house_number),
        "house_letter": _house_letter(house_letter),
        "house_number_addition": _house_addition(house_number_addition),
    }


def _bag_id(value: object) -> str:
    bag_id = _text(value, "Het BAG-id")
    if not _BAG_ID.fullmatch(bag_id):
        raise InvalidArgumentError("Een BAG-id bestaat uit 16 cijfers.")
    return bag_id


def _query(value: object) -> str:
    if not isinstance(value, str) or not 2 <= len(value) <= 100:
        raise InvalidArgumentError("De zoektekst moet 2 tot 100 tekens lang zijn.")
    return value


def _paging(page: object, per_page: object) -> dict[str, Any]:
    return {
        "page": _optional_integer(page, "De pagina", 1),
        "per_page": _optional_integer(per_page, "Het aantal per pagina", 1, 500),
    }


def _one_of(value: str | None, name: str, allowed: Sequence[str]) -> str | None:
    if value is not None and value not in allowed:
        raise InvalidArgumentError(f"{name} moet een van deze zijn: {', '.join(allowed)}.")
    return value


def _path_id(value: object, name: str) -> str:
    text = _text(value, name)
    if not text:
        raise InvalidArgumentError(f"{name} mag niet leeg zijn.")
    return quote(text, safe="")


def _get(path: str, params: dict[str, Any], idempotency_key: str | None) -> Request:
    return Request("GET", path, params=params, idempotency_key=idempotency_key)


def _post(path: str, body: dict[str, Any], *, invalid_is_answer: bool) -> Request:
    return Request("POST", path, body=body, invalid_is_answer=invalid_is_answer)


class _Resource(Generic[R]):
    def __init__(self, call: Call[R]) -> None:
        self._call = call


class Kvk(_Resource[R]):
    """KVK-handelsregister: zoeken, details en controleren."""

    def search(
        self,
        naam: str | None = None,
        kvk_nummer: str | None = None,
        page: int | None = None,
        size: int | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> R:
        """Zoek bedrijven in het handelsregister. Geef ``naam`` of ``kvk_nummer`` mee (minstens één).

        ``size`` mag 5, 10, 25, 50 of 75 zijn.
        """
        naam = _text(naam, "De bedrijfsnaam") if naam is not None else None
        kvk_nummer = _text(kvk_nummer, "Het KVK-nummer") if kvk_nummer is not None else None
        if not naam and not kvk_nummer:
            raise InvalidArgumentError("Geef minstens een bedrijfsnaam (naam) of KVK-nummer (kvk_nummer) op.")
        if size is not None and size not in _KVK_PAGE_SIZES:
            raise InvalidArgumentError("size moet 5, 10, 25, 50 of 75 zijn.")
        params = {"naam": naam, "kvkNummer": kvk_nummer, "page": _optional_integer(page, "De pagina", 1), "size": size}
        return self._call(_get("/v1/kvk/search", params, idempotency_key))

    def get(self, kvk_nummer: str, geo: bool | None = None, *, idempotency_key: str | None = None) -> R:
        """Haal de gegevens van één bedrijf op via het KVK-nummer (8 cijfers).

        Met ``geo=True`` komen ook de coördinaten en BAG-id's van het adres mee.
        """
        nummer = _text(kvk_nummer, "Het KVK-nummer")
        if not _KVK_NUMBER.fullmatch(nummer):
            raise InvalidArgumentError("Een KVK-nummer bestaat uit 8 cijfers.")
        return self._call(_get(f"/v1/kvk/{nummer}", {"geo": geo}, idempotency_key))

    def validate(self, kvk_nummer: str) -> R:
        """Controleer of een KVK-nummer bestaat. Een onbekend nummer geeft ``valid: false``, geen fout."""
        body = {"kvkNummer": _text(kvk_nummer, "Het KVK-nummer")}
        return self._call(_post("/v1/kvk/validate", body, invalid_is_answer=True))


class Address(_Resource[R]):
    """BAG-adressen: opzoeken, suggesties en BAG-id."""

    def lookup(
        self,
        postcode: str,
        house_number: int,
        house_letter: str | None = None,
        house_number_addition: str | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> R:
        """Zoek een adres op in de BAG.

        Splits het adres in losse delen: "Hooidrift 161C-03" wordt huisnummer 161, letter C en toevoeging 03.
        """
        params = _address(postcode, house_number, house_letter, house_number_addition)
        return self._call(_get("/v1/kadaster/bag/address", params, idempotency_key))

    def suggest(self, query: str, limit: int | None = None, *, idempotency_key: str | None = None) -> R:
        """Adressuggesties terwijl iemand typt (zoektekst van 2 tot 100 tekens, limiet 1 tot 25)."""
        params = {"q": _query(query), "limit": _optional_integer(limit, "De limiet", 1, 25)}
        return self._call(_get("/v1/kadaster/bag/address-suggest", params, idempotency_key))

    def by_id(self, bag_id: str, *, idempotency_key: str | None = None) -> R:
        """Zoek een adres op via het BAG-id (16 cijfers)."""
        return self._call(_get("/v1/kadaster/bag/id", {"id": _bag_id(bag_id)}, idempotency_key))

    def postcode(self, postcode: str, number: int | None = None, *, idempotency_key: str | None = None) -> R:
        """Zoek op postcode, optioneel met huisnummer."""
        params = {"postcode": _postcode(postcode), "number": _optional_integer(number, "Het huisnummer", 1, 99999)}
        return self._call(_get("/v1/lookup/postcode", params, idempotency_key))


class Property(_Resource[R]):
    """Pandgegevens: WOZ-waarde, energielabel en pandinformatie."""

    def woz_value(
        self,
        postcode: str | None = None,
        house_number: int | None = None,
        house_letter: str | None = None,
        house_number_addition: str | None = None,
        *,
        bag_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> R:
        """WOZ-waarde van een adres, of van een BAG-nummeraanduiding via ``bag_id``.

        Geef ``postcode`` met ``house_number`` op, of alleen ``bag_id``.
        """
        if bag_id is not None:
            if any(part is not None for part in (postcode, house_number, house_letter, house_number_addition)):
                raise InvalidArgumentError("Geef een BAG-id op of een adres, niet allebei.")
            params: dict[str, Any] = {"id": _bag_id(bag_id)}
        else:
            if postcode is None or house_number is None:
                raise InvalidArgumentError("Geef een postcode en huisnummer op, of een BAG-id.")
            params = _address(postcode, house_number, house_letter, house_number_addition)
        return self._call(_get("/v1/property/woz-waarde", params, idempotency_key))

    def energy_label(
        self,
        postcode: str,
        house_number: int,
        house_letter: str | None = None,
        house_number_addition: str | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> R:
        """Geregistreerd energielabel van een adres (bron: EP-Online van RVO)."""
        params = _address(postcode, house_number, house_letter, house_number_addition, postcode_key="zipcode")
        return self._call(_get("/v1/property/energy-label", params, idempotency_key))

    def details(
        self,
        postcode: str,
        house_number: int,
        house_letter: str | None = None,
        house_number_addition: str | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> R:
        """Gecombineerde pandgegevens: BAG, energielabel, WOZ-waarde, bestemmingsplan en omgeving."""
        params = _address(postcode, house_number, house_letter, house_number_addition)
        return self._call(_get("/v1/property/pandgegevens", params, idempotency_key))

    def details_lite(
        self,
        postcode: str,
        house_number: int,
        house_letter: str | None = None,
        house_number_addition: str | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> R:
        """Lichte variant van de pandgegevens, met minder velden."""
        params = _address(postcode, house_number, house_letter, house_number_addition)
        return self._call(_get("/v1/property/pandgegevens-lite", params, idempotency_key))


class Validation(_Resource[R]):
    """Controles: BTW, IBAN, e-mail en IP-blacklists."""

    def vat(self, vat_number: str) -> R:
        """Controleer een BTW-nummer bij VIES. Een ongeldig nummer geeft ``valid: false``, geen fout."""
        number = re.sub(r"[\s.\-]+", "", _text(vat_number, "Het BTW-nummer")).upper()
        return self._call(_post("/v1/validate/vat", {"vat_number": number}, invalid_is_answer=True))

    def iban(self, iban: str, bic: str | None = None) -> R:
        """Controleer een IBAN, optioneel samen met een BIC."""
        body = {"iban": re.sub(r"\s+", "", _text(iban, "De IBAN")).upper()}
        if bic:
            body["bic"] = _text(bic, "De BIC")
        return self._call(_post("/v1/validate/iban", body, invalid_is_answer=True))

    def email(self, email: str) -> R:
        """Controleer of een e-mailadres geldig en bereikbaar is. Een ongeldig adres geeft ``valid: false``."""
        body = {"email": _text(email, "Het e-mailadres")}
        return self._call(_post("/v1/validate/email", body, invalid_is_answer=True))

    def email_batch(self, emails: Sequence[str]) -> R:
        """Controleer maximaal 25 e-mailadressen in één keer."""
        if isinstance(emails, str) or not 1 <= len(emails) <= _MAX_BATCH_EMAILS:
            raise InvalidArgumentError("Geef 1 tot 25 e-mailadressen op, als lijst.")
        body = {"emails": [_text(email, "Elk e-mailadres") for email in emails]}
        return self._call(_post("/v1/validate/email/batch", body, invalid_is_answer=False))

    def disposable_email(self, email: str) -> R:
        """Controleer of een e-mailadres van een wegwerpdienst is."""
        body = {"email": _text(email, "Het e-mailadres")}
        return self._call(_post("/v1/validate/email/disposable", body, invalid_is_answer=False))

    def dnsbl(self, ip: str) -> R:
        """Controleer of een IP-adres op een DNS-blacklist staat."""
        return self._call(_post("/v1/validate/dnsbl", {"ip": _text(ip, "Het IP-adres")}, invalid_is_answer=False))


class Lookup(_Resource[R]):
    """Opzoeken: IP-adres en DNS."""

    def ip(self, ip: str, *, idempotency_key: str | None = None) -> R:
        """Gegevens over een IP-adres."""
        return self._call(_get("/v1/lookup/ip", {"ip": _text(ip, "Het IP-adres")}, idempotency_key))

    def dns_nameservers(self, domain: str, *, idempotency_key: str | None = None) -> R:
        """Nameservers van een domein."""
        return self._call(_get("/v1/lookup/dns/nameservers", {"domain": _text(domain, "Het domein")}, idempotency_key))

    def dns_records(self, domain: str, record_type: str | None = None, *, idempotency_key: str | None = None) -> R:
        """DNS-records van een domein. ``record_type`` mag A, AAAA, CNAME, MX, NS, TXT, SOA, PTR, SRV of ALL zijn."""
        kind = None
        if record_type is not None:
            kind = _one_of(_text(record_type, "Het recordtype").upper(), "record_type", _DNS_RECORD_TYPES)
        params = {"domain": _text(domain, "Het domein"), "type": kind}
        return self._call(_get("/v1/lookup/dns/records", params, idempotency_key))


class Vehicle(_Resource[R]):
    """RDW-voertuiggegevens."""

    def get(self, license_plate: str, *, idempotency_key: str | None = None) -> R:
        """Voertuiggegevens op kenteken (met of zonder streepjes)."""
        plate = re.sub(r"[\s-]+", "", _text(license_plate, "Het kenteken")).upper()
        if not _LICENSE_PLATE.fullmatch(plate):
            raise InvalidArgumentError("Dit is geen geldig kenteken.")
        return self._call(_get("/v1/rdw/vehicle", {"license_plate": plate}, idempotency_key))


class Sbi(_Resource[R]):
    """CBS SBI-codes (bedrijfsindeling)."""

    def index(self, level: int | None = None, parent_code: str | None = None, *, idempotency_key: str | None = None) -> R:
        """Lijst SBI-codes, optioneel gefilterd op niveau (1 tot 5) of bovenliggende code."""
        if parent_code is not None and not _SBI_CODE.fullmatch(_text(parent_code, "De bovenliggende code")):
            raise InvalidArgumentError("Dit is geen geldige SBI-code.")
        params = {"level": _optional_integer(level, "Het niveau", 1, 5), "parent_code": parent_code}
        return self._call(_get("/v1/cbs/sbi", params, idempotency_key))

    def search(self, query: str, limit: int | None = None, *, idempotency_key: str | None = None) -> R:
        """Zoek SBI-codes op tekst (2 tot 100 tekens, limiet 1 tot 100)."""
        params = {"q": _query(query), "limit": _optional_integer(limit, "De limiet", 1, 100)}
        return self._call(_get("/v1/cbs/sbi/search", params, idempotency_key))

    def get(self, code: str, *, idempotency_key: str | None = None) -> R:
        """Eén SBI-code ophalen."""
        return self._call(_get(f"/v1/cbs/sbi/{_path_id(code, 'De SBI-code')}", {}, idempotency_key))


class Dso(_Resource[R]):
    """Omgevingsloket (DSO): documenten en plannen bij een locatie."""

    @staticmethod
    def _location(lat: float | None, lon: float | None, postcode: str | None, huisnummer: int | None) -> dict[str, Any]:
        if (lat is None) != (lon is None):
            raise InvalidArgumentError("Geef lat en lon samen op.")
        if (postcode is None) != (huisnummer is None):
            raise InvalidArgumentError("Geef postcode en huisnummer samen op.")
        if lat is None and postcode is None:
            raise InvalidArgumentError("Geef een locatie op: lat en lon, of postcode en huisnummer.")
        params: dict[str, Any] = {}
        if lat is not None and lon is not None:
            for value, name, limit in ((lat, "lat", 90), (lon, "lon", 180)):
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not -limit <= value <= limit:
                    raise InvalidArgumentError(f"{name} moet een getal tussen -{limit} en {limit} zijn.")
            params.update(lat=lat, lon=lon)
        if postcode is not None:
            params.update(postcode=_postcode(postcode), huisnummer=_house_number(huisnummer))
        return params

    def documents(
        self,
        lat: float | None = None,
        lon: float | None = None,
        postcode: str | None = None,
        huisnummer: int | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> R:
        """Documenten bij een locatie: geef ``lat`` en ``lon`` op, of ``postcode`` en ``huisnummer``."""
        return self._call(_get("/v1/dso/documents", self._location(lat, lon, postcode, huisnummer), idempotency_key))

    def plans(
        self,
        lat: float | None = None,
        lon: float | None = None,
        postcode: str | None = None,
        huisnummer: int | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> R:
        """Plannen bij een locatie: geef ``lat`` en ``lon`` op, of ``postcode`` en ``huisnummer``."""
        return self._call(_get("/v1/dso/plans", self._location(lat, lon, postcode, huisnummer), idempotency_key))


class Ndw(_Resource[R]):
    """NDW-verkeersdata: laadpunten, emissiezones en truckparkeerplaatsen."""

    def charge_points(
        self,
        city: str | None = None,
        status: str | None = None,
        connector_types: Sequence[str] | None = None,
        available: bool | None = None,
        page: int | None = None,
        per_page: int | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> R:
        """Laadpunten voor elektrische voertuigen."""
        if isinstance(connector_types, str):
            raise InvalidArgumentError("connector_types moet een lijst zijn.")
        params = {
            "city": city,
            "status": status,
            "connector_types[]": list(connector_types) if connector_types is not None else None,
            "beschikbaar": available,
            **_paging(page, per_page),
        }
        return self._call(_get("/v1/ndw/laadpunten", params, idempotency_key))

    def charge_point(self, charge_point_id: str, *, idempotency_key: str | None = None) -> R:
        """Eén laadpunt ophalen."""
        return self._call(_get(f"/v1/ndw/laadpunten/{_path_id(charge_point_id, 'Het id')}", {}, idempotency_key))

    def emission_zones(
        self,
        zone_type: str | None = None,
        city: str | None = None,
        page: int | None = None,
        per_page: int | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> R:
        """Milieuzones en zero-emissiezones. ``zone_type`` is ``low_emission`` of ``zero_emission``."""
        params = {"zone_type": _one_of(zone_type, "zone_type", _EMISSION_ZONE_TYPES), "city": city, **_paging(page, per_page)}
        return self._call(_get("/v1/ndw/emissiezones", params, idempotency_key))

    def emission_zone(self, emission_zone_id: str, *, idempotency_key: str | None = None) -> R:
        """Eén emissiezone ophalen."""
        return self._call(_get(f"/v1/ndw/emissiezones/{_path_id(emission_zone_id, 'Het id')}", {}, idempotency_key))

    def truck_parking(
        self,
        status: str | None = None,
        available: bool | None = None,
        road: str | None = None,
        page: int | None = None,
        per_page: int | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> R:
        """Parkeerplaatsen voor vrachtwagens. ``status`` is ``available``, ``full``, ``closed`` of ``unknown``."""
        params = {
            "status": _one_of(status, "status", _TRUCK_PARKING_STATUSES),
            "beschikbaar": available,
            "road": road,
            **_paging(page, per_page),
        }
        return self._call(_get("/v1/ndw/truckparking", params, idempotency_key))

    def truck_parking_site(self, truck_parking_id: str, *, idempotency_key: str | None = None) -> R:
        """Eén truckparkeerplaats ophalen."""
        return self._call(_get(f"/v1/ndw/truckparking/{_path_id(truck_parking_id, 'Het id')}", {}, idempotency_key))


class Scraping(_Resource[R]):
    """Gegevens uit webpagina's halen."""

    def email(self, url: str) -> R:
        """Haal e-mailadressen uit de HTML van een webpagina. Geeft ``found: false`` en een lege lijst als er geen zijn."""
        address = _text(url, "De URL")
        if not _WEB_URL.fullmatch(address):
            raise InvalidArgumentError("De URL moet met http:// of https:// beginnen.")
        return self._call(_post("/v1/scraping/email", {"url": address}, invalid_is_answer=False))
