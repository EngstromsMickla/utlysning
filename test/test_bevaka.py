"""Prövar den veckovisa bevakningen utan nätet, med påhittade svar från finansiärerna.
    python3 -m unittest discover -s test -p "test_*.py"
"""
import json, pathlib, shutil, sys, tempfile, unittest, urllib.error

ROT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROT / "scripts"))
import bevaka  # noqa: E402

IDAG = "2026-10-19"


def vinnova_omg(dnr, titel, stang, text="", publik=1, oppnar="2026-10-01T00:00:00"):
    return {"Diarienummer": dnr, "Titel": titel, "Oppningsdatum": oppnar, "Stangningsdatum": stang,
            "Publik": publik, "UppskattatBeslutsdatum": "2027-03-01T00:00:00", "SenastProjektstart": None,
            "WebTextLista": [{"TextID": 1, "TextSv": text}]}


class Natet:
    """Påhittat nät. Okända adresser svarar 404."""

    def __init__(self, sidor):
        self.sidor = sidor
        self.anrop = []

    def __call__(self, url):
        self.anrop.append(url)
        if url in self.sidor:
            return self.sidor[url]
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)


def lista_html(lankar, text=""):
    a = "".join(f'<a href="{u}">{n}</a>' for u, n in lankar)
    return f"<html><head><script>var x='2099-01-01';</script></head><body><main>{text}{a}</main></body></html>"


