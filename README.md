# GetAPI voor Python

[![PyPI](https://img.shields.io/pypi/v/getapi.svg)](https://pypi.org/project/getapi/)
[![Tests](https://github.com/GetApiNL/getapi-python/actions/workflows/tests.yml/badge.svg)](https://github.com/GetApiNL/getapi-python/actions/workflows/tests.yml)
[![Licentie](https://img.shields.io/pypi/l/getapi.svg)](LICENSE)

Officiële client voor [GetAPI.nl](https://getapi.nl/?utm_source=pypi&utm_medium=sdk&utm_campaign=python-readme): Nederlandse bedrijfs-, adres-, pand- en controlegegevens via één API-key. KVK, BAG, BTW (VIES), WOZ, energielabel, RDW en meer.

GetAPI verzamelt en publiceert de data zelf, onder een eigen domein, API en account. Eén key is genoeg.

- Synchroon (`GetApi`) en asynchroon (`AsyncGetApi`)
- Volledig getypeerd (`py.typed`, `mypy --strict`), Python 3.8 of hoger
- Eén afhankelijkheid: [httpx](https://www.python-httpx.org/)

## Installeren

```bash
pip install getapi
```

[Maak gratis een API-key aan](https://getapi.nl/register?utm_source=pypi&utm_medium=sdk&utm_campaign=python-readme&utm_content=install).

## Gebruiken

```python
import os
from getapi import GetApi

getapi = GetApi(os.environ["GETAPI_KEY"])

bedrijf = getapi.kvk.get("53743792")
print(bedrijf.data["naam"])
print(bedrijf.credits_remaining)  # alleen gevuld als de API X-Credits-Remaining meestuurt
```

Elke aanroep geeft een `Response` met `data`, `status_code`, `credits_remaining` en `headers`. `response["naam"]` is een afkorting voor `response.data["naam"]`.

```python
# Bedrijf zoeken op naam
getapi.kvk.search(naam="bol", size=10)

# Adres opzoeken. Splits het adres in losse delen:
# "Hooidrift 161C-03" wordt huisnummer 161, letter C en toevoeging 03.
getapi.address.lookup("3023KN", 161, house_letter="C", house_number_addition="03")

# BTW-nummer controleren: een ongeldig nummer geeft valid=False, geen fout.
getapi.validation.vat("NL820646660B01")

# WOZ-waarde en energielabel
getapi.property.woz_value("3023KN", 161)
getapi.property.energy_label("3023KN", 161)

# WOZ-waarde via BAG-id in plaats van adres
getapi.property.woz_value(bag_id="0363200000218908")

# Kenteken
getapi.vehicle.get("AB-123-C")

# KVK-gegevens met coördinaten en BAG-id's van het adres
getapi.kvk.get("53743792", geo=True)

# E-mailadressen uit een webpagina halen
getapi.scraping.email("https://example.nl/contact")
```

### Asynchroon

Dezelfde methodes, met `await`:

```python
import asyncio
from getapi import AsyncGetApi


async def main():
    async with AsyncGetApi("ga_live_...") as getapi:
        bedrijf = await getapi.kvk.get("53743792")
        print(bedrijf["naam"])


asyncio.run(main())
```

## Overzicht

| Resource | Methodes |
| --- | --- |
| `kvk` | `search`, `get`, `validate` |
| `address` | `lookup`, `suggest`, `by_id`, `postcode` |
| `property` | `woz_value`, `energy_label`, `details`, `details_lite` |
| `validation` | `vat`, `iban`, `email`, `email_batch`, `disposable_email`, `dnsbl` |
| `lookup` | `ip`, `dns_nameservers`, `dns_records` |
| `vehicle` | `get` |
| `sbi` | `index`, `search`, `get` |
| `dso` | `documents`, `plans` |
| `ndw` | `charge_points`, `charge_point`, `emission_zones`, `emission_zone`, `truck_parking`, `truck_parking_site` |
| `scraping` | `email` |

De volledige API-documentatie staat op [getapi.nl/docs](https://getapi.nl/docs).

## Opties

```python
GetApi(
    "ga_live_...",
    base_url="https://api.getapi.nl",  # standaard, moet https zijn
    timeout=15.0,  # seconden, standaard
    client_name="mijn-app/2.1",  # optioneel, voor herkenning in je logs
    http_client=httpx.Client(...),  # optioneel, voor proxy of tests
)
```

Geef je zelf een `http_client` mee, dan gelden zijn time-out en instellingen en sluit jij hem ook zelf.

Alle GET-aanroepen accepteren `idempotency_key=`. Dezelfde key binnen 10 minuten geeft hetzelfde antwoord en rekent hooguit één keer af. Handig als je een aanroep opnieuw doet na een time-out:

```python
getapi.property.woz_value("3023KN", 161, idempotency_key="order-4711")
```

## Fouten afhandelen

Alle fouten erven van `GetApiError`.

| Klasse | Wanneer |
| --- | --- |
| `AuthError` | 401 of 403: key ontbreekt of is ongeldig |
| `CreditsExhaustedError` | 402: credits op, met `topup_url` |
| `NotFoundError` | 404: bijvoorbeeld een onbekend KVK-nummer |
| `ValidationError` | 422: ongeldige invoer, met `errors` per veld |
| `RateLimitError` | 429: te veel verzoeken, met `retry_after` (seconden) |
| `UpstreamUnavailableError` | 503: een bron achter de API is tijdelijk niet beschikbaar |
| `ConnectionError` | netwerkfout of time-out |
| `InvalidArgumentError` | ongeldige invoer, gemeld voordat er iets is verstuurd |

```python
from getapi import NotFoundError, CreditsExhaustedError

try:
    getapi.kvk.get("00000000")
except NotFoundError:
    ...  # onbekend KVK-nummer
except CreditsExhaustedError as e:
    print(e.topup_url)
```

Let op: `getapi.ConnectionError` is een eigen klasse en vervangt dus niet de ingebouwde `ConnectionError`. Importeer hem met een alias als je beide gebruikt.

## Ontwikkelen

```bash
pip install -e ".[dev]"
pytest          # tests, inclusief controle tegen tests/openapi.json, vereist 100% dekking
ruff check .    # lint
ruff format .   # opmaak
mypy            # typecontrole (strict)
```

`tests/openapi.json` is een momentopname van [getapi.nl/openapi.json](https://getapi.nl/openapi.json). Vernieuw hem met
`curl -o tests/openapi.json https://getapi.nl/openapi.json`; een nieuw endpoint laat de contracttest dan falen tot de SDK het ondersteunt.

## Totstandkoming
Deze package is met behulp van AI geschreven en voor zover mogelijk door GetApi.nl beoordeeld. De code wordt gecontroleerd door een testsuite met 100% dekking, door een contracttest tegen de [OpenAPI-spec](https://getapi.nl/openapi.json) en door ruff en mypy --strict.
Zie je iets dat niet klopt? Open een [issue](https://github.com/GetApiNL/getapi-python/issues).

## Over GetAPI

GetAPI is een label van [WD Noord](https://wdnoord.nl/?utm_source=pypi&utm_medium=sdk&utm_campaign=getapi-python-readme&utm_content=footer).

## Licentie

[MIT](LICENSE)
