"""Veckovis standardsökning på finansiärernas webbplatser.

Körs av GitHub Actions varje måndag (.github/workflows/bevakning.yml), aldrig i besökarens webbläsare.
Skriptet publicerar ingenting. Det skriver en rapport och förslag som Dan granskar i en pull request.

Vad det gör:
  1. Läser Vinnovas öppna data och föreslår nya utlysningar som verkar relevanta (utkast i bevakning/forslag/).
  2. Läser finansiärernas utlysningssidor och rapporterar nya länkar.
  3. Läser källorna till befintliga poster och rapporterar om datum på sidan har ändrats.
  4. Rättar status: en utlysning vars sista dag har passerat blir "stangd", en som har öppnat blir "oppen".
  5. Påminner om källor som måste kontrolleras för hand (robots.txt tillåter inte hämtning).

Respekterar robots.txt, identifierar sig med en egen användaragent och väntar mellan anropen.
Använder bara Pythons standardbibliotek.

    python3 scripts/bevaka.py               # skarp körning
    python3 scripts/bevaka.py --idag 2026-10-19
"""
import argparse, datetime, hashlib, html.parser, json, os, pathlib, re, sys, time
import urllib.error, urllib.parse, urllib.request, urllib.robotparser

ROT = pathlib.Path(__file__).resolve().parent.parent
BEV = ROT / "bevakning"
MAX_BYTES = 4_000_000
PAUS_SEK = 2

MANADER = {m: i + 1 for i, m in enumerate(
    "januari februari mars april maj juni juli augusti september oktober november december".split())}
DATUM_ISO = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b")
DATUM_SV = re.compile(r"\b(\d{1,2})\s+(" + "|".join(MANADER) + r")\s+(20\d\d)\b", re.I)


# ---------- Hämtning ----------