class Bevakning(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        shutil.copytree(ROT / "data", self.tmp / "data")
        (self.tmp / "bevakning").mkdir()
        shutil.copy(ROT / "bevakning/kallor.json", self.tmp / "bevakning/kallor.json")
        self._rot, self._bev = bevaka.ROT, bevaka.BEV
        bevaka.ROT, bevaka.BEV = self.tmp, self.tmp / "bevakning"

    def tearDown(self):
        bevaka.ROT, bevaka.BEV = self._rot, self._bev
        shutil.rmtree(self.tmp)

    def natet(self, vinnova, energi_lankar, eureka_text="Sista dag 26 januari 2027."):
        konf = json.loads((self.tmp / "bevakning/kallor.json").read_text())
        sidor = {
            "https://formas.se/robots.txt": "User-agent: *\nDisallow: /",
            "https://tillvaxtverket.se/robots.txt": "User-agent: *\nDisallow: /",
            konf["vinnova"]["api"] + "2026-08-20": json.dumps(vinnova),
            konf["vinnova"]["api"] + IDAG: json.dumps(vinnova),
            "https://www.energimyndigheten.se/utlysningar/": lista_html(energi_lankar),
        }
        for lista in konf["listor"]:
            sidor.setdefault(lista["url"], lista_html([], "Inga utlysningar just nu."))
        for f in (self.tmp / "data/poster").glob("*.json"):
            for k in json.loads(f.read_text())["kallor"]:
                sidor.setdefault(k["url"], lista_html([], "Sidan om utlysningen. 18 november 2026."))
        eureka = json.loads((self.tmp / "data/poster/vinnova-eureka-smart-call10.json").read_text())
        for k in eureka["kallor"]:
            if k["roll"] == "primar":
                sidor[k["url"]] = lista_html([], eureka_text)
        return Natet(sidor)

    def kor(self, natet, idag=IDAG):
        h = bevaka.Hamtare("test", hamta_ra=natet, paus=0)
        return bevaka.kor(idag, h)

    def test_forsta_korningen_sparar_utgangslage_och_foreslar_relevant_vinnova(self):
        vinnova = [
            vinnova_omg("2026-09999", "Energieffektiva byggnader 2026", "2027-02-01T14:00:00", "Om bebyggelse."),
            vinnova_omg("2026-08888", "Rymdteknik för satelliter", "2027-02-01T14:00:00", "Om rymden."),
            vinnova_omg("2020-00001", "Gammal utlysning om bygg", "2021-01-01T14:00:00"),
            vinnova_omg("2026-07777", "Intern bygg", "2027-02-01T14:00:00", publik=0),
        ]
        natet = self.natet(vinnova, [("/utlysningar/dut/", "DUT")])
        rapport, antal, fynd = self.kor(natet)
        self.assertTrue(fynd)
        self.assertIn("Energieffektiva byggnader 2026", rapport)
        self.assertNotIn("Rymdteknik", rapport)
        self.assertIn("1 nya ansökningsomgångar utan träff", rapport)
        self.assertNotIn("Gammal utlysning", rapport)
        self.assertNotIn("Intern bygg", rapport)
        utkast = json.loads((self.tmp / "bevakning/forslag/vinnova-energieffektiva-byggnader-2026.json").read_text())
        self.assertEqual(utkast["diarienummer"], "2026-09999")
        self.assertEqual(utkast["tidpunkter"][1], {"typ": "sista_dag", "datum": "2027-02-01", "tid": "14:00"})
        self.assertIn("UTKAST", utkast["_utkast"])
        self.assertIn("första genomgången", rapport)
        # Formas och Tillväxtverket läses aldrig.
        self.assertFalse(any("tillvaxtverket.se/" in u and not u.endswith("robots.txt") for u in natet.anrop))
        self.assertFalse(any(u.startswith("https://formas.se/") and not u.endswith("robots.txt") for u in natet.anrop))
        self.assertIn("Tillväxtverket", rapport)

    def test_andra_korningen_rapporterar_bara_det_nya(self):
        vinnova = [vinnova_omg("2026-09999", "Energieffektiva byggnader 2026", "2027-02-01T14:00:00", "bebyggelse")]
        self.kor(self.natet(vinnova, [("/utlysningar/dut/", "DUT")]))
        natet = self.natet(vinnova, [("/utlysningar/dut/", "DUT"), ("/utlysningar/ny-cirkular-byggnad/", "Ny utlysning om cirkulär bygg")],
                           eureka_text="Sista dag 2 februari 2027.")
        rapport, antal, fynd = self.kor(natet, "2026-10-26")
        self.assertTrue(fynd)
        self.assertIn("Ny länk: [Ny utlysning om cirkulär bygg](https://www.energimyndigheten.se/utlysningar/ny-cirkular-byggnad/)", rapport)
        self.assertNotIn("Ny länk: [DUT]", rapport)
        self.assertNotIn("Energieffektiva byggnader 2026", rapport)  # redan föreslagen förra veckan
        self.assertIn("nya datum 2027-02-02", rapport)
        self.assertIn("borttagna datum 2027-01-26", rapport)

    def test_inget_nytt_ger_inget_fynd(self):
        natet = self.natet([], [])
        self.kor(natet)
        rapport, antal, fynd = self.kor(self.natet([], []), "2026-10-26")
        self.assertEqual(antal, 0)
        self.assertFalse(fynd)

    def test_status_rattas_nar_sista_dag_passerat(self):
        self.kor(self.natet([], []), "2026-11-20")
        dut = json.loads((self.tmp / "data/poster/dut-call-2026.json").read_text())
        self.assertEqual(dut["status"], "oppen")  # steg två 2027-04-15 återstår
        energi = json.loads((self.tmp / "data/poster/energimyndigheten-energieffektiv-bebyggelse-2026.json").read_text())
        self.assertEqual(energi["status"], "stangd")
        text = (self.tmp / "data/poster/energimyndigheten-energieffektiv-bebyggelse-2026.json").read_text()
        self.assertIn('\n\n  "kallor"', text)  # filens övriga formatering lämnas orörd

    def test_andrat_datum_hos_vinnova_for_kand_post(self):
        vinnova = [vinnova_omg("2026-01106", "Eureka SMART Call 10", "2027-02-09T11:00:00")]
        rapport, antal, fynd = self.kor(self.natet(vinnova, []))
        self.assertIn("Vinnova anger sista dag 2027-02-09", rapport)

    def test_nyckelord_traffar_ordborjan(self):
        self.assertEqual(bevaka.relevant("Byggnader och ombyggnad", ["bygg"]), ["bygg"])
        self.assertEqual(bevaka.relevant("Ett tidigt stadium", ["staden", "stads"]), [])

    def test_datum_hittas_i_svensk_och_iso_form(self):
        self.assertEqual(bevaka.hitta_datum("Senast 4 november 2026 eller 2027-01-12. Ogiltigt 2026-02-31."),
                         ["2026-11-04", "2027-01-12"])

    def test_robots_fel_tolkas_som_forbud(self):
        def trasigt(url):
            raise urllib.error.HTTPError(url, 500, "fel", {}, None)
        h = bevaka.Hamtare("test", hamta_ra=trasigt, paus=0)
        text, fel = h.hamta("https://exempel.se/sida")
        self.assertIsNone(text)
        self.assertIn("robots.txt", fel)


if __name__ == "__main__":
    unittest.main()
