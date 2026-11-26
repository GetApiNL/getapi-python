from __future__ import annotations

import json
from typing import Any, Callable

import pytest

from getapi import GetApi, InvalidArgumentError, UpstreamUnavailableError, ValidationError

from .helpers import Recorder

BASE = "https://api.getapi.nl"

ADDRESS = "postcode=3023KN&house_number=161&house_letter=C&house_number_addition=03"
BAG_ID = "0363200000218908"

Call = Callable[[GetApi], Any]

# (naam, aanroep, methode, verwachte url na de basis, verwachte JSON-body)
REQUESTS: list[tuple[str, Call, str, str, Any]] = [
    ("kvk.search", lambda c: c.kvk.search(naam="bol", kvk_nummer="53743792", page=2, size=10), "GET", "/v1/kvk/search?naam=bol&kvkNummer=53743792&page=2&size=10", None),
    ("kvk.search-nummer", lambda c: c.kvk.search(kvk_nummer=" 53743792 "), "GET", "/v1/kvk/search?kvkNummer=53743792", None),
    ("kvk.get", lambda c: c.kvk.get("53743792"), "GET", "/v1/kvk/53743792", None),
    ("kvk.get-geo", lambda c: c.kvk.get(" 53743792 ", geo=True), "GET", "/v1/kvk/53743792?geo=true", None),
    ("kvk.get-geo-false", lambda c: c.kvk.get("53743792", geo=False), "GET", "/v1/kvk/53743792?geo=false", None),
    ("kvk.validate", lambda c: c.kvk.validate(" 53743792 "), "POST", "/v1/kvk/validate", {"kvkNummer": "53743792"}),
    ("address.lookup", lambda c: c.address.lookup("3023 kn", 161, "C", "03"), "GET", f"/v1/kadaster/bag/address?{ADDRESS}", None),
    ("address.lookup-kaal", lambda c: c.address.lookup("3023KN", 161), "GET", "/v1/kadaster/bag/address?postcode=3023KN&house_number=161", None),
    ("address.suggest", lambda c: c.address.suggest("Hooidrift 1", 5), "GET", "/v1/kadaster/bag/address-suggest?q=Hooidrift+1&limit=5", None),
    ("address.by_id", lambda c: c.address.by_id(BAG_ID), "GET", f"/v1/kadaster/bag/id?id={BAG_ID}", None),
    ("address.postcode", lambda c: c.address.postcode("3023KN", 161), "GET", "/v1/lookup/postcode?postcode=3023KN&number=161", None),
    ("address.postcode-zonder-nummer", lambda c: c.address.postcode("3023KN"), "GET", "/v1/lookup/postcode?postcode=3023KN", None),
    ("property.woz_value", lambda c: c.property.woz_value("3023KN", 161, "C", "03"), "GET", f"/v1/property/woz-waarde?{ADDRESS}", None),
    ("property.woz_value-bag", lambda c: c.property.woz_value(bag_id=BAG_ID), "GET", f"/v1/property/woz-waarde?id={BAG_ID}", None),
    ("property.energy_label", lambda c: c.property.energy_label("3023KN", 161, "C", "03"), "GET", "/v1/property/energy-label?zipcode=3023KN&house_number=161&house_letter=C&house_number_addition=03", None),
    ("property.details", lambda c: c.property.details("3023KN", 161, "C", "03"), "GET", f"/v1/property/pandgegevens?{ADDRESS}", None),
    ("property.details_lite", lambda c: c.property.details_lite("3023KN", 161, "C", "03"), "GET", f"/v1/property/pandgegevens-lite?{ADDRESS}", None),
    ("validation.vat", lambda c: c.validation.vat("nl 8206.46.660-b01"), "POST", "/v1/validate/vat", {"vat_number": "NL820646660B01"}),
    ("validation.iban", lambda c: c.validation.iban("nl91 abna 0417 1643 00"), "POST", "/v1/validate/iban", {"iban": "NL91ABNA0417164300"}),
    ("validation.iban-bic", lambda c: c.validation.iban("NL91ABNA0417164300", "ABNANL2A"), "POST", "/v1/validate/iban", {"iban": "NL91ABNA0417164300", "bic": "ABNANL2A"}),
    ("validation.email", lambda c: c.validation.email(" a@b.nl "), "POST", "/v1/validate/email", {"email": "a@b.nl"}),
    ("validation.email_batch", lambda c: c.validation.email_batch(["a@b.nl", "c@d.nl"]), "POST", "/v1/validate/email/batch", {"emails": ["a@b.nl", "c@d.nl"]}),
    ("validation.email_batch-tuple", lambda c: c.validation.email_batch(("a@b.nl",)), "POST", "/v1/validate/email/batch", {"emails": ["a@b.nl"]}),
    ("validation.disposable_email", lambda c: c.validation.disposable_email("a@b.nl"), "POST", "/v1/validate/email/disposable", {"email": "a@b.nl"}),
    ("validation.dnsbl", lambda c: c.validation.dnsbl("1.2.3.4"), "POST", "/v1/validate/dnsbl", {"ip": "1.2.3.4"}),
    ("lookup.ip", lambda c: c.lookup.ip("8.8.8.8"), "GET", "/v1/lookup/ip?ip=8.8.8.8", None),
    ("lookup.dns_nameservers", lambda c: c.lookup.dns_nameservers("getapi.nl"), "GET", "/v1/lookup/dns/nameservers?domain=getapi.nl", None),
    ("lookup.dns_records", lambda c: c.lookup.dns_records("getapi.nl"), "GET", "/v1/lookup/dns/records?domain=getapi.nl", None),
    ("lookup.dns_records-type", lambda c: c.lookup.dns_records("getapi.nl", "mx"), "GET", "/v1/lookup/dns/records?domain=getapi.nl&type=MX", None),
    ("vehicle.get", lambda c: c.vehicle.get("ab-123-c"), "GET", "/v1/rdw/vehicle?license_plate=AB123C", None),
    ("sbi.index", lambda c: c.sbi.index(), "GET", "/v1/cbs/sbi", None),
    ("sbi.index-filter", lambda c: c.sbi.index(2, "62.01"), "GET", "/v1/cbs/sbi?level=2&parent_code=62.01", None),
    ("sbi.search", lambda c: c.sbi.search("software", 10), "GET", "/v1/cbs/sbi/search?q=software&limit=10", None),
    ("sbi.get", lambda c: c.sbi.get("62.01"), "GET", "/v1/cbs/sbi/62.01", None),
    ("dso.documents-coordinaten", lambda c: c.dso.documents(lat=52.37, lon=4.89), "GET", "/v1/dso/documents?lat=52.37&lon=4.89", None),
    ("dso.documents-adres", lambda c: c.dso.documents(postcode="3023 KN", huisnummer=161), "GET", "/v1/dso/documents?postcode=3023KN&huisnummer=161", None),
    ("dso.plans-coordinaten", lambda c: c.dso.plans(lat=0, lon=0), "GET", "/v1/dso/plans?lat=0&lon=0", None),
    ("dso.plans-adres", lambda c: c.dso.plans(postcode="3023KN", huisnummer=161), "GET", "/v1/dso/plans?postcode=3023KN&huisnummer=161", None),
    ("ndw.charge_points", lambda c: c.ndw.charge_points("Utrecht", "available", ["CCS", "Type2"], True, 2, 50), "GET", "/v1/ndw/laadpunten?city=Utrecht&status=available&connector_types%5B%5D=CCS&connector_types%5B%5D=Type2&beschikbaar=true&page=2&per_page=50", None),
    ("ndw.charge_points-kaal", lambda c: c.ndw.charge_points(), "GET", "/v1/ndw/laadpunten", None),
    ("ndw.charge_point", lambda c: c.ndw.charge_point("NL-ABC/1"), "GET", "/v1/ndw/laadpunten/NL-ABC%2F1", None),
    ("ndw.emission_zones", lambda c: c.ndw.emission_zones("zero_emission", "Utrecht", 1, 10), "GET", "/v1/ndw/emissiezones?zone_type=zero_emission&city=Utrecht&page=1&per_page=10", None),
    ("ndw.emission_zone", lambda c: c.ndw.emission_zone("abc"), "GET", "/v1/ndw/emissiezones/abc", None),
    ("ndw.truck_parking", lambda c: c.ndw.truck_parking("full", False, "A2", 3, 25), "GET", "/v1/ndw/truckparking?status=full&beschikbaar=false&road=A2&page=3&per_page=25", None),
    ("ndw.truck_parking_site", lambda c: c.ndw.truck_parking_site("abc"), "GET", "/v1/ndw/truckparking/abc", None),
    ("scraping.email", lambda c: c.scraping.email(" https://example.nl/contact "), "POST", "/v1/scraping/email", {"url": "https://example.nl/contact"}),
]  # fmt: skip