class Hamtare:
    """Hämtar sidor artigt: robots.txt, egen användaragent, paus mellan anrop till samma värd."""

    def __init__(self, agent, hamta_ra=None, paus=PAUS_SEK):
        self.agent = agent
        self.paus = paus
        self._ra = hamta_ra or self._hamta_natet
        self._robots = {}
        self._senast = {}

    def _hamta_natet(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": self.agent, "Accept-Language": "sv,en"})
        with urllib.request.urlopen(req, timeout=30) as svar:
            data = svar.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError("sidan är större än 4 MB")
            return data.decode(svar.headers.get_content_charset() or "utf-8", errors="replace")

    def tillats(self, url):
        delar = urllib.parse.urlsplit(url)
        vard = f"{delar.scheme}://{delar.netloc}"
        if vard not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                rp.parse(self._ra(vard + "/robots.txt").splitlines())
            except urllib.error.HTTPError as e:
                # 404 betyder inga regler; andra fel tolkas försiktigt som förbud.
                rp.parse([] if e.code in (404, 410) else ["User-agent: *", "Disallow: /"])
            except Exception:
                rp.parse(["User-agent: *", "Disallow: /"])
            self._robots[vard] = rp
        return self._robots[vard].can_fetch(self.agent, url)

    def hamta(self, url):
        """Returnerar (text, None) eller (None, felbeskrivning)."""
        if not self.tillats(url):
            return None, "robots.txt tillåter inte automatisk hämtning"
        vard = urllib.parse.urlsplit(url).netloc
        vanta = self._senast.get(vard, 0) + self.paus - time.monotonic()
        if vanta > 0:
            time.sleep(vanta)
        try:
            return self._ra(url), None
        except urllib.error.HTTPError as e:
            return None, f"svarade {e.code}"
        except Exception as e:  # nätverksfel, tidsgrans
            return None, f"kunde inte läsas ({type(e).__name__})"
        finally:
            self._senast[vard] = time.monotonic()


# ---------- Tolkning av sidor ----------

class _Sidtolk(html.parser.HTMLParser):
    HOPPA = {"script", "style", "noscript", "svg", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text, self.lankar = [], []
        self._djup = 0
        self._lank = None

    def handle_starttag(self, tag, attrs):
        if tag in self.HOPPA:
            self._djup += 1
        elif tag == "a":
            self._lank = [dict(attrs).get("href") or "", []]

    def handle_endtag(self, tag):
        if tag in self.HOPPA and self._djup:
            self._djup -= 1
        elif tag == "a" and self._lank:
            self.lankar.append((self._lank[0], " ".join(" ".join(self._lank[1]).split())))
            self._lank = None

    def handle_data(self, data):
        if self._djup:
            return
        self.text.append(data)
        if self._lank:
            self._lank[1].append(data)


def tolka_sida(html_text, bas_url):
    t = _Sidtolk()
    t.feed(html_text)
    text = " ".join(" ".join(t.text).split())
    lankar = {}
    for href, namn in t.lankar:
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        url = urllib.parse.urljoin(bas_url, href).split("#")[0]
        if namn and url not in lankar:
            lankar[url] = namn
    return {"text": text, "lankar": lankar}


def hitta_datum(text):
    datum = set()
    for a, m, d in DATUM_ISO.findall(text):
        datum.add(f"{a}-{m}-{d}")
    for d, m, a in DATUM_SV.findall(text):
        datum.add(f"{a}-{MANADER[m.lower()]:02d}-{int(d):02d}")
    return sorted(x for x in datum if _giltigt(x))


def _giltigt(iso):
    try:
        datetime.date.fromisoformat(iso)
        return True
    except ValueError:
        return False


def fingeravtryck(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def relevant(text, nyckelord):
    """Nyckelord som förekommer i början av ett ord, så att "bygg" träffar "byggnad" men inte "ombygga"s mitt."""
    t = text.lower()
    return [n for n in nyckelord if re.search(r"(?<![a-zåäöé])" + re.escape(n.lower()), t)]


# ---------- Poster ----------

def las_poster():
    poster = {}
    for f in sorted((ROT / "data/poster").glob("*.json")):
        poster[f.stem] = (f, json.loads(f.read_text(encoding="utf-8")))
    return poster


def datum_av(post, typ):
    return sorted(t["datum"] for t in post.get("tidpunkter", []) if t["typ"] == typ)


def ratta_status(poster, idag):
    """Ändrar status direkt i postfilerna. Ändringen syns i pull requesten och granskas där."""
    andringar = []
    for pid, (fil, post) in poster.items():
        if post["typ"] != "utlysning":
            continue
        sista = datum_av(post, "sista_dag")
        oppnar = datum_av(post, "oppnar")
        ny = post["status"]
        if sista and all(d < idag for d in sista):
            ny = "stangd"
        elif post["status"] == "kommande" and oppnar and oppnar[0] <= idag:
            ny = "oppen"
        if ny != post["status"]:
            text = fil.read_text(encoding="utf-8")
            text, antal = re.subn(r'"status":\s*"' + post["status"] + '"', f'"status": "{ny}"', text, count=1)
            if antal:
                fil.write_text(text, encoding="utf-8")
                andringar.append((post["titel"], post["status"], ny))
                post["status"] = ny
    return andringar


# ---------- Vinnova ----------

def slugga(text, maxlangd=50):
    t = text.lower()
    for a, b in (("å", "a"), ("ä", "a"), ("ö", "o"), ("é", "e"), ("ü", "u")):
        t = t.replace(a, b)
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:maxlangd].rstrip("-") or "utlysning"


def vinnova_utkast(omg, idag, webb):
    texter = {w.get("TextID"): (w.get("TextSv") or "").strip() for w in omg.get("WebTextLista") or []}
    tid = []
    if omg.get("Oppningsdatum", "").startswith("20"):
        tid.append({"typ": "oppnar", "datum": omg["Oppningsdatum"][:10]})
    stang = omg["Stangningsdatum"]
    sista = {"typ": "sista_dag", "datum": stang[:10]}
    if stang[11:16] not in ("", "00:00"):
        sista["tid"] = stang[11:16]
    tid.append(sista)
    if omg.get("UppskattatBeslutsdatum"):
        tid.append({"typ": "beslut", "datum": omg["UppskattatBeslutsdatum"][:10], "preliminar": True})
    if omg.get("SenastProjektstart"):
        tid.append({"typ": "projektstart_senast", "datum": omg["SenastProjektstart"][:10]})
    return {
        "_utkast": "UTKAST från den veckovisa sökningen. Inte granskat. Sammanfattning, filter, krav, belopp och bedömning ska skrivas innan posten flyttas till data/poster/.",
        "_vinnova_text": {"vad": texter.get(1, ""), "vem": texter.get(2, ""), "hur_mycket": texter.get(3, "")},
        "id": "vinnova-" + slugga(omg["Titel"]),
        "typ": "utlysning",
        "titel": omg["Titel"],
        "finansiar": {"id": "vinnova", "namn": "Vinnova"},
        "diarienummer": omg["Diarienummer"],
        "sammanfattning": "",
        "status": "oppen" if (omg.get("Oppningsdatum") or "")[:10] <= idag else "kommande",
        "kallor": [
            {"url": webb, "titel": "Vinnova: hitta finansiering (sök på diarienumret)", "roll": "primar", "sprak": "sv"},
            {"url": f"https://data.vinnova.se/api/ansokningsomgangar/{idag}", "titel": f"Vinnovas öppna data, ansökningsomgång {omg['Diarienummer']}", "roll": "kompletterande"}
        ],
        "kontroll": {"senast": idag, "metod": "automatisk", "godkand_av": ""},
        "precision": "lag",
        "tidpunkter": tid,
    }


def bevaka_vinnova(hamtare, konf, tillstand, poster, idag, nyckelord):
    fynd = {"nya": [], "ovriga": 0, "andrade": [], "fel": None}
    fran = tillstand.get("vinnova_senast") or (datetime.date.fromisoformat(idag) - datetime.timedelta(days=60)).isoformat()
    text, fel = hamtare.hamta(konf["api"] + fran)
    if fel:
        fynd["fel"] = fel
        return fynd
    try:
        omgangar = json.loads(text)
    except ValueError:
        fynd["fel"] = "svaret gick inte att tolka"
        return fynd
    kanda_dnr = {p.get("diarienummer"): (pid, p) for pid, (_, p) in poster.items() if p.get("diarienummer")}
    tidigare = set(tillstand.get("vinnova_sedda", []))
    sedda = set(tidigare)
    for o in omgangar:
        stang = (o.get("Stangningsdatum") or "")[:10]
        if not o.get("Publik") or not stang.startswith("20") or stang < idag:
            continue
        dnr = o["Diarienummer"]
        if dnr in kanda_dnr:
            pid, post = kanda_dnr[dnr]
            if stang not in datum_av(post, "sista_dag"):
                fynd["andrade"].append((post["titel"], f"Vinnova anger sista dag {stang}, posten har {', '.join(datum_av(post, 'sista_dag')) or 'ingen'}."))
            continue
        if dnr in tidigare:
            continue
        sedda.add(dnr)
        texter = " ".join(w.get("TextSv") or "" for w in o.get("WebTextLista") or [])
        traffar = relevant(o["Titel"] + " " + texter, nyckelord)
        if traffar:
            utkast = vinnova_utkast(o, idag, konf["webb"])
            fil = BEV / "forslag" / f"{utkast['id']}.json"
            fil.write_text(json.dumps(utkast, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            fynd["nya"].append((o["Titel"], dnr, stang, traffar[:4], fil.relative_to(ROT).as_posix()))
        else:
            fynd["ovriga"] += 1
    tillstand["vinnova_sedda"] = sorted(sedda)
    tillstand["vinnova_senast"] = idag
    return fynd


# ---------- Listor och källor ----------

def bevaka_listor(hamtare, listor, tillstand, nyckelord):
    resultat = []
    sparat = tillstand.setdefault("listor", {})
    for lista in listor:
        text, fel = hamtare.hamta(lista["url"])
        if fel:
            resultat.append({"namn": lista["namn"], "url": lista["url"], "fel": fel})
            continue
        sida = tolka_sida(text, lista["url"])
        monster = re.compile(lista["lankmonster"], re.I) if lista.get("lankmonster") else None
        lankar = {u: n for u, n in sida["lankar"].items() if monster and monster.search(u)}
        datum = hitta_datum(sida["text"])
        forra = sparat.get(lista["id"])
        post = {"namn": lista["namn"], "url": lista["url"], "baslinje": forra is None,
                "nya_lankar": [], "nya_datum": []}
        if forra:
            post["nya_lankar"] = [(n, u, relevant(n + " " + u, nyckelord)) for u, n in lankar.items()
                                  if u not in forra.get("lankar", [])]
            post["nya_datum"] = [d for d in datum if d not in forra.get("datum", [])]
        sparat[lista["id"]] = {"lankar": sorted(lankar), "datum": datum}
        resultat.append(post)
    return resultat


def bevaka_kallor(hamtare, poster, tillstand, idag):
    resultat = []
    sparat = tillstand.setdefault("kallor", {})
    for pid, (_, post) in poster.items():
        for kalla in post.get("kallor", []):
            if kalla.get("roll") != "primar" or kalla["url"].lower().endswith(".pdf"):
                continue
            url = kalla["url"]
            text, fel = hamtare.hamta(url)
            if fel:
                resultat.append({"post": post["titel"], "url": url, "fel": fel, "for_hand": "robots" in fel})
                continue
            sida = tolka_sida(text, url)
            datum = [d for d in hitta_datum(sida["text"]) if d >= f"{int(idag[:4]) - 1}-01-01"]
            avtryck = fingeravtryck(sida["text"])
            forra = sparat.get(url)
            rad = {"post": post["titel"], "url": url, "baslinje": forra is None,
                   "nya_datum": [], "borta_datum": [], "text_andrad": False}
            if forra:
                rad["nya_datum"] = [d for d in datum if d not in forra["datum"]]
                rad["borta_datum"] = [d for d in forra["datum"] if d not in datum]
                rad["text_andrad"] = forra["avtryck"] != avtryck
            sparat[url] = {"avtryck": avtryck, "datum": datum, "last": idag}
            resultat.append(rad)
    return resultat


def narmaste_deadlines(poster, idag, dagar=21):
    grans = (datetime.date.fromisoformat(idag) + datetime.timedelta(days=dagar)).isoformat()
    ut = []
    for _, post in poster.values():
        for d in datum_av(post, "sista_dag"):
            if idag <= d <= grans:
                ut.append((d, post["titel"]))
    return sorted(ut)


def gamla_kontroller(poster, idag, dagar=90):
    grans = (datetime.date.fromisoformat(idag) - datetime.timedelta(days=dagar)).isoformat()
    return sorted((p["kontroll"]["senast"], p["titel"]) for _, p in poster.values()
                  if p["kontroll"]["senast"] < grans and p["status"] != "stangd")


def checklista_for_hand(for_hand, poster, kallor, tillstand, idag):
    """Finansiärer som inte får läsas automatiskt. Var intervall_dagar:e dag blir de en checklista
    som Dan bockar av efter att ha tittat i sin egen webbläsare."""
    sparat = tillstand.setdefault("for_hand", {})
    blockerade = {k["post"] for k in kallor if k.get("for_hand")}
    aktuella, vilande = [], []
    for f in for_hand:
        senast = sparat.get(f["id"])
        nasta = (datetime.date.fromisoformat(senast) + datetime.timedelta(days=f.get("intervall_dagar", 14))).isoformat() if senast else idag
        if nasta > idag:
            vilande.append((f["namn"], nasta))
            continue
        sparat[f["id"]] = idag
        relaterade = []
        for _, p in poster.values():
            partner = " ".join(p["finansiar"].get("partner", []))
            if p["finansiar"]["id"] in f.get("finansiarer", []) or f.get("partnernamn", "\0") in partner:
                sista = [d for d in datum_av(p, "sista_dag") if d >= idag]
                relaterade.append((p["titel"], p["kontroll"]["senast"], sista[0] if sista else None, p["titel"] in blockerade))
        aktuella.append({**f, "poster": sorted(relaterade)})
    return aktuella, vilande


# ---------- Rapport ----------

def skriv_rapport(idag, vinnova, listor, kallor, status, deadlines, gamla, for_hand, vilande=()):
    r = [f"# Bevakning {idag}", "",
         "Veckans standardsökning på finansiärernas webbplatser. Inget av detta är publicerat. "
         "Granska, ändra och godkänn i pull requesten; när den slås ihop publiceras ändringarna i `data/poster/`. "
         "Utkast i `bevakning/forslag/` publiceras aldrig förrän de flyttats till `data/poster/`.", ""]
    att_gora = 0

    r.append("## Statusändringar som redan gjorts i posterna")
    if status:
        for titel, fran, till in status:
            r.append(f"- {titel}: `{fran}` blir `{till}`.")
            att_gora += 1
    else:
        r.append("- Inga.")
    r.append("")

    r.append("## Nya utlysningar hos Vinnova")
    if vinnova["fel"]:
        r.append(f"- Vinnovas öppna data kunde inte läsas: {vinnova['fel']}.")
    elif vinnova["nya"]:
        for titel, dnr, stang, traffar, fil in vinnova["nya"]:
            r.append(f"- **{titel}** ({dnr}), sista dag {stang}. Träfford: {', '.join(traffar)}. Utkast: `{fil}`")
            att_gora += 1
    else:
        r.append("- Inga nya som verkar relevanta.")
    if vinnova["ovriga"]:
        r.append(f"- Dessutom {vinnova['ovriga']} nya ansökningsomgångar utan träff på nyckelorden (inte listade).")
    for titel, text in vinnova["andrade"]:
        r.append(f"- Ändrat datum i **{titel}**: {text}")
        att_gora += 1
    r.append("")

    r.append("## Finansiärernas utlysningssidor")
    for l in listor:
        if l.get("fel"):
            r.append(f"- {l['namn']}: {l['fel']}. Kontrollera {l['url']} för hand, eller rätta adressen i `bevakning/kallor.json`.")
            att_gora += 1
        elif l["baslinje"]:
            r.append(f"- {l['namn']}: första genomgången. Sidan är sparad som utgångsläge.")
        elif l["nya_lankar"] or l["nya_datum"]:
            r.append(f"- {l['namn']} ({l['url']}):")
            for namn, url, traffar in sorted(l["nya_lankar"], key=lambda x: not x[2]):
                markering = f" (träfford: {', '.join(traffar[:3])})" if traffar else ""
                r.append(f"  - Ny länk: [{namn}]({url}){markering}")
            if l["nya_datum"]:
                r.append(f"  - Nya datum på sidan: {', '.join(l['nya_datum'])}")
            att_gora += 1
        else:
            r.append(f"- {l['namn']}: inget nytt.")
    r.append("")

    r.append("## Källor till befintliga poster")
    andrade = [k for k in kallor if (k.get("fel") and not k.get("for_hand")) or k.get("nya_datum") or k.get("borta_datum")]
    for k in andrade:
        if k.get("fel"):
            r.append(f"- {k['post']}: {k['url']} {k['fel']}.")
        else:
            delar = []
            if k["nya_datum"]:
                delar.append("nya datum " + ", ".join(k["nya_datum"]))
            if k["borta_datum"]:
                delar.append("borttagna datum " + ", ".join(k["borta_datum"]))
            r.append(f"- **{k['post']}**: {'; '.join(delar)}. {k['url']}")
        att_gora += 1
    texter = [k for k in kallor if k.get("text_andrad") and k not in andrade]
    if texter:
        r.append(f"- Texten har ändrats utan att datumen ändrats på {len(texter)} sidor. Oftast småändringar; titta om du har tid:")
        r.extend(f"  - {k['post']}: {k['url']}" for k in texter)
    baslinje = sum(1 for k in kallor if k.get("baslinje"))
    if baslinje:
        r.append(f"- {baslinje} källor lästes för första gången och är sparade som utgångsläge.")
    if not andrade and not texter and not baslinje:
        r.append("- Inga ändringar.")
    r.append("")

    r.append("## Kontrollera för hand")
    if for_hand:
        r.append("De här webbplatserna får inte läsas automatiskt, men du får läsa dem i din vanliga webbläsare. "
                 "Öppna länken, titta efter nya utlysningar och ändrade datum, och bocka av rutan. "
                 "Hittar du något: klistra in länken eller texten hos Claude i projektet Interaktiva webbplatser "
                 "och skriv \"Ny utlysning för radarn\" eller \"Ändring i radarn\".")
        r.append("")
        for f in for_hand:
            r.append(f"- [ ] **{f['namn']}**: [{f['url']}]({f['url']}). {f['hur_hitta']}")
            for titel, senast, sista, blockerad in f["poster"]:
                delar = [f"senast kontrollerad {senast}"]
                if sista:
                    delar.append(f"nästa sista dag {sista}")
                if blockerad:
                    delar.append("källan får inte läsas automatiskt")
                r.append(f"  - Finns i radarn: {titel} ({', '.join(delar)}).")
            att_gora += 1
    else:
        r.append("- Inget denna vecka.")
    for namn, nasta in vilande:
        r.append(f"- Nästa påminnelse om {namn}: {nasta}.")
    for d, titel in gamla:
        r.append(f"- [ ] {titel}: senast kontrollerad {d}, mer än tre månader sedan.")
    r.append("")

    r.append("## Sista dag inom tre veckor")
    r.extend([f"- {d}: {t}" for d, t in deadlines] or ["- Ingen."])
    r.append("")
    return "\n".join(r), att_gora


# ---------- Huvudprogram ----------

def kor(idag, hamtare=None):
    konf = json.loads((BEV / "kallor.json").read_text(encoding="utf-8"))
    hamtare = hamtare or Hamtare(konf["anvandaragent"])
    (BEV / "forslag").mkdir(parents=True, exist_ok=True)
    tillstandsfil = BEV / "tillstand.json"
    tillstand = json.loads(tillstandsfil.read_text(encoding="utf-8")) if tillstandsfil.exists() else {}
    forsta = not tillstand

    poster = las_poster()
    status = ratta_status(poster, idag)
    vinnova = bevaka_vinnova(hamtare, konf["vinnova"], tillstand, poster, idag, konf["nyckelord"])
    listor = bevaka_listor(hamtare, konf["listor"], tillstand, konf["nyckelord"])
    kallor = bevaka_kallor(hamtare, poster, tillstand, idag)

    for_hand, vilande = checklista_for_hand(konf["for_hand"], poster, kallor, tillstand, idag)
    rapport, att_gora = skriv_rapport(idag, vinnova, listor, kallor, status,
                                      narmaste_deadlines(poster, idag), gamla_kontroller(poster, idag), for_hand, vilande)
    tillstand["senaste_korning"] = idag
    tillstandsfil.write_text(json.dumps(tillstand, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (BEV / "rapport.md").write_text(rapport + "\n", encoding="utf-8")
    fynd = att_gora > 0 or forsta
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"fynd={'true' if fynd else 'false'}\nantal={att_gora}\n")
    return rapport, att_gora, fynd


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--idag", default=datetime.date.today().isoformat())
    a = ap.parse_args()
    rapport, antal, fynd = kor(a.idag)
    print(rapport)
    print(f"\n{antal} saker att granska." if fynd else "\nInget att granska denna vecka.")
