# utlysning.mickla.se: datastruktur

Utlysningsradarn: datastruktur, sida och veckovis bevakning. Se `CLAUDE.md` för principer och beslut.

## Filerna

| Fil | Vad den gör |
|---|---|
| `schema/post.schema.json` | Reglerna för hur en post får se ut. Allt i `data/poster/` kontrolleras mot den. |
| `schema/fragor.json` | De fasta frågorna i idéverktyget med svarsalternativ. |
| `data/poster/*.json` | En fil per finansieringsmöjlighet. Filnamnet är postens id. |
| `publik/index.html`, `app.js`, `style.css` | Själva sidan: idéverktyget, radarn och om-sidan. |
| `publik/filter.js` | Reglerna som körs i besökarens webbläsare. Skickar ingenting någonstans. |
| `publik/prompt.js` | Bygger prompten som användaren kopierar till sin egen AI. |
| `scripts/bygg.py` | Slår ihop posterna till `publik/data/`, som sidan läser. |
| `scripts/validera.py` | Kontrollerar alla poster. Körs före varje publicering. |
| `scripts/bevaka.py` | Veckovis standardsökning på finansiärernas webbplatser. Körs av GitHub Actions varje måndag och föreslår ändringar som pull request. |
| `bevakning/kallor.json` | Vilka sidor bevakningen läser och vilka nyckelord som räknas som relevanta. |
| `bevakning/rapport.md`, `tillstand.json`, `forslag/` | Senaste rapporten, vad som setts förut och utkast till nya poster. Skrivs av bevakningen. |
| `test/` | Prövar filtreringen, prompten och bevakningen. |

Kör kontrollerna:

```
python3 scripts/validera.py
node --test test/*.mjs
python3 -m unittest discover -s test -p "test_*.py"
```

## Tre posttyper, en gemensam grund

Alla poster har samma grund:

- **id, titel, finansiär, sammanfattning** (egen text, aldrig kopierad från källan)
- **källor**: varje källa märks som primär (finansiärens egen sida), kompletterande eller sekundär (någon annans återgivning)
- **kontroll**: datum för senaste avstämning, om den gjordes automatiskt eller för hand, och vem som godkände
- **precision**: hur skarp bedömning underlaget tillåter (`hog`, `medel`, `lag`, `ingen`)
- **osäkerheter**: det som är oklart. Visas på sidan och följer med in i prompten.

Sedan skiljer de sig:

| | Utlysning | Löpande kanal | Vägvisare |
|---|---|---|---|
| Exempel | Eureka SMART Call 10 (Vinnova) | SBUF | Tillväxtverket |
| Tidpunkter | Krävs, med steg vid flerstegsansökan | Valfritt (SBUF har sex fasta tillfällen per år) | Nej |
| Krav, belopp, bedömning | Krävs | Krav krävs, belopp och bedömning om de finns | Nej |
| Särskilt | | `finansierar`, `beslutsrytm` | `vagar` med villkor och vart de leder |
| Precision | Oftast `hog` | Oftast `lag` | Alltid `ingen` |
| Vad användaren får | Passar / kanske / passar inte, med skäl | Samma, men märkt som grövre | Vilka vägar som är värda att undersöka, aldrig ett besked om behörighet |

## Hur frågorna kopplas till filtreringen

Varje post har ett `filter` där nyckeln är fråge-id:t och värdet säger vilka svar som **passar** och vilka som ger **kanske**. Alla andra svar ger **passar inte**. Till varje svar kan ett **skäl** skrivas, som visas för användaren.

```json
"organisationstyp": {
  "passar": ["foretag"],
  "kanske": ["universitet_hogskola", "forskningsinstitut"],
  "skal": { "universitet_hogskola": "Kan delta, men bara med ett svenskt företag." }
}
```

Fyra regler gäller för alla poster:

1. Saknas en fråga i postens filter påverkar den inte bedömningen.
2. "Vet inte" ger alltid kanske, aldrig passar inte.
3. Vid flervalsfrågor räknas det bästa svaret.
4. Postens samlade utfall är det sämsta av frågornas utfall. Tidsfrågan räknas mot nästa sista ansökningsdag.

Vägvisaren använder samma regelformat per väg, plus en uppslagstabell (`fordelning`) som till exempel pekar ut programområde utifrån län.

## Tillägg jämfört med din frågelista

- **Bidragsbehov** i stället för budget: frågan gäller hur mycket bidrag man söker, eftersom det är det beloppstaken avser.
- **Tidshorisont** är formulerad som "när kan ni tidigast lämna in" och jämförs med datum.
- **Branschorganisation** gäller den sökande organisationen. SBUF kräver att just den sökande är medlem.
- **Resultat** (egen produkt, delvis öppet, öppet) avgör bland annat SBUF, som kräver öppna resultat.
- **Kombinationsregler** (`kombinationer` i en post) skärper urvalet när flera svar sammanfaller, till exempel inga partner och idéstadium.

## Vad exemplen visade om bevakningen

- **Vinnova** har öppna data (`data.vinnova.se/api`) med datum, belopp och kortfattad målgrupp. Bedömningskriterierna finns bara på webbsidan.
- **SBUF** går att läsa automatiskt.
- **Formas och Tillväxtverket** tillåter inte automatisk hämtning av sina webbplatser (robots.txt). Bevakningen ska respektera det. Posterna från dem kontrolleras för hand, och veckorapporten påminner om när det är dags.
- Vinnovas engelska utlysningssidor är maskinöversatta. Kriterierna ska stämmas av mot den svenska texten.
