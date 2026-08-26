# IKEA-restaurantmeny til skjerm

Viser hovedkategori, navn, beskrivelse, IKEA Family-pris, vanlig pris,
allergener og eventuell kampanjetekst ("commercial label") for rettene i
IKEA-restauranten, hentet fra samme interne API som
https://www.ikea.com/no/no/food/salesareas/restaurant/ selv bruker — satt
opp som én statisk tavle for en portrettskjerm i inngangen, med et eget
"nyhet"-overtak for retter IKEA selv har merket som nye.

## Filer

- `fetch_menu.py` – henter fersk menydata fra IKEA og skriver `menu-data.json`.
- `menu.html` – selve skjermvisningen. Portrettformat, viser **alle**
  rettene samtidig på én tavle (ingen rullering mellom kategorier),
  fordelt i to spalter. Hver rett vises med navn, beskrivelse under
  tittelen, IKEA Family-pris (blå, når den finnes), vanlig pris (svart,
  fet) og — når IKEA har oppgitt det — en liten kursivert linje med
  allergener ("Inneholder: gluten, melk — kan inneholde spor av: sesam").
  Retter IKEA selv omtaler som en tradisjonell svensk spesialitet får et
  lite svensk flagg ved siden av navnet i stedet for at det skrives ut
  som tekst. Header med "Hej! Smaklig måltid" øverst og IKEA-logoen nede
  i høyre hjørne (med luft rundt tilsvarende egen høyde). Skalerer
  automatisk ned hvis menyen en dag blir for lang til å få plass. Med
  jevne mellomrom (hvert 25. sekund) tar en rett IKEA har merket som
  "nyhet" over hele skjermen i noen sekunder, med bilde, navn,
  beskrivelse og pris — deretter tilbake til tavlen. Vises ingenting hvis
  ingen retter er merket som nye.
- `menu-data.json` – ferdig eksempeldata (IKEA Slependen, hentet nå) så
  visningen fungerer med det samme. Blir overskrevet neste gang du kjører
  `fetch_menu.py`.
- `assets/ikea-logo.svg` – IKEA sin egen logo, hentet direkte fra
  ikea.com (`global/assets/logos/brand/ikea.svg`).
- `assets/ikea-labels.css` – ekte fargetokens og CSS hentet fra ikea.com
  sitt eget stilark (Skapa-designsystemet): riktig IKEA-blå, gult, og
  ikke minst den gule/røde prislappen de bruker på enkelte retter (se
  "Ekte IKEA-prislapp" under). Lastes automatisk inn av `menu.html`.
- `download-ikea-assets.sh` – lite script du kjører selv (se punkt 4
  under) som laster ned skriften "Noto IKEA" fra ikea.com til
  `assets/fonts/`.
