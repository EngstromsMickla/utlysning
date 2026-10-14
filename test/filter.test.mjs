// Kör: node --test test/
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { bedomPost, filtrera } from "../publik/filter.js";

const poster = readdirSync("data/poster").map((f) => JSON.parse(readFileSync(`data/poster/${f}`, "utf8")));
const post = (id) => poster.find((p) => p.id === id);
const IDAG = "2026-10-14";

test("byggföretag i Västra Götaland med svenska partner", () => {
  const svar = { organisationstyp: "foretag", foretagsstorlek: "medel", lan: "vastra_gotaland",
    sektor: ["bygg_fastighet"], mognad: "fou", bidragsbehov: "0_5_till_2",
    tidshorisont: "1_till_3_man", partners: "svenska", branschorganisation: ["byggforetagen"] };
  const sbuf = bedomPost(post("sbuf-projektbidrag"), svar, IDAG);
  assert.equal(sbuf.utfall, "kanske");          // allt passar utom tiden: 4 nov hinns inte, 2027 ej publicerat
  assert.ok(sbuf.skal.filter((s) => s.fraga !== "tidshorisont").every((s) => s.utfall === "passar"));
  const eureka = bedomPost(post("vinnova-eureka-smart-call10"), svar, IDAG);
  assert.equal(eureka.utfall, "kanske");        // saknar internationell partner, sektor kanske
  const tvv = bedomPost(post("tillvaxtverket-vagvisare"), svar, IDAG);
  const ris = tvv.vagar.find((v) => v.id === "regionalt-investeringsstod");
  assert.equal(ris.utfall, "passar_inte");      // stödet gäller investering, inte FoU
  const rf = tvv.vagar.find((v) => v.id === "regionalfonden");
  assert.equal(rf.fordelning.namn, "Västsverige");
});

test("SBUF: inlämning om mer än en månad ger kanske när 2027 inte är publicerat", () => {
  const r = bedomPost(post("sbuf-projektbidrag"), { tidshorisont: "1_till_3_man" }, IDAG);
  const tid = r.skal.find((s) => s.fraga === "tidshorisont");
  // 4 nov ligger 21 dagar bort; 30 dagar krävs.
  assert.equal(tid.utfall, "kanske");
});

test("Eureka: kommun som vill skala upp utfaller passar_inte", () => {
  const r = bedomPost(post("vinnova-eureka-smart-call10"),
    { organisationstyp: "kommun_region", mognad: "implementering" }, IDAG);
  assert.equal(r.utfall, "passar_inte");
  assert.match(r.skal.find((s) => s.fraga === "mognad").text, /Införande/);
});

test("Eureka: över sex månader är för sent för projektskissen", () => {
  const r = bedomPost(post("vinnova-eureka-smart-call10"), { tidshorisont: "over_6_man" }, IDAG);
  assert.equal(r.utfall, "passar_inte");
});

test("vet_ej ger aldrig passar_inte", () => {
  const svar = { organisationstyp: "vet_ej", foretagsstorlek: "vet_ej", mognad: "vet_ej",
    bidragsbehov: "vet_ej", partners: "vet_ej", tidshorisont: "vet_ej", branschorganisation: ["vet_ej"] };
  for (const p of poster.filter((p) => p.typ !== "vagvisare")) {
    assert.notEqual(bedomPost(p, svar, IDAG).utfall, "passar_inte", p.id);
  }
});

test("flerval: bästa svaret räknas", () => {
  const r = bedomPost(post("sbuf-projektbidrag"), { sektor: ["halsa", "bygg_fastighet"] }, IDAG);
  assert.equal(r.utfall, "passar");
});

test("privatperson faller bort och får förklaring", () => {
  const { bortfallna } = filtrera(poster, { organisationstyp: "privatperson" }, IDAG);
  assert.ok(bortfallna.some((b) => b.post.id === "vinnova-eureka-smart-call10"));
});

test("stort företag i Norrbotten som ska investera: investeringsstöd värt att undersöka", () => {
  const r = bedomPost(post("tillvaxtverket-vagvisare"),
    { organisationstyp: "foretag", foretagsstorlek: "stor", lan: "norrbotten", mognad: "implementering" }, IDAG);
  assert.equal(r.vagar.find((v) => v.id === "regionalt-investeringsstod").utfall, "kanske");
  assert.equal(r.vagar.find((v) => v.id === "regionala-foretagsstod").utfall, "passar_inte");
});
