# Wijzigingen

Dit project volgt [Semantic Versioning](https://semver.org/lang/nl/).

## 1.0.0

- Eerste versie: KVK, adressen (BAG), pandgegevens (WOZ, energielabel), controles (BTW, IBAN, e-mail, DNSBL), opzoeken (IP, DNS), RDW, CBS SBI, DSO, NDW en e-mailadressen uit webpagina's (`scraping.email`).
- Synchrone en asynchrone client op basis van httpx, volledig getypeerd (`mypy --strict`). `await` op `AsyncGetApi` is ook voor typecheckers correct.
- `kvk.get(..., geo=True)` en `property.woz_value(bag_id=...)`.
- Invoer wordt gecontroleerd voordat er iets wordt verstuurd (postcode, huisnummer, KVK-nummer, BAG-id, kenteken, locatie, enzovoort); verkeerde typen geven `InvalidArgumentError`.
- Een 422 bij BTW-, IBAN-, e-mail- en KVK-controles is alleen een antwoord als de body een `valid`-veld heeft; een echte invoerfout blijft een `ValidationError`.
- `base_url` moet `https` zijn (behalve voor localhost), zodat de API-key niet onversleuteld verstuurd wordt.
- `Response.headers` is hoofdletterongevoelig.
- Vereist Python 3.10 of hoger.
