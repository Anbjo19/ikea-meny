#!/usr/bin/env python3
"""
fetch_menu.py
=============

Henter menydata fra IKEA sitt interne food-API (samme data som vises på
https://www.ikea.com/no/no/food/salesareas/<salesarea>/) og skriver dem ut
som en ryddig menu-data.json som skjermvisningen (menu.html) leser.

Bakgrunn / hvordan dette funker
-------------------------------
IKEA sin restaurant-side er en Next.js-side. Den henter menyen sin fra en
intern JSON-rute:

    https://www.ikea.com/<marked>/<språk>/food/_next/data/<buildId>/salesareas/<salesarea>.json?salesarea=<salesarea>

<buildId> endrer seg hver gang IKEA deployer siden på nytt, så vi kan ikke
hardkode den — scriptet henter derfor HTML-siden først og leser ut
gjeldende buildId derfra, akkurat slik nettleseren din gjør.

Denne JSON-en inneholder IKKE "commercial label" (kampanje-/salgstekst).
Det feltet ligger bare på hvert enkelt produkts detaljside
(.../salesareas/<salesarea>/<productId>.json). Scriptet kan hente det med
et ekstra kall per rett hvis du legger på --labels (av som standard,
siden feltet så og si alltid er tomt — se heller `isNew`, som er et ekte
flagg IKEA selv bruker for å markere nyheter, og som skjermen bruker til
"nyhet"-slideet).

Hver rett kan ha to priser: vanlig pris ("RegularSalesUnitPrice") og
IKEA Family-pris ("IKEAFamilySalesUnitPrice") — de fleste retter har bare
vanlig pris, noen få (typisk kaffe/te) har begge. Scriptet henter begge
når de finnes.

`isBti` er IKEA sitt eget flagg for retter som får den gule/røde
prislappen ("Budget"/"BTI") på ikea.com — samme visuelle stil som
menu.html gjenbruker for disse rettene.

Allergener hentes fra `item.allergens` (inneholder) og
`item.allergensTracesOf` (kan inneholde spor av) på hver rett, oversatt
til norske navn via IKEA sin egen kodeliste (`pageProps.allergens`).
Ingen ekstra kall nødvendig — dataene ligger allerede i menylisten.

IKEA merker enkelte retter som "Tradisjonell svensk spesialitet" eller
"En typisk svensk klassiker" — men putter teksten inn som en vanlig
setning i selve beskrivelsen, ikke som et eget flagg. Scriptet kjenner
igjen disse setningene, fjerner dem fra beskrivelsen og setter i stedet
`isSwedishClassic: true`, slik at skjermen kan vise et lite svensk flagg
i stedet for å skrive det ut som tekst.

IKEA sitt API har ingen egen markering for vegetar/vegansk — bare
allergener og kategorier finnes som filtre på nettsiden deres.

Denne JSON-en har heller INGEN CORS-header (Access-Control-Allow-Origin),
så den kan ikke hentes direkte fra JavaScript i en nettside som ikke
kjører på ikea.com. Derfor kjøres dette scriptet på en maskin (f.eks. den
som driver skjermen, eller en liten server) med vanlig serverside-nettverk,
og skriver resultatet til en lokal fil som skjermsiden leser fra samme
origin.

Bruk
----
    python3 fetch_menu.py
    python3 fetch_menu.py --salesarea restaurant --store 091
    python3 fetch_menu.py --labels             # hent også kampanjetekst (tregere, ekstra kall per rett)

Flere butikker fra samme utrulling av menu.html
-------------------------------------------------
Skal én og samme menu.html brukes til skjermer i flere butikker (i stedet
for én fast fil per skjerm), kjør scriptet én gang per butikk med --out
satt til et butikk-spesifikt filnavn:

    python3 fetch_menu.py --store 091 --out menu-data-091.json
    python3 fetch_menu.py --store 095 --out menu-data-095.json

Eller, enklest: kjør med --all-stores, så genereres én fil per butikk i
STORES (alle IKEA Norge-varehus med restaurant) i ett jafs, pluss en
stores.json med butikklisten:

    python3 fetch_menu.py --all-stores

Dette gjør bare ÉTT kall for selve menylisten (den er ikke butikk-
spesifikk — hver rett har sin egen excludedStores-liste), og filtrerer den
lokalt én gang per butikk, så det er ikke tregere enn nødvendig selv om
det skrives 8 filer.

Pek så hver skjerm sin nettleser til riktig URL med ?store=<kode>, f.eks.
http://<server>/menu.html?store=091 — menu.html leser da menu-data-091.json
i stedet for menu-data.json. Uten ?store i URL-en brukes menu-data.json som
før (fint for en skjerm som alltid står i samme butikk).

Kjør scriptet periodisk (f.eks. hver natt) med cron / Windows Task
Scheduler / launchd. IKEA cacher selv denne dataen i ca. 48 timer, så det
er ingen vits i å kjøre det oftere enn et par ganger i døgnet.

    # cron-eksempel: hver dag kl 04:30
    30 4 * * * cd /sti/til/ikea-meny && /usr/bin/python3 fetch_menu.py >> fetch_menu.log 2>&1
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
import time
import urllib.error
import urllib.request

MARKET = "no"
LANG = "no"
BASE = f"https://www.ikea.com/{MARKET}/{LANG}/food"

# Alle IKEA Norge-butikker med restaurant, med butikkoder verifisert direkte
# mot IKEA sin egen "Bytt varehus"-velger på restaurant-siden (26.08.2026).
STORES = {
    "091": "IKEA Slependen",
    "095": "IKEA Furuset",
    "441": "IKEA Åsane",
    "371": "IKEA Leangen",
    "126": "IKEA Forus",
    "390": "IKEA Ringsaker",
    "007": "IKEA Sørlandet",
    "722": "IKEA Karl Johan",
}

# Rekkefølgen kategoriene vises i på skjermen. Kategorier som dukker opp i
# dataene men ikke står her, havner til slutt (i den rekkefølgen IKEA gir dem).
CATEGORY_ORDER = [
    "breakfast",          # Frokost
    "mains",               # Hovedretter
    "childrens-menu",      # Barnemeny
    "sandwiches-wraps",    # Smørbrød og wraps
    "cold-starter",        # Kalde tallerkener og forretter
    "salads",              # Salater
    "side-dishes",         # Tilbehør
    "desserts-pastries",   # Bakverk, desserter og småkaker
    "hot-beverages",       # Varme drikker
]

HEADERS = {
    # En vanlig nettleser-UA gjør at vi får akkurat samme respons som
    # nettleseren din ville fått.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "no,nb;q=0.9,en;q=0.8",
}


def http_get(url: str, timeout: float = 15.0, retries: int = 3) -> bytes:
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            last_err = e
            print(f"  forsøk {attempt}/{retries} feilet for {url}: {e}", file=sys.stderr)
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"Klarte ikke hente {url}: {last_err}")


def get_build_id(salesarea: str) -> str:
    """Henter gjeldende Next.js build-id fra den vanlige HTML-siden."""
    html = http_get(f"{BASE}/salesareas/{salesarea}/").decode("utf-8", "replace")
    m = re.search(r'"buildId"\s*:\s*"([^"]+)"', html)
    if not m:
        raise RuntimeError(
            "Fant ikke buildId i IKEA-siden — de kan ha endret sidestrukturen."
        )
    return m.group(1)


def get_listing(build_id: str, salesarea: str) -> dict:
    url = f"{BASE}/_next/data/{build_id}/salesareas/{salesarea}.json?salesarea={salesarea}"
    raw = http_get(url)
    return json.loads(raw)


def get_commercial_label(build_id: str, salesarea: str, product_id: str) -> str | None:
    """Henter kampanje-/salgstekst ("commercial label") for ett produkt.

    Feltet heter `commercialTexts` på produktets detalj-JSON og er tomt for
    de fleste retter — det brukes typisk til kampanjer ("Nyhet", sesong-
    tilbud og lignende). Vi plukker ut norsk tekst hvis den finnes, ellers
    første tilgjengelige.
    """
    url = (
        f"{BASE}/_next/data/{build_id}/salesareas/{salesarea}/{product_id}.json"
        f"?salesarea={salesarea}&productId={product_id}"
    )
    try:
        raw = http_get(url, retries=2)
    except RuntimeError:
        return None
    data = json.loads(raw)
    texts = data.get("pageProps", {}).get("product", {}).get("item", {}).get(
        "commercialTexts", []
    )
    if not texts:
        return None
    # Vanlig IKEA-form er en liste med {"languageCode": "no", "text": "..."}.
    # Vi er defensive siden feltet så og si aldri er fylt ut i praksis.
    candidates = []
    for t in texts:
        if isinstance(t, str):
            candidates.append(t)
        elif isinstance(t, dict):
            txt = t.get("text") or t.get("value") or t.get("name")
            if txt:
                if t.get("languageCode") == LANG:
                    return txt
                candidates.append(txt)
    return candidates[0] if candidates else None


def format_price(price: float | None) -> str | None:
    if price is None:
        return None
    if float(price).is_integer():
        return f"{int(price)},-"
    return f"{price:.2f}".replace(".", ",")


def extract_prices(entry: dict) -> tuple[float | None, float | None]:
    """Plukker ut (vanlig pris, IKEA Family-pris) fra en rett.

    IKEA lister flere pristyper per rett (vanlig, spis-her, ansatt osv.).
    Vi bryr oss om to av dem:
      - RegularSalesUnitPrice      -> vanlig pris
      - IKEAFamilySalesUnitPrice   -> medlemspris (finnes ikke på alle retter)
    """
    sales_prices = (entry.get("itemSalesPrice") or {}).get("salesPrices") or []
    regular = None
    family = None
    for p in sales_prices:
        if p.get("type") == "RegularSalesUnitPrice" and regular is None:
            regular = p.get("priceInclTax")
        elif p.get("type") == "IKEAFamilySalesUnitPrice" and family is None:
            family = p.get("priceInclTax")
    if regular is None and sales_prices:
        # Fallback: ingen "RegularSalesUnitPrice" funnet, bruk første pris i lista.
        regular = sales_prices[0].get("priceInclTax")
    return regular, family


def build_allergen_dict(listing: dict) -> dict[str, str]:
    """paramCode -> norsk allergen-navn (f.eks. ALLERGEN_CODE_MILK -> "Melk"),
    hentet fra den globale kodelisten i pageProps.allergens."""
    entries = listing.get("pageProps", {}).get("allergens", []) or []
    return {
        e.get("paramCode"): e.get("description")
        for e in entries
        if e.get("paramCode") and e.get("description")
    }


def extract_allergens(item: dict, allergen_dict: dict[str, str]) -> tuple[list[str], list[str]]:
    """Plukker ut (allergener retten inneholder, allergener den kan inneholde
    spor av) for en rett, oversatt til norske navn.

    `item.allergens` er allergenene retten faktisk inneholder.
    `item.allergensTracesOf` er allergener den kan inneholde spor av
    (kryssforurensning), og listes derfor separat.
    """
    contains: list[str] = []
    for a in item.get("allergens", []) or []:
        code = a.get("paramCode") or a.get("code")
        label = allergen_dict.get(code, code)
        if label and label not in contains:
            contains.append(label)

    traces: list[str] = []
    for a in item.get("allergensTracesOf", []) or []:
        code = a.get("paramCode") or a.get("code")
        label = allergen_dict.get(code, code)
        if label and label not in traces:
            traces.append(label)

    return contains, traces


# Setninger IKEA vever inn i `shortDescription` for å markere en rett som en
# tradisjonell svensk spesialitet, i stedet for å bruke et eget datafelt.
# Vi kjenner dem igjen og fjerner dem fra beskrivelsen — skjermen viser et
# lite svensk flagg i stedet (se isSwedishClassic under).
SWEDISH_CLASSIC_PATTERNS = [
    re.compile(r"\s*Tradisjonell svensk spesialitet\.?\s*$", re.IGNORECASE),
    re.compile(r"\s*Tradisjonell svensk (?:rett|matrett)\.?\s*$", re.IGNORECASE),
    re.compile(r"^\s*En typisk svensk klassiker\.?\s*", re.IGNORECASE),
]


def strip_swedish_classic_marker(description: str) -> tuple[str, bool]:
    is_classic = False
    for pattern in SWEDISH_CLASSIC_PATTERNS:
        new_description, n = pattern.subn("", description)
        if n:
            is_classic = True
            description = new_description.strip()
    return description, is_classic


def fetch_listing(salesarea: str) -> tuple[str, dict]:
    """Henter buildId + selve menylisten (ikke butikk-filtrert ennå).

    Denne er felles for alle butikker — hver rett har sin egen
    excludedStores-liste, så vi trenger bare hente den én gang selv om vi
    skal bygge menu-data for flere butikker (se --all-stores).
    """
    print(f"Henter buildId for salesarea={salesarea} ...")
    build_id = get_build_id(salesarea)
    print(f"  buildId = {build_id}")

    print("Henter menyliste ...")
    listing = get_listing(build_id, salesarea)
    reduced_products = listing.get("pageProps", {}).get("reducedProducts", [])
    print(f"  {len(reduced_products)} retter totalt (før butikk-filter)")
    return build_id, listing


def build_menu_from_listing(
    build_id: str,
    listing: dict,
    salesarea: str,
    store_code: str | None,
    fetch_labels: bool,
) -> dict:
    reduced_products = listing.get("pageProps", {}).get("reducedProducts", [])
    allergen_dict = build_allergen_dict(listing)

    items = []
    for entry in reduced_products:
        item = entry.get("item", {})
        excluded = {s.get("code") for s in item.get("excludedStores", []) or []}
        if store_code and store_code in excluded:
            continue  # denne retten selges ikke i den valgte butikken

        sales_areas = item.get("salesAreas") or []
        categories = sales_areas[0].get("categories") if sales_areas else []
        category = categories[0] if categories else {"slug": "ovrig", "name": "Øvrig"}

        regular_price, family_price = extract_prices(entry)

        label = None
        if fetch_labels:
            label = get_commercial_label(build_id, salesarea, item.get("id"))

        image = item.get("mainImage") or {}
        image_url = (image.get("sizes") or {}).get("500w") or image.get("url")

        raw_description = re.sub(r"\s+", " ", (item.get("shortDescription") or "")).strip()
        description, is_swedish_classic = strip_swedish_classic_marker(raw_description)

        allergens, allergens_traces = extract_allergens(item, allergen_dict)

        items.append(
            {
                "categorySlug": category.get("slug", "ovrig"),
                "category": category.get("name", "Øvrig"),
                "name": (item.get("title") or "").strip(),
                "description": description,
                "isSwedishClassic": is_swedish_classic,
                "regularPrice": regular_price,
                "regularPriceFormatted": format_price(regular_price),
                "familyPrice": family_price,
                "familyPriceFormatted": format_price(family_price),
                "isNew": bool(item.get("showAsNew")),
                "isBti": bool(item.get("showAsBti")),
                "commercialLabel": label,
                "allergens": allergens,
                "allergensTraces": allergens_traces,
                "image": image_url,
            }
        )

    print(f"  {len(items)} retter etter butikk-filter")

    grouped: dict[str, list[dict]] = {}
    for it in items:
        grouped.setdefault(it["categorySlug"], []).append(it)

    ordered_slugs = [s for s in CATEGORY_ORDER if s in grouped]
    ordered_slugs += [s for s in grouped.keys() if s not in ordered_slugs]

    categories = [
        {"slug": slug, "name": grouped[slug][0]["category"], "items": grouped[slug]}
        for slug in ordered_slugs
    ]

    return {
        "generatedAt": datetime.datetime.now(datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "salesarea": salesarea,
        "store": {"code": store_code, "name": STORES.get(store_code) if store_code else None},
        "categories": categories,
    }


def build_menu(salesarea: str, store_code: str | None, fetch_labels: bool) -> dict:
    """Bekvemmelighetsfunksjon: henter listen og bygger menyen for én butikk
    i ett kall. Bruk fetch_listing() + build_menu_from_listing() direkte
    hvis du skal bygge for flere butikker fra samme liste (se --all-stores
    i main())."""
    build_id, listing = fetch_listing(salesarea)
    return build_menu_from_listing(build_id, listing, salesarea, store_code, fetch_labels)


def main():
    parser = argparse.ArgumentParser(description="Hent IKEA-restaurantmeny til menu-data.json")
    parser.add_argument(
        "--salesarea",
        default="restaurant",
        help="restaurant, bistro eller swedishfoodmarket (standard: restaurant)",
    )
    parser.add_argument(
        "--store",
        default="091",
        help=(
            "Butikkode brukt til å filtrere bort retter som ikke selges i "
            "denne butikken (excludedStores). Standard 091 = IKEA Oslo - "
            "Slependen. Sett til tom streng for ingen filtrering."
        ),
    )
    parser.add_argument(
        "--labels",
        action="store_true",
        help=(
            "Hent også kampanjetekst ('commercial label') — krever ett ekstra "
            "kall per rett, så det tar en del lenger tid. Av som standard "
            "siden feltet nesten alltid er tomt; bruk heller `isNew`."
        ),
    )
    parser.add_argument(
        "--out", default="menu-data.json", help="Filnavn for resultatet (standard menu-data.json)"
    )
    parser.add_argument(
        "--all-stores",
        action="store_true",
        help=(
            "Bygg menu-data-<kode>.json for ALLE butikkene i STORES (ett "
            "kall for selve menylisten, gjenbrukt for hver butikk) og skriv "
            "en stores.json med butikklisten, til bruk for en butikk-"
            "velger i menu.html. Overstyrer --store og --out."
        ),
    )
    args = parser.parse_args()

    if args.all_stores:
        build_id, listing = fetch_listing(args.salesarea)
        for code, name in STORES.items():
            print(f"\n== {code} ({name}) ==")
            menu = build_menu_from_listing(
                build_id, listing, args.salesarea, code, fetch_labels=args.labels
            )
            out_name = f"menu-data-{code}.json"
            with open(out_name, "w", encoding="utf-8") as f:
                json.dump(menu, f, ensure_ascii=False, indent=2)
            n_items = sum(len(c["items"]) for c in menu["categories"])
            print(f"  Skrev {out_name}: {n_items} retter i {len(menu['categories'])} kategorier.")

        stores_list = [{"code": code, "name": name} for code, name in STORES.items()]
        with open("stores.json", "w", encoding="utf-8") as f:
            json.dump({"stores": stores_list}, f, ensure_ascii=False, indent=2)
        print(f"\nSkrev stores.json: {len(stores_list)} butikker.")
        return

    store_code = args.store or None
    menu = build_menu(args.salesarea, store_code, fetch_labels=args.labels)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(menu, f, ensure_ascii=False, indent=2)

    n_items = sum(len(c["items"]) for c in menu["categories"])
    print(f"Skrev {args.out}: {n_items} retter i {len(menu['categories'])} kategorier.")


if __name__ == "__main__":
    main()