- `.github/workflows/update-menu.yml` – GitHub Actions-workflow som
  kjører `fetch_menu.py --all-stores` hver natt og committer ny
  menydata, hvis du hoster med GitHub Pages (se "Hosting med GitHub
  Pages + Actions" under).

## Hvorfor et eget script, og ikke bare en nettside som henter direkte?

IKEA sitt API sender ikke noen CORS-header, så en nettleser på en annen
side enn ikea.com får ikke lov til å lese svaret direkte av
sikkerhetsgrunner. Det er derfor `fetch_menu.py` som gjør selve
IKEA-kallet (vanlig serverkall, ingen CORS-begrensning der), og
`menu.html` som bare leser den lokale `menu-data.json`-filen. Dette gjør
også visningen mer robust: skjermen slutter ikke å vise meny selv om
IKEA sin side skulle være nede en kort stund.

## Oppsett

1. **Test at scriptet fungerer:**

   ```bash
   python3 fetch_menu.py
   ```

   Standard er satt til `IKEA Oslo - Slependen` (butikkode `091`) og
   `salesarea=restaurant`. Bytt butikk med `--store <kode>`, eller se
   Bistro-menyen med `--salesarea bistro`. Kjør `python3 fetch_menu.py -h`
   for alle valg.

2. **Server mappen lokalt** (menu.html må hentes over http://, ikke som
   `file://`, for at `fetch()` skal fungere pålitelig i alle nettlesere):

   ```bash
   python3 -m http.server 8080
   ```

   Pek skjermens nettleser (i kiosk-/fullskjermmodus) mot
   `http://<maskinens-ip>:8080/menu.html`.

3. **Hold dataene ferske** – legg `fetch_menu.py` inn i en periodisk jobb.
   IKEA cacher selv menyen sin i ca. 48 timer, så én til to kjøringer i
   døgnet er mer enn nok:

   ```cron
   # kl 04:30 hver natt
   30 4 * * * cd /sti/til/ikea-meny && /usr/bin/python3 fetch_menu.py >> fetch_menu.log 2>&1
   ```

   (Windows: sett opp samme kommando som en "Basic Task" i Task Scheduler.)

   `menu.html` sjekker selv om `menu-data.json` er oppdatert hvert 5.
   minutt og bytter til ny meny uten at du trenger å laste siden på nytt,
   og laster hele siden på nytt hver 6. time som en ekstra sikkerhet for
   en skjerm som står på døgnet rundt.

4. **(Flere butikker fra samme `menu.html`)** Skal samme utrulling
   betjene skjermer i flere butikker, kjør scriptet én gang per butikk
   med et butikk-spesifikt filnavn — eller kjør `--all-stores` for å
   generere alle på én gang (se "Alle butikker på én gang" lenger ned):

   ```bash
   python3 fetch_menu.py --store 091 --out menu-data-091.json
   python3 fetch_menu.py --store 095 --out menu-data-095.json
   # ...eller rett og slett:
   python3 fetch_menu.py --all-stores
   ```

   Pek så hver skjerm mot riktig butikk med `?store=<kode>` i URL-en,
   f.eks. `http://<server>/menu.html?store=091` — da leses
   `menu-data-091.json` i stedet for `menu-data.json`. Uten `?store` i
   URL-en (som i alle eksemplene ellers i denne filen) brukes
   `menu-data.json` som normalt, fint for en skjerm som alltid står i
   samme butikk.

5. **(Valgfritt) Hent den ekte IKEA-fonten "Noto IKEA":**

   ```bash
   chmod +x download-ikea-assets.sh
   ./download-ikea-assets.sh
   ```

   Dette må kjøres fra din egen Terminal (ikke via Claude) siden det
   trenger vanlig internett-tilgang til ikea.com. Scriptet laster ned de
   4 fontfilene (normal/fet, med/uten kursiv, kun "latin"-varianten — det
   er den IKEA selv bruker for norsk tekst) til `assets/fonts/`.
   `menu.html` bruker fonten automatisk så snart filene finnes der; helt
   fint å la stå — da faller den bare tilbake til en systemfont som
   ligner (Helvetica/Arial) inntil du kjører scriptet.

## Hosting med GitHub Pages + Actions (anbefalt for permanent drift)

Skjermen(e) trenger en ekte, alltid-tilgjengelig nettadresse — vanlig
FTP/webhotell holder ikke alene, siden `fetch_menu.py` faktisk må *kjøres*
med jevne mellomrom, ikke bare ligge som filer. Løsningen under er gratis,
krever ingen egen server, og løser nettopp det: GitHub Pages viser selve
siden, og GitHub Actions kjører `fetch_menu.py` for deg hver natt.

**Engangsoppsett:**

1. Opprett en gratis konto på [github.com](https://github.com) hvis du
   ikke har en fra før.
2. Opprett et nytt repository — **New repository** — kall det f.eks.
   `ikea-meny`, og la det stå som **Public** (nødvendig for at GitHub
   Pages skal være gratis; menydataene er uansett IKEA sin egen, allerede
   offentlige informasjon).
3. Last opp alt innholdet i denne mappen til repoet — enklest via
   **Add file → Upload files** i nettleseren og dra inn hele mappen, eller
   med git fra Terminal:

   ```bash
   cd ~/Downloads/IKEAfood
   git init
   git add .
   git commit -m "Første versjon"
   git branch -M main
   git remote add origin https://github.com/<brukernavn>/ikea-meny.git
   git push -u origin main
   ```

4. Slå på GitHub Pages: **Settings → Pages** i repoet → under "Build and
   deployment" velg **Deploy from a branch** → branch **main**, mappe
   **/ (root)** → **Save**. Etter et minutt eller to er siden din på
   `https://<brukernavn>.github.io/ikea-meny/`.
5. Gi selve oppdateringsjobben lov til å skrive tilbake til repoet:
   **Settings → Actions → General** → under "Workflow permissions" velg
   **Read and write permissions** → **Save**. (Uten dette får ikke
   `.github/workflows/update-menu.yml` — som allerede ligger i mappen —
   lov til å committe ny menydata.)
6. Trigg den første kjøringen manuelt så du har data med en gang, i
   stedet for å vente til kl 04:30: fanen **Actions** → velg workflowen
   **"Oppdater IKEA-menydata"** → **Run workflow**. Etter ca. et minutt
   bør `menu-data-091.json` osv. og `stores.json` dukke opp i repoet.

**Ferdig.** Pek hver skjerm mot sin egen butikk, f.eks.:

```
https://<brukernavn>.github.io/ikea-meny/menu.html?store=441
```

Workflowen i `.github/workflows/update-menu.yml` kjører
`fetch_menu.py --all-stores` automatisk hver natt og committer ny data —
ingen server å vedlikeholde, ingen cron-jobb å administrere selv. Du kan
også trigge den manuelt når som helst fra **Actions**-fanen (f.eks. rett
etter at du har endret noe i `menu.html` eller vil ha fersk data med en
gang).

Vil du endre selve visningen (`menu.html`) eller scriptet senere, gjør du
det i repoet (last opp nye filer på samme måte, eller `git push` på
nytt) — GitHub Pages oppdaterer seg automatisk innen kort tid.

## Ekte IKEA-prislapp ("BTI")

På ikea.com får enkelte retter en gul prislapp med et lite rødt "skygge"-
merke — IKEA sitt eget "BTI"-flagg (samme flagg som `showAsBti` i
food-API-et). `fetch_menu.py` henter dette som `isBti`, og `menu.html`
gjenbruker IKEA sin egen CSS for det (se `assets/ikea-labels.css`) — så
prislappen ser nøyaktig ut som på ikea.com, ikke en tilnærming.

## Allergener

Hver rett i IKEA sine data har en liste over allergener den inneholder
(`item.allergens`) og eventuelt allergener den kan inneholde spor av ved
kryssforurensning (`item.allergensTracesOf`) — begge er kodede
(`ALLERGEN_CODE_MILK` osv.) og `fetch_menu.py` oversetter dem til norske
navn ("Melk" osv.) via IKEA sin egen kodeliste, som ligger i samme
API-svar. Ingen ekstra kall trengs. `menu.html` viser dette som en liten,
kursiv, grå linje rett under beskrivelsen — vises kun for retter som
faktisk har allergener registrert.

Merk: IKEA sitt API har ingen egen markering for vegetar/vegansk — det
finnes verken som et datafelt eller et filter på ikea.com sin egen
restaurantside, bare allergener og menykategorier.

## Tradisjonelle svenske retter

IKEA markerer enkelte retter (typisk kjøttboller, rekesmørbrød,
kanelbolle) som en tradisjonell svensk spesialitet — men gjør det ved å
veve en setning ("Tradisjonell svensk spesialitet." / "En typisk svensk
klassiker.") inn i selve beskrivelsesteksten, ikke som et eget flagg.
`fetch_menu.py` kjenner igjen disse setningene, fjerner dem fra
beskrivelsen og setter i stedet `isSwedishClassic: true` — `menu.html`
viser da et lite svensk flagg ved siden av rettens navn (se forklaringen
øverst til høyre på tavlen), i stedet for å skrive det ut som tekst.

## "Nyhet"-overtaket

Skjermen henter feltet `showAsNew` — det ekte flagget IKEA selv bruker
for å markere nye retter på restaurantsiden (per nå: BBQ-marinert
kyllingfilet og Mandelkake med sitron, på Slependen). Alle retter merket
som nye vises på rundgang i overtaket; er ingen merket som nye, dukker
overtaket rett og slett aldri opp — tavlen blir stående i ro.

## Kampanjetekst ("commercial label")

Feltet finnes også i IKEA sin datamodell (`commercialTexts` på hver
rett), men er tomt for de fleste retter i praksis — det brukes til
kampanjer og sesongtilbud når IKEA legger dem inn manuelt. Henting av det
krever ett ekstra kall per rett (langsommere), så det er av som standard.
Legg til `--labels` hvis du vil ha det med — retter med kampanjetekst
dukker da også opp i "nyhet"-overtaket, i tillegg til de som er merket
`showAsNew`.

## Butikkode

`fetch_menu.py` filtrerer bort retter som ikke selges i den valgte
butikken (feltet `excludedStores` i IKEA sine data). Standard er `091`
(IKEA Oslo - Slependen). Sett `--store ""` for ingen filtrering (viser
alt).

Alle IKEA Norge-varehus med restaurant, verifisert direkte mot IKEA sin
egen "Bytt varehus"-velger på restaurantsiden:

| Kode  | Varehus            |
|-------|---------------------|
| `091` | IKEA Slependen       |
| `095` | IKEA Furuset         |
| `441` | IKEA Åsane           |
| `371` | IKEA Leangen         |
| `126` | IKEA Forus           |
| `390` | IKEA Ringsaker       |
| `007` | IKEA Sørlandet       |
| `722` | IKEA Karl Johan      |

Denne listen ligger også som `STORES` øverst i `fetch_menu.py`.

## Alle butikker på én gang (`--all-stores`)

Skal utrullingen dekke flere varehus, kjør:

```bash
python3 fetch_menu.py --all-stores
```

Dette henter selve menylisten kun ÉN gang (den er ikke butikk-spesifikk —
hver rett har sin egen `excludedStores`-liste), filtrerer den lokalt for
hver butikk i `STORES`, og skriver `menu-data-091.json`,
`menu-data-095.json` osv. — én fil per butikk — pluss en `stores.json`
med hele butikklisten. Legg gjerne denne kommandoen i samme cron-jobb som
punkt 3 i "Oppsett" over, i stedet for et vanlig `fetch_menu.py`-kall.

Pek hver skjerm mot sin egen butikk med `?store=<kode>` i URL-en, som
beskrevet i punkt 4 over — f.eks. `menu.html?store=441` for skjermen i
Åsane. Selve `menu.html`-filen er identisk for alle skjermer; det er kun
URL-en som avgjør hvilken butikk som vises, så én og samme utrulling
dekker alle varehusene.
