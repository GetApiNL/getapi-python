"""Controleert de SDK tegen de OpenAPI-spec van GetAPI.

``openapi.json`` is een momentopname van https://getapi.nl/openapi.json. Vernieuw hem als de API verandert:
``curl -o tests/openapi.json https://getapi.nl/openapi.json``. Een nieuw endpoint laat ``test_elke_operatie_heeft_een_aanroep`` falen.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

import httpx
import pytest

from getapi import DEFAULT_BASE_URL, GetApi

from .helpers import Recorder

SPEC: dict[str, Any] = json.loads((Path(__file__).parent / "openapi.json").read_text())
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
BAG_ID = "0363200000218908"

Call = Callable[[GetApi], Any]

CALLS: dict[str, Call] = {
    "kadaster.bag.address": lambda c: c.address.lookup("3023KN", 161, "C", "03"),
    "kadaster.bag.address-suggest": lambda c: c.address.suggest("Hooidrift", 5),
    "kadaster.bag.id": lambda c: c.address.by_id(BAG_ID),
    "cbs.sbi": lambda c: c.sbi.index(2, "62.01"),
    "cbs.sbi.search": lambda c: c.sbi.search("software", 10),
    "cbs.sbi.detail": lambda c: c.sbi.get("62.01"),
    "lookup.dns.nameservers": lambda c: c.lookup.dns_nameservers("getapi.nl"),
    "lookup.dns.records": lambda c: c.lookup.dns_records("getapi.nl", "mx"),
    "validation.dnsbl": lambda c: c.validation.dnsbl("1.2.3.4"),
    "dso.documents": lambda c: c.dso.documents(lat=52.37, lon=4.89),
    "dso.plans": lambda c: c.dso.plans(postcode="3023KN", huisnummer=161),
    "validation.email": lambda c: c.validation.email("a@b.nl"),
    "validation.email.batch": lambda c: c.validation.email_batch(["a@b.nl"]),
    "validation.email.disposable": lambda c: c.validation.disposable_email("a@b.nl"),
    "lookup.postcode": lambda c: c.address.postcode("3023KN", 161),
    "validation.iban": lambda c: c.validation.iban("NL91ABNA0417164300", "ABNANL2A"),
    "lookup.ip": lambda c: c.lookup.ip("8.8.8.8"),
    "kvk.validate": lambda c: c.kvk.validate("53743792"),
    "kvk.search": lambda c: c.kvk.search(naam="bol", kvk_nummer="53743792", page=1, size=25),
    "kvk.detail": lambda c: c.kvk.get("53743792", geo=True),
    "ndw.laadpunten": lambda c: c.ndw.charge_points("Utrecht", "available", ["CCS"], True, 1, 50),
    "ndw.laadpunten.detail": lambda c: c.ndw.charge_point("abc"),
    "ndw.emissiezones": lambda c: c.ndw.emission_zones("low_emission", "Utrecht", 1, 50),
    "ndw.emissiezones.detail": lambda c: c.ndw.emission_zone("abc"),
    "ndw.truckparking": lambda c: c.ndw.truck_parking("available", True, "A2", 1, 50),
    "ndw.truckparking.detail": lambda c: c.ndw.truck_parking_site("abc"),
    "property.pandgegevens": lambda c: c.property.details("3023KN", 161, "C", "03"),
    "property.pandgegevens-lite": lambda c: c.property.details_lite("3023KN", 161, "C", "03"),
    "property.woz-waarde": lambda c: c.property.woz_value("3023KN", 161, "C", "03"),
    "rdw.vehicle": lambda c: c.vehicle.get("AB-123-C"),
    "property.energy-label": lambda c: c.property.energy_label("3023KN", 161, "C", "03"),
    "scraping.email": lambda c: c.scraping.email("https://example.nl"),
    "validation.vat": lambda c: c.validation.vat("NL820646660B01"),
}

# Extra aanroepen die de andere kant van een alternatief in de spec dekken.
ALTERNATIVES: dict[str, Call] = {
    "property.woz-waarde": lambda c: c.property.woz_value(bag_id=BAG_ID),
    "dso.documents": lambda c: c.dso.documents(postcode="3023KN", huisnummer=161),
    "dso.plans": lambda c: c.dso.plans(lat=52.37, lon=4.89),
    "kvk.search": lambda c: c.kvk.search(naam="bol"),
}


def resolve(node: Any) -> Any:
    if isinstance(node, dict) and "$ref" in node:
        target: Any = SPEC
        for part in node["$ref"][2:].split("/"):
            target = target[part]
        return resolve(target)
    return node


def operations() -> dict[str, tuple[str, str, dict[str, Any]]]:
    out: dict[str, tuple[str, str, dict[str, Any]]] = {}
    for path, item in SPEC["paths"].items():
        for method, op in item.items():
            if method in HTTP_METHODS:
                out[op["operationId"]] = (method.upper(), path, op)
    return out


OPERATIONS = operations()


def path_regex(template: str) -> re.Pattern[str]:
    parts = re.split(r"\{[^}]+\}", template)
    return re.compile("^" + "[^/]+".join(re.escape(part) for part in parts) + "$")


def schema_types(schema: dict[str, Any]) -> list[str]:
    kind = schema.get("type", [])
    return kind if isinstance(kind, list) else [kind]


def check_value(value: Any, schema: dict[str, Any], where: str) -> None:
    """Controleer een waarde tegen het (eenvoudige) schema uit de spec."""
    schema = resolve(schema)
    types = schema_types(schema)
    if isinstance(value, bool):
        assert "boolean" in types, f"{where}: boolean niet toegestaan"
    elif isinstance(value, int):
        assert {"integer", "number"} & set(types), f"{where}: geheel getal niet toegestaan"
    elif isinstance(value, float):
        assert "number" in types, f"{where}: getal niet toegestaan"
    elif isinstance(value, str):
        assert "string" in types, f"{where}: tekst niet toegestaan"
        if "pattern" in schema:
            assert re.search(schema["pattern"], value), f"{where}: {value!r} past niet op {schema['pattern']}"
        assert len(value) >= schema.get("minLength", 0), f"{where}: te kort"
        assert len(value) <= schema.get("maxLength", 10**9), f"{where}: te lang"
    elif isinstance(value, list):
        assert "array" in types, f"{where}: lijst niet toegestaan"
        assert schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 10**9), f"{where}: aantal items"
        for item in value:
            check_value(item, schema.get("items", {}), where)
        return
    if "enum" in schema:
        assert value in schema["enum"], f"{where}: {value!r} staat niet in {schema['enum']}"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        assert value >= schema.get("minimum", float("-inf")), f"{where}: te klein"
        assert value <= schema.get("maximum", float("inf")), f"{where}: te groot"


def check_request(operation_id: str, request: httpx.Request) -> None:
    method, template, op = OPERATIONS[operation_id]
    assert request.method == method
    assert path_regex(template).match(request.url.path), f"{request.url.path} past niet op {template}"

    params = [resolve(p) for p in [*SPEC["paths"][template].get("parameters", []), *op.get("parameters", [])]]
    query = {p["name"]: p for p in params if p["in"] == "query"}

    sent: dict[str, list[str]] = {}
    for key, value in request.url.params.multi_items():
        sent.setdefault(key, []).append(value)
    assert set(sent) <= set(query), f"onbekende queryparameters: {set(sent) - set(query)}"
    for name, spec in query.items():
        if spec.get("required"):
            assert name in sent, f"verplichte parameter {name} ontbreekt"
    for name, values in sent.items():
        schema = resolve(query[name]["schema"])
        types = schema_types(schema)
        for text in values:
            check_value(coerce(text, types), schema if "array" not in types else schema["items"], name)

    path_params = [p for p in params if p["in"] == "path"]
    assert len(path_params) == template.count("{")

    body_schema = (op.get("requestBody") or {}).get("content", {}).get("application/json", {}).get("schema")
    if body_schema is None:
        assert not request.content
        return
    body_schema = resolve(body_schema)
    body = json.loads(request.content)
    assert set(body) <= set(body_schema["properties"]), f"onbekende bodyvelden: {set(body) - set(body_schema['properties'])}"
    for name in body_schema.get("required", []):
        assert name in body, f"verplicht veld {name} ontbreekt"
    for name, value in body.items():
        check_value(value, body_schema["properties"][name], name)


def coerce(text: str, types: list[str]) -> Any:
    if "boolean" in types and text in {"true", "false"}:
        return text == "true"
    if "integer" in types and re.fullmatch(r"-?\d+", text):
        return int(text)
    if "number" in types and re.fullmatch(r"-?\d+(\.\d+)?", text):
        return float(text)
    return text


def test_elke_operatie_heeft_een_aanroep() -> None:
    assert set(CALLS) == set(OPERATIONS), f"ontbrekend: {set(OPERATIONS) - set(CALLS)}, onbekend: {set(CALLS) - set(OPERATIONS)}"


def test_spec_gebruikt_de_verwachte_authenticatie() -> None:
    assert SPEC["components"]["securitySchemes"]["ApiKeyAuth"] == {"type": "apiKey", "in": "header", "name": "X-Api-Key"}


def test_standaard_server_komt_overeen_met_de_spec() -> None:
    assert [s["url"] for s in SPEC["servers"]] == [DEFAULT_BASE_URL]


@pytest.mark.parametrize("operation_id", sorted(OPERATIONS))
def test_verzoek_voldoet_aan_de_spec(client: GetApi, server: Recorder, operation_id: str) -> None:
    CALLS[operation_id](client)
    assert len(server.requests) == 1
    check_request(operation_id, server.last)


@pytest.mark.parametrize("operation_id", sorted(ALTERNATIVES))
def test_alternatieve_aanroep_voldoet_aan_de_spec(client: GetApi, server: Recorder, operation_id: str) -> None:
    ALTERNATIVES[operation_id](client)
    check_request(operation_id, server.last)