@pytest.mark.parametrize(("call", "method", "path", "body"), [pytest.param(c, m, p, b, id=n) for n, c, m, p, b in REQUESTS])
def test_bouwt_het_juiste_verzoek(client: GetApi, server: Recorder, call: Call, method: str, path: str, body: Any) -> None:
    server.body = {"ok": True}
    res = call(client)
    assert res.data == {"ok": True}
    assert server.last.method == method
    assert str(server.last.url).replace("%20", "+") == BASE + path
    if body is None:
        assert server.last.content == b""
    else:
        assert json.loads(server.last.content) == body


INVALID: list[tuple[str, Call]] = [
    ("kvk.search-niets", lambda c: c.kvk.search()),
    ("kvk.search-leeg", lambda c: c.kvk.search(naam="  ", kvk_nummer="")),
    ("kvk.search-size", lambda c: c.kvk.search(naam="x", size=11)),
    ("kvk.search-page", lambda c: c.kvk.search(naam="x", page=0)),
    ("kvk.search-type", lambda c: c.kvk.search(naam=5)),  # type: ignore[arg-type]
    ("kvk.search-nummer-type", lambda c: c.kvk.search(kvk_nummer=5)),  # type: ignore[arg-type]
    ("kvk.get-kort", lambda c: c.kvk.get("123")),
    ("kvk.get-letters", lambda c: c.kvk.get("1234567a")),
    ("kvk.get-int", lambda c: c.kvk.get(53743792)),  # type: ignore[arg-type]
    ("kvk.validate-int", lambda c: c.kvk.validate(53743792)),  # type: ignore[arg-type]
    ("address.postcode-ongeldig", lambda c: c.address.lookup("0123AB", 1)),
    ("address.postcode-type", lambda c: c.address.lookup(None, 1)),  # type: ignore[arg-type]
    ("address.huisnummer-nul", lambda c: c.address.lookup("3023KN", 0)),
    ("address.huisnummer-te-groot", lambda c: c.address.lookup("3023KN", 100000)),
    ("address.huisnummer-bool", lambda c: c.address.lookup("3023KN", True)),
    ("address.huisnummer-tekst", lambda c: c.address.lookup("3023KN", "161")),  # type: ignore[arg-type]
    ("address.letter-twee", lambda c: c.address.lookup("3023KN", 1, "ab")),
    ("address.letter-type", lambda c: c.address.lookup("3023KN", 1, 5)),  # type: ignore[arg-type]
    ("address.toevoeging-koppelteken", lambda c: c.address.lookup("3023KN", 1, None, "ab-12")),
    ("address.toevoeging-te-lang", lambda c: c.address.lookup("3023KN", 1, None, "12345")),
    ("address.suggest-kort", lambda c: c.address.suggest("a")),
    ("address.suggest-lang", lambda c: c.address.suggest("a" * 101)),
    ("address.suggest-type", lambda c: c.address.suggest(None)),  # type: ignore[arg-type]
    ("address.suggest-limit", lambda c: c.address.suggest("abc", 26)),
    ("address.by_id-kort", lambda c: c.address.by_id("123")),
    ("address.by_id-type", lambda c: c.address.by_id(363200000218908)),  # type: ignore[arg-type]
    ("address.postcode-nummer", lambda c: c.address.postcode("3023KN", 0)),
    ("property.woz-niets", lambda c: c.property.woz_value()),
    ("property.woz-alleen-postcode", lambda c: c.property.woz_value("3023KN")),
    ("property.woz-alleen-huisnummer", lambda c: c.property.woz_value(house_number=1)),
    ("property.woz-bag-en-adres", lambda c: c.property.woz_value("3023KN", 1, bag_id=BAG_ID)),
    ("property.woz-bag-ongeldig", lambda c: c.property.woz_value(bag_id="12")),
    ("property.energy-ongeldig", lambda c: c.property.energy_label("x", 1)),
    ("property.details-ongeldig", lambda c: c.property.details("3023KN", 0)),
    ("property.details_lite-ongeldig", lambda c: c.property.details_lite("3023KN", 1, "ab")),
    ("validation.vat-type", lambda c: c.validation.vat(None)),  # type: ignore[arg-type]
    ("validation.iban-type", lambda c: c.validation.iban(None)),  # type: ignore[arg-type]
    ("validation.iban-bic-type", lambda c: c.validation.iban("NL91ABNA0417164300", 5)),  # type: ignore[arg-type]
    ("validation.email-type", lambda c: c.validation.email(None)),  # type: ignore[arg-type]
    ("validation.email_batch-leeg", lambda c: c.validation.email_batch([])),
    ("validation.email_batch-te-veel", lambda c: c.validation.email_batch(["a@b.nl"] * 26)),
    ("validation.email_batch-tekst", lambda c: c.validation.email_batch("a@b.nl")),
    ("validation.email_batch-item", lambda c: c.validation.email_batch([5])),  # type: ignore[list-item]
    ("validation.disposable-type", lambda c: c.validation.disposable_email(None)),  # type: ignore[arg-type]
    ("validation.dnsbl-type", lambda c: c.validation.dnsbl(None)),  # type: ignore[arg-type]
    ("lookup.ip-type", lambda c: c.lookup.ip(None)),  # type: ignore[arg-type]
    ("lookup.dns_nameservers-type", lambda c: c.lookup.dns_nameservers(None)),  # type: ignore[arg-type]
    ("lookup.dns_records-type", lambda c: c.lookup.dns_records("getapi.nl", "ZZZ")),
    ("lookup.dns_records-recordtype-type", lambda c: c.lookup.dns_records("getapi.nl", 5)),  # type: ignore[arg-type]
    ("vehicle.leeg", lambda c: c.vehicle.get("")),
    ("vehicle.tekens", lambda c: c.vehicle.get("AB!123")),
    ("vehicle.type", lambda c: c.vehicle.get(None)),  # type: ignore[arg-type]
    ("sbi.index-niveau", lambda c: c.sbi.index(6)),
    ("sbi.index-niveau-bool", lambda c: c.sbi.index(True)),
    ("sbi.index-code", lambda c: c.sbi.index(parent_code="a b")),
    ("sbi.search-kort", lambda c: c.sbi.search("a")),
    ("sbi.search-limit", lambda c: c.sbi.search("abc", 101)),
    ("sbi.get-leeg", lambda c: c.sbi.get(" ")),
    ("dso.niets", lambda c: c.dso.documents()),
    ("dso.alleen-lat", lambda c: c.dso.documents(lat=1.0)),
    ("dso.alleen-lon", lambda c: c.dso.plans(lon=1.0)),
    ("dso.alleen-postcode", lambda c: c.dso.documents(postcode="3023KN")),
    ("dso.alleen-huisnummer", lambda c: c.dso.documents(huisnummer=1)),
    ("dso.lat-bereik", lambda c: c.dso.documents(lat=91, lon=0)),
    ("dso.lon-bereik", lambda c: c.dso.documents(lat=0, lon=-181)),
    ("dso.lat-type", lambda c: c.dso.documents(lat="1", lon=1)),  # type: ignore[arg-type]
    ("dso.lat-bool", lambda c: c.dso.documents(lat=True, lon=1)),
    ("dso.postcode-ongeldig", lambda c: c.dso.plans(postcode="x", huisnummer=1)),
    ("ndw.connector_types-tekst", lambda c: c.ndw.charge_points(connector_types="CCS")),
    ("ndw.charge_points-page", lambda c: c.ndw.charge_points(page=0)),
    ("ndw.charge_points-per_page", lambda c: c.ndw.charge_points(per_page=501)),
    ("ndw.charge_point-leeg", lambda c: c.ndw.charge_point("")),
    ("ndw.emission_zones-type", lambda c: c.ndw.emission_zones("onbekend")),
    ("ndw.emission_zone-leeg", lambda c: c.ndw.emission_zone("")),
    ("ndw.truck_parking-status", lambda c: c.ndw.truck_parking("onbekend")),
    ("ndw.truck_parking_site-type", lambda c: c.ndw.truck_parking_site(5)),  # type: ignore[arg-type]
    ("scraping.url-zonder-schema", lambda c: c.scraping.email("example.nl")),
    ("scraping.url-ftp", lambda c: c.scraping.email("ftp://example.nl")),
    ("scraping.url-type", lambda c: c.scraping.email(None)),  # type: ignore[arg-type]
]  # fmt: skip


