# Utlysningsradarn: utlysning.mickla.se

Arbetsbeskrivning för den som utvecklar verktyget vidare, människa eller Claude.

## Sammanhang

- Publikt verktyg som hjälper forskare, företag och offentliga aktörer att hitta forsknings- och innovationsutlysningar som passar en idé.
- Upphov: Dan Engström, Engströms Mickla AB. Dan äger allt innehåll; Claude föreslår, Dan beslutar.
- Tre delar: idéverktyget (`#ide`), radarn (`#radar`) och användarinstruktionen med processkarta (`#instruktion`). Om-sidan ligger i `#om`.
- Version 1 är helt statisk. Sidan anropar ingen AI. Användaren får ett urval med skäl och en färdig prompt att klistra in i sin egen AI-tjänst. Inbyggd analys kan komma i version 2, men löftet att idén inte lämnar webbläsaren förrän användaren själv kopierar den ska behållas som val.

## Fasta principer

- Allt på svenska. Inga tankstreck (varken — eller –) i texter som skrivs nya.
- Ingen data lämnar besökarens webbläsare: ingen server, ingen statistik, inga kakor, inga externa typsnitt eller CDN, inget sparas i webbläsaren. Content Security Policy i `publik/index.html` tillåter bara sidans egna filer.
- All text läggs in med DOM-metoder och `textContent`, aldrig `innerHTML`.
- Text som klistras in i en AI behandlas som material, aldrig som instruktioner (idén ramas in mellan `<ide>`-markeringar och neutraliseras).
- Underlaget är vägledning, inte finansiärens bedömning. Varje post har källa och kontrolldatum.
- Publikt repo i organisationen EngstromsMickla. Inget får läggas i repot som inte tål att vara offentligt. Dans egen passformsbedömning och ansökningspipeline hör inte hit.
- Upphovsrad: "© Engströms Mickla AB 2026". Versionsnummer (`VERSION` i `publik/app.js`) räknas upp vid varje publicering och syns i sidfoten. Nu: prototyp v0.1.

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

## Bevakning (nästa steg, inte byggd)

- GitHub Action varje måndag morgon som föreslår nya eller ändrade poster som pull request. Inget publiceras utan Dans godkännande.
- Vinnova har öppna data (`data.vinnova.se/api`). SBUF går att läsa automatiskt.
- Formas och Tillväxtverket tillåter inte automatisk hämtning (robots.txt). Respektera det; deras poster kontrolleras för hand och veckorapporten påminner.

## Formgivning

- Samma formspråk som boost.mickla.se: papper `#f6f4ef`, grön accent `#2f6b5e`, ockra `#a57a12` för "kanske", rost `#b8532c` för nära deadline, serif i rubriker (Iowan Old Style, Palatino), systemets sans-serif i brödtext. Endast ljust läge, som Boost.
- Micklas logotyp (ormen, `publik/img/mickla.png`) visas diskret i sidfoten tillsammans med upphovsraden.
- Processkartan bygger på Boosts fasrad och visar tre zoner: i webbläsaren, i den AI-tjänst användaren väljer, och bakom kulisserna.

## Test

Kör `python3 scripts/validera.py` och `node --test test/*.mjs`. Kör hela flödet i en webbläsare (Playwright med Chromium) i datorstorlek och telefonstorlek innan något föreslås för publicering, och kontrollera att sidan inte gör några anrop utanför den egna domänen.

## Publicering

Dan laddar upp filer via GitHubs webbgränssnitt. Mappar som börjar med punkt (`.github`) följer inte med vid uppladdning och skapas i stället med Add file > Create new file.
