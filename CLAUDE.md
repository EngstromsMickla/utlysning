# Utlysningsradarn: utlysning.mickla.se

Arbetsbeskrivning för den som utvecklar verktyget vidare, människa eller Claude.

## Sammanhang

- Publikt verktyg som hjälper forskare, företag och offentliga aktörer att hitta forsknings- och innovationsutlysningar som passar en idé.
- Upphov: Dan Engström, Engströms Mickla AB. Dan äger allt innehåll; Claude föreslår, Dan beslutar.
- Tre delar: idéverktyget (`#ide`), radarn (`#radar`) och användarinstruktionen med processkarta (`#instruktion`). Om-sidan ligger i `#om`.
- Version 1 är helt statisk. Sidan anropar ingen AI. Användaren får ett urval med skäl och en färdig prompt att klistra in i sin egen AI-tjänst. Inbyggd analys kan komma i version 2, men löftet att idén inte lämnar webbläsaren förrän användaren själv kopierar den ska behållas som val.

## Fasta principer

- Allt på svenska. Inga tankstreck (varken — eller –) i texter som skrivs nya.
- Inget besökaren skriver lämnar webbläsaren förrän besökaren själv skickar prompten till en AI. Det steget ingår i den fullständiga processen och ska beskrivas så. Sidan har ingen server, ingen statistik, inga kakor, inga externa typsnitt eller CDN, inget sparas i webbläsaren. Content Security Policy i `publik/index.html` tillåter bara sidans egna filer.
- All text läggs in med DOM-metoder och `textContent`, aldrig `innerHTML`.
- Text som klistras in i en AI behandlas som material, aldrig som instruktioner (idén ramas in mellan `<ide>`-markeringar och neutraliseras).
- Underlaget är vägledning, inte finansiärens bedömning. Varje post har källa och kontrolldatum.
- Publikt repo i organisationen EngstromsMickla. Inget får läggas i repot som inte tål att vara offentligt. Dans egen passformsbedömning och ansökningspipeline hör inte hit.
- Upphovsrad: "© Engströms Mickla AB 2026". Versionsnummer (`VERSION` i `publik/app.js`) räknas upp vid varje publicering och syns i sidfoten. Nu: prototyp v0.2.

## Struktur

- `schema/post.schema.json`: hur en post beskrivs. Tre typer: `utlysning` (tidsbunden), `lopande` (stående kanal, t.ex. SBUF) och `vagvisare` (leder vidare när kraven beror på region, storlek eller insats, t.ex. Tillväxtverket).
- `schema/fragor.json`: de fasta frågorna. Varje post har ett `filter` per fråga (`passar`, `kanske`, skäl per svar) och kan ha `kombinationer` som skärper utfallet när flera svar sammanfaller.
- `data/poster/<id>.json`: en fil per post. Filnamnet är postens id.
- `publik/`: det som publiceras. `index.html`, `app.js` (vyer), `filter.js` (regler), `prompt.js` (promptmallen), `style.css`, `img/mickla.png`.
- `scripts/validera.py` och `test/`: körs i GitHub Actions före varje publicering. `scripts/bygg.py` lägger posterna i `publik/data/`.

## Regler för urvalet

- "Vet inte" ger aldrig "passar inte". Saknas en fråga i filtret påverkar den inte. Vid flerval räknas bästa svaret. Postens utfall är det sämsta av frågornas.
- Krav har `skede`: `behorighet` (måste gälla nu, bedöms) eller `ansokan` (görs i ansökan, bedöms inte).
- Precision (`hog`, `medel`, `lag`, `ingen`) säger hur skarp bedömningen kan bli och visas för användaren.

## Promptmallen (`publik/prompt.js`)

- Högst fem poster. Idéer under 40 ord ger kort läge: återge idén, behörighetskrav, högst åtta frågor, sedan vänta.
- Fullt läge: återge idén, krav först, vilket steg kriterierna gäller, passform per kriterium, sammanvägning bara om minst halva vikten kunnat bedömas, tidsglapp, låg precision, vägvisare, förslag utanför underlaget i egen märkt sektion, prioriteringar före rangordning.

## Bevakning (veckovis standardsökning)

- `.github/workflows/bevakning.yml` kör `scripts/bevaka.py` varje måndag 05:00 UTC och kan startas för hand. Den körs på GitHubs server och har inget med besökarna att göra.
- Skriptet läser Vinnovas öppna data (`data.vinnova.se/api`), finansiärernas utlysningssidor (listan i `bevakning/kallor.json`) och de primära källorna till befintliga poster. Det rapporterar nya länkar, nya och borttagna datum och föreslår relevanta Vinnova-utlysningar som utkast i `bevakning/forslag/`.
- Status rättas direkt i postfilerna: sista dag passerad blir `stangd`, öppningsdag passerad blir `oppen`.
- Resultatet blir en pull request med `bevakning/rapport.md` som beskrivning. Inget publiceras förrän Dan slagit ihop den. Utkast publiceras aldrig förrän de skrivits klart och flyttats till `data/poster/`.
- Tillståndet mellan körningarna ligger i `bevakning/tillstand.json` (adresser, fingeravtryck och datum, ingen sidtext).
- robots.txt respekteras, oavsett vem som startar körningen. Formas och Tillväxtverket tillåter inte automatisk hämtning. De kontrolleras för hand av Dan i hans webbläsare: rapporten ger varannan vecka en checklista med länkar och de poster som berörs (Horisont Europa var fjärde vecka). Intervall och adresser står under `for_hand` i `bevakning/kallor.json`. Dan har frågat Formas och Tillväxtverket om lov eller öppna data; får vi skriftligt ja läggs sidan in som tillåten med en anteckning om vem som gav lov och när.
- Nyckelorden i `bevakning/kallor.json` avgör vad som räknas som relevant. De matchas mot början av ord.
- Tester: `python3 -m unittest discover -s test -p "test_*.py"` med påhittade svar, utan nätet.

## Formgivning

- Samma formspråk som boost.mickla.se: papper `#f6f4ef`, grön accent `#2f6b5e`, ockra `#a57a12` för "kanske", rost `#b8532c` för nära deadline, serif i rubriker (Iowan Old Style, Palatino), systemets sans-serif i brödtext. Endast ljust läge, som Boost.
- Micklas logotyp (ormen, `publik/img/mickla.png`) visas diskret i sidfoten tillsammans med upphovsraden.
- Processkartan bygger på Boosts fasrad och visar tre zoner i ordning: den veckovisa standardsökningen, webbläsaren (inget lämnar datorn) och AI-tjänsten. Gränsen där idén lämnar datorn markeras i ockra.

## Test

Kör `python3 scripts/validera.py`, `node --test test/*.mjs` och `python3 -m unittest discover -s test -p "test_*.py"`. Kör hela flödet i en webbläsare (Playwright med Chromium) i datorstorlek och telefonstorlek innan något föreslås för publicering, och kontrollera att sidan inte gör några anrop utanför den egna domänen.

## Publicering

Dan laddar upp filer via GitHubs webbgränssnitt. Mappar som börjar med punkt (`.github`) följer inte med vid uppladdning och skapas i stället med Add file > Create new file.