@pytest.mark.parametrize("call", [pytest.param(c, id=n) for n, c in INVALID])
def test_ongeldige_invoer_wordt_gemeld_voor_het_versturen(client: GetApi, server: Recorder, call: Call) -> None:
    with pytest.raises(InvalidArgumentError):
        call(client)
    assert server.requests == []


@pytest.mark.parametrize(
    ("call", "validity_answer"),
    [
        (lambda c: c.validation.vat("NL000"), True),
        (lambda c: c.validation.iban("NL00"), True),
        (lambda c: c.validation.email("x"), True),
        (lambda c: c.kvk.validate("11111111"), True),
        (lambda c: c.validation.email_batch(["x"]), False),
        (lambda c: c.validation.disposable_email("x"), False),
        (lambda c: c.validation.dnsbl("x"), False),
        (lambda c: c.scraping.email("https://x.nl"), False),
    ],
    ids=["vat", "iban", "email", "kvk", "batch", "disposable", "dnsbl", "scraping"],
)
def test_422_is_alleen_een_antwoord_bij_controles(client: GetApi, server: Recorder, call: Call, validity_answer: bool) -> None:
    server.status = 422
    server.body = {"valid": False, "message": "nee"}
    if validity_answer:
        assert call(client).status_code == 422
    else:
        with pytest.raises(ValidationError):
            call(client)


def test_kvk_validate_503_is_upstream_fout(client: GetApi, server: Recorder) -> None:
    server.status = 503
    server.body = {"found": None, "valid": None, "retry_after": 5}
    with pytest.raises(UpstreamUnavailableError):
        client.kvk.validate("53743792")
