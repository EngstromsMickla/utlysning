// Utlysningsradarn. Allt räknas i webbläsaren. Sidan hämtar bara sina egna
// datafiler och skickar aldrig något vidare. Innehållet byggs med DOM-metoder
// och textContent, aldrig med innerHTML, så att inmatad text alltid är text.

import { filtrera, nastaSistaDag } from "./filter.js";
import { byggPrompt, MAX_POSTER, arTunnIde, TUNN_IDE_ORD } from "./prompt.js";

const vy = document.getElementById("vy");
const IDAG = new Date().toLocaleDateString("sv-SE");

let DATA = null;
let FRAGOR = null;

// Tillstånd för idéverktyget. Finns bara i minnet och försvinner när fliken stängs.
const tillstand = { steg: 1, ide: "", svar: {}, valda: null, resultat: null };

// ---------- Hjälpfunktioner ----------

function el(tagg, attr = {}, ...barn) {
  const n = document.createElement(tagg);
  for (const [k, v] of Object.entries(attr)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (v === true) n.setAttribute(k, "");
    else n.setAttribute(k, v);
  }
  for (const b of barn.flat()) {
    if (b === null || b === undefined || b === false) continue;
    n.append(b instanceof Node ? b : document.createTextNode(String(b)));
  }
  return n;
}

function lank(url, text) {
  // Bara http(s)-länkar visas som länkar.
  if (!/^https?:\/\//i.test(url || "")) return document.createTextNode(text);
  return el("a", { href: url, rel: "noopener noreferrer", target: "_blank" }, text);
}

const datumFormat = new Intl.DateTimeFormat("sv-SE", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
const datum = (iso) => datumFormat.format(new Date(iso + "T00:00:00Z"));
const dagarTill = (iso) => Math.round((Date.parse(iso + "T00:00:00Z") - Date.parse(IDAG + "T00:00:00Z")) / 86400000);
const kronor = (n) => n.toLocaleString("sv-SE") + " kr";

const STATUS = { passar: "Passar", kanske: "Kanske", passar_inte: "Föll bort", vagvisare: "Vägvisare" };
const TYP = { utlysning: "Utlysning", lopande: "Löpande", vagvisare: "Vägvisare" };

// Lägger till innehåll i vyn och hoppar över tomma delar.
function lagg(...delar) {
  vy.append(...delar.flat().filter((d) => d !== null && d !== undefined && d !== false));
}

function sattTitel(text) {
  document.title = text ? `${text} | Utlysningsradarn` : "Utlysningsradarn";
}

function fokusera() {
  const h = vy.querySelector("h1");
  if (h) { h.setAttribute("tabindex", "-1"); h.focus({ preventScroll: true }); }
  window.scrollTo(0, 0);
}

function nastaText(post) {
  const n = nastaSistaDag(post, IDAG);
  if (!n) return post.typ === "lopande" ? "Nästa inlämningsdag är inte publicerad" : null;
  const d = dagarTill(n.datum);
  const steg = post.typ === "utlysning" && n.steg ? n.steg.replace(/^\d+\.\s*/, "") : "";
  return `Sista dag ${datum(n.datum)}${n.tid ? " kl. " + n.tid : ""} (${d === 0 ? "i dag" : d + " dagar kvar"})${steg ? ". Gäller " + steg.charAt(0).toLowerCase() + steg.slice(1) : ""}`;
}

function kallLista(post) {
  return el("ul", {}, post.kallor.filter((k) => k.roll !== "sekundar").map((k) => el("li", {}, lank(k.url, k.titel))));
}

// ---------- Idéverktyget ----------

function stegLista() {
  const namn = ["Beskriv idén", "Svara på frågorna", "Se urvalet", "Kopiera prompten"];
  return el("ol", { class: "steg", "aria-label": "Steg" },
    namn.map((n, i) => el("li", { "aria-current": tillstand.steg === i + 1 ? "step" : null }, n)));
}

function visaIde() {
  sattTitel("Pröva en idé");
  vy.replaceChildren();
  if (tillstand.steg === 1) return visaSteg1();
  if (tillstand.steg === 2) return visaSteg2();
  if (tillstand.steg === 3) return visaSteg3();
  return visaSteg4();
}

function visaSteg1() {
  const ord = () => tillstand.ide.trim().split(/\s+/).filter(Boolean).length;
  const raknare = el("p", { class: "raknare", id: "ide-raknare" });
  const uppdatera = () => {
    const n = ord();
    raknare.textContent = n < TUNN_IDE_ORD
      ? `${n} ord. Med minst ${TUNN_IDE_ORD} ord kan din AI bedöma idén mot kriterierna direkt; annars börjar den med frågor.`
      : `${n} ord.`;
  };
  const falt = el("textarea", {
    id: "ide", name: "ide", "aria-describedby": "ide-hjalp ide-raknare", spellcheck: "true",
    oninput: (e) => { tillstand.ide = e.target.value; uppdatera(); },
  });
  falt.value = tillstand.ide;
  uppdatera();

  lagg(
    el("h1", {}, "Vilken finansiering passar din idé?"),
    el("p", { class: "ingress" }, "Beskriv idén och svara på några frågor. Du får ett urval av utlysningar med skäl, och en färdig instruktion att klistra in i den AI-tjänst du själv använder för en djupare bedömning."),
    stegLista(),
    el("label", { for: "ide" }, "Beskriv idén"),
    el("p", { class: "hjalp", id: "ide-hjalp" }, "Skriv vad ni vill göra, för vem, och vilket resultat det ska ge. Berätta gärna vilka som är med och vad ni redan har gjort. Texten stannar i din webbläsare."),
    falt,
    raknare,
    el("div", { class: "knappar" },
      el("button", { type: "button", onclick: () => { tillstand.steg = 2; visaIde(); fokusera(); } }, "Fortsätt till frågorna")),
  );
}

function fragaSynlig(f) {
  if (!f.visas_om) return true;
  return Object.entries(f.visas_om).every(([id, varden]) => varden.includes(tillstand.svar[id]));
}

function visaSteg2() {
  const form = el("form", { onsubmit: (e) => e.preventDefault() });
  const rita = () => {
    form.replaceChildren();
    for (const f of FRAGOR.fragor) {
      if (!fragaSynlig(f)) { delete tillstand.svar[f.id]; continue; }
      const fs = el("fieldset", {}, el("legend", {}, f.fraga));
      if (f.hjalptext) fs.append(el("p", { class: "hjalp" }, f.hjalptext));
      for (const a of f.alternativ) {
        const id = `${f.id}-${a.id}`;
        let markerad;
        if (f.typ === "flera_val") markerad = (tillstand.svar[f.id] || []).includes(a.id);
        else markerad = tillstand.svar[f.id] === a.id;
        const input = el("input", {
          type: f.typ === "flera_val" ? "checkbox" : "radio", name: f.id, id, value: a.id, checked: markerad,
          onchange: (e) => {
            if (f.typ === "flera_val") {
              const lista = new Set(tillstand.svar[f.id] || []);
              e.target.checked ? lista.add(a.id) : lista.delete(a.id);
              tillstand.svar[f.id] = [...lista];
            } else {
              tillstand.svar[f.id] = a.id;
            }
            if (f.id === "organisationstyp") { rita(); document.getElementById(id)?.focus(); }
          },
        });
        fs.append(el("label", { class: "val", for: id }, input, el("span", {}, a.text)));
      }
      form.append(fs);
    }
  };
  rita();

  lagg(
    el("h1", {}, "Några frågor om förutsättningarna"),
    el("p", { class: "ingress" }, "Svaren används för att sortera utlysningarna. Hoppa över det du inte vet; ett obesvarat eller osäkert svar sorterar aldrig bort något."),
    stegLista(),
    form,
    el("div", { class: "knappar" },
      el("button", { type: "button", class: "sekundar", onclick: () => { tillstand.steg = 1; visaIde(); fokusera(); } }, "Tillbaka"),
      el("button", { type: "button", onclick: () => { tillstand.resultat = null; tillstand.valda = null; tillstand.steg = 3; visaIde(); fokusera(); } }, "Visa urvalet")),
  );
}

function skalLista(bedomning) {
  const skal = bedomning.skal.filter((s) => s.text && s.utfall !== "passar");
  if (!skal.length) return null;
  return el("ul", {}, skal.map((s) => el("li", {}, s.text)));
}

function postKort(post, bedomning, medVal) {
  const valt = tillstand.valda.has(post.id);
  const kort = el("article", { class: `post ${bedomning.utfall}` },
    el("h3", {}, post.titel),
    el("p", { class: "fakta" }, [post.finansiar.namn, TYP[post.typ], nastaText(post)].filter(Boolean).join(". ") + "."),
  );

  if (post.typ === "vagvisare") {
    kort.append(el("p", {}, post.besked));
    for (const v of bedomning.vagar) {
      const full = post.vagar.find((x) => x.id === v.id);
      const besked = !v.fordelning && full.fordelning && full.besked_utan_fordelning ? full.besked_utan_fordelning : v.besked;
      const vag = el("div", { class: "vag" },
        el("h4", {}, v.namn, " ", el("span", { class: `status ${v.utfall}` }, `(${v.utfall === "passar_inte" ? "inte aktuell" : STATUS[v.utfall].toLowerCase()})`)));
      if (v.utfall !== "passar_inte") {
        if (v.fordelning) vag.append(el("p", {}, `Gäller er: ${v.fordelning.namn}.`, v.fordelning.url ? [" ", lank(v.fordelning.url, "Läs mer")] : []));
        const skal = v.skal.filter((s) => s.text && s.utfall !== "passar");
        if (skal.length) vag.append(el("ul", {}, skal.map((s) => el("li", {}, s.text))));
        if (besked) vag.append(el("p", {}, besked));
        if (v.leder_till?.url) vag.append(el("p", {}, lank(v.leder_till.url, "Läs vidare hos källan")));
        else if (v.leder_till?.hur_hitta) vag.append(el("p", { class: "hjalp" }, v.leder_till.hur_hitta));
      }
      kort.append(vag);
    }
  } else {
    kort.append(el("p", {}, post.sammanfattning));
    const skal = skalLista(bedomning);
    if (skal) kort.append(el("p", { class: "hjalp" }, "Att tänka på:"), skal);
    if (post.precision === "lag") kort.append(el("p", { class: "hjalp" }, "Finansiären publicerar inga bedömningskriterier, så bedömningen blir grövre."));
    kort.append(el("details", {}, el("summary", {}, "Källor och kontroll"),
      el("p", { class: "hjalp" }, `Senast kontrollerad ${datum(post.kontroll.senast)}.`), kallLista(post)));
  }

  if (medVal) {
    const id = `ta-med-${post.id}`;
    const input = el("input", {
      type: "checkbox", id, checked: valt,
      onchange: (e) => {
        e.target.checked ? tillstand.valda.add(post.id) : tillstand.valda.delete(post.id);
        uppdateraVal();
      },
    });
    input.dataset.post = post.id;
    kort.append(el("div", { class: "medtag" }, el("label", { class: "val", for: id }, input, el("span", {}, "Ta med i prompten"))));
  }
  return kort;
}

function uppdateraVal() {
  const fullt = tillstand.valda.size >= MAX_POSTER;
  for (const cb of vy.querySelectorAll("input[data-post]")) cb.disabled = !cb.checked && fullt;
  const info = document.getElementById("val-info");
  if (info) info.textContent = `${tillstand.valda.size} av högst ${MAX_POSTER} valda.`;
  const knapp = document.getElementById("skapa-prompt");
  if (knapp) knapp.disabled = tillstand.valda.size === 0;
}

function visaSteg3() {
  if (!tillstand.resultat) tillstand.resultat = filtrera(DATA.poster, tillstand.svar, IDAG);
  const { aktuella, bortfallna } = tillstand.resultat;
  if (!tillstand.valda) tillstand.valda = new Set(aktuella.slice(0, MAX_POSTER).map((r) => r.post.id));

  lagg(
    el("h1", {}, "Det här kan passa din idé"),
    el("p", { class: "ingress" }, "Urvalet bygger på dina svar och enkla regler. Läs skälen, och välj vilka du vill ta med i prompten för en djupare bedömning."),
    stegLista(),
  );

  const grupper = [
    ["passar", "Passar enligt dina svar"],
    ["kanske", "Kan passa, men kontrollera"],
    ["vagvisare", "Vägar att undersöka"],
  ];
  for (const [utfall, rubrik] of grupper) {
    const poster = aktuella.filter((r) => r.bedomning.utfall === utfall);
    if (!poster.length) continue;
    lagg(el("section", { class: "grupp" },
      el("h2", {}, el("span", { class: `markor ${utfall}`, "aria-hidden": "true" }), rubrik),
      poster.map((r) => postKort(r.post, r.bedomning, true))));
  }
  if (!aktuella.length) {
    lagg(el("p", { class: "varning" }, "Inget i underlaget passar dina svar just nu. Se vad som föll bort och varför, eller gå tillbaka och ändra svar som du är osäker på."));
  }
  if (bortfallna.length) {
    lagg(el("section", { class: "grupp" },
      el("details", {},
        el("summary", {}, `Föll bort (${bortfallna.length})`),
        bortfallna.map((r) => postKort(r.post, r.bedomning, false)))));
  }

  lagg(el("div", { class: "knappar" },
    el("button", { type: "button", class: "sekundar", onclick: () => { tillstand.steg = 2; visaIde(); fokusera(); } }, "Ändra svaren"),
    el("button", { type: "button", id: "skapa-prompt", onclick: () => { tillstand.steg = 4; visaIde(); fokusera(); } }, "Skapa prompten"),
    el("span", { class: "hjalp", id: "val-info", "aria-live": "polite" })));
  uppdateraVal();
}

function visaSteg4() {
  const valda = tillstand.resultat.aktuella.filter((r) => tillstand.valda.has(r.post.id)).map((r) => r.post);
  const text = byggPrompt({ poster: valda, svar: tillstand.svar, ide: tillstand.ide, idag: IDAG, fragor: FRAGOR });
  const kort = arTunnIde(tillstand.ide);

  const ruta = el("textarea", { id: "prompt", class: "prompt", readonly: true, "aria-describedby": "prompt-info" });
  ruta.value = text;
  ruta.addEventListener("focus", () => ruta.select());
  const kvitto = el("span", { class: "kvitto", role: "status" });

  const kopiera = async () => {
    try {
      await navigator.clipboard.writeText(text);
      kvitto.textContent = "Kopierad. Klistra in den i en ny konversation.";
    } catch {
      ruta.focus();
      ruta.select();
      kvitto.textContent = "Kopieringen gick inte automatiskt. Texten är markerad: tryck Ctrl+C eller Cmd+C.";
    }
  };

  lagg(
    el("h1", {}, "Din prompt är klar"),
    el("p", { class: "ingress" }, "Prompten innehåller din idé, dina svar och underlaget för de utlysningar du valde. Den skickas ingenstans förrän du själv klistrar in den."),
    stegLista(),
    el("ol", { class: "instruktion" },
      el("li", {}, "Kopiera prompten."),
      el("li", {}, "Öppna en ny konversation i Claude, ChatGPT eller den AI-tjänst du använder."),
      el("li", {}, "Klistra in och skicka. Svara på AI:ns frågor; den rangordnar först när den vet vad som är viktigast för dig.")),
    kort ? el("p", { class: "varning" }, "Din beskrivning är kort. Prompten ber därför AI:n att börja med frågor och bedöma kriterierna först när du svarat.") : null,
    el("p", { class: "hjalp" }, "Tänk på vad du delar: din idé hamnar hos den AI-tjänst du klistrar in den i, enligt den tjänstens villkor."),
    el("div", { class: "knappar" },
      el("button", { type: "button", onclick: kopiera }, "Kopiera prompten"),
      kvitto),
    el("p", { class: "hjalp", id: "prompt-info" }, `${text.length.toLocaleString("sv-SE")} tecken. Om knappen inte fungerar: markera texten nedan och kopiera den.`),
    ruta,
    el("div", { class: "knappar" },
      el("button", { type: "button", class: "sekundar", onclick: () => { tillstand.steg = 3; visaIde(); fokusera(); } }, "Ändra urvalet"),
      el("button", { type: "button", class: "sekundar", onclick: borjaOm }, "Börja om med en ny idé")),
  );
}

function borjaOm() {
  tillstand.steg = 1; tillstand.ide = ""; tillstand.svar = {}; tillstand.valda = null; tillstand.resultat = null;
  visaIde(); fokusera();
}

// ---------- Radarn ----------

const radarFilter = { finansiar: "", typ: "" };

function visaRadar() {
  sattTitel("Alla utlysningar");
  vy.replaceChildren();

  const sorterade = [...DATA.poster].sort((a, b) => {
    const ordning = (p) => (p.typ === "vagvisare" ? 2 : nastaSistaDag(p, IDAG) ? 0 : 1);
    const oa = ordning(a), ob = ordning(b);
    if (oa !== ob) return oa - ob;
    const da = nastaSistaDag(a, IDAG)?.datum ?? "9999", db = nastaSistaDag(b, IDAG)?.datum ?? "9999";
    return da.localeCompare(db) || a.titel.localeCompare(b.titel, "sv");
  });

  const finansiarer = [...new Map(DATA.poster.map((p) => [p.finansiar.id, p.finansiar.namn])).entries()]
    .sort((a, b) => a[1].localeCompare(b[1], "sv"));

  const lista = el("ul", { class: "radar" });
  const antal = el("p", { class: "hjalp", "aria-live": "polite" });

  const rita = () => {
    const synliga = sorterade.filter((p) =>
      (!radarFilter.finansiar || p.finansiar.id === radarFilter.finansiar) && (!radarFilter.typ || p.typ === radarFilter.typ));
    antal.textContent = `${synliga.length} av ${sorterade.length} visas, sorterade efter sista dag.`;
    lista.replaceChildren(...synliga.map(radarRad));
    if (!synliga.length) lista.append(el("li", { class: "tom" }, "Inget matchar filtret."));
  };

  const valj = (id, etikett, alternativ, nyckel) => {
    const s = el("select", { id, onchange: (e) => { radarFilter[nyckel] = e.target.value; rita(); } },
      alternativ.map(([v, t]) => el("option", { value: v, selected: radarFilter[nyckel] === v }, t)));
    return el("div", {}, el("label", { for: id }, etikett), s);
  };

  lagg(
    el("h1", {}, "Alla utlysningar"),
    el("p", { class: "ingress" }, "Öppna och kommande utlysningar, löpande kanaler och vägvisare. Varje post visar när den senast kontrollerades mot källan."),
    el("div", { class: "filter" },
      valj("f-finansiar", "Finansiär", [["", "Alla finansiärer"], ...finansiarer], "finansiar"),
      valj("f-typ", "Typ", [["", "Alla typer"], ["utlysning", "Utlysningar"], ["lopande", "Löpande kanaler"], ["vagvisare", "Vägvisare"]], "typ")),
    antal,
    lista,
  );
  rita();
}

function radarRad(post) {
  const n = nastaSistaDag(post, IDAG);
  let dagar;
  if (post.typ === "vagvisare") {
    dagar = el("div", { class: "dagar ingen" }, el("span", { class: "tal" }, "Vägvisare"));
  } else if (n) {
    const d = dagarTill(n.datum);
    dagar = el("div", { class: `dagar${d <= 30 ? " nara" : ""}` },
      el("span", { class: "tal" }, String(d)),
      el("span", { class: "enhet" }, d === 1 ? "dag kvar" : "dagar kvar"));
  } else {
    dagar = el("div", { class: "dagar lopande" }, el("span", { class: "tal" }, post.typ === "lopande" ? "Löpande" : "Stängd"));
  }

  const fakta = [post.finansiar.namn, TYP[post.typ]];
  if (n) fakta.push(`Sista dag ${datum(n.datum)}${n.tid ? " kl. " + n.tid : ""}`);
  if (post.belopp?.max_sek) fakta.push(`Högst ${kronor(post.belopp.max_sek)}`);

  const detaljer = el("details", {}, el("summary", {}, "Krav, osäkerheter och källor"));
  const behorighet = (post.krav || []).filter((k) => k.skarpt && k.skede !== "ansokan");
  if (behorighet.length) detaljer.append(el("p", { class: "hjalp" }, "Behörighetskrav:"), el("ul", {}, behorighet.map((k) => el("li", {}, k.text))));
  if (post.bedomning?.kriterier?.length) {
    detaljer.append(el("p", { class: "hjalp" }, "Bedömningskriterier:"),
      el("ul", {}, post.bedomning.kriterier.map((k) => el("li", {}, k.rubrik + (k.vikt != null ? ` (${Math.round(k.vikt * 100)} %)` : "")))));
  }
  if (post.vagar) detaljer.append(el("p", { class: "hjalp" }, "Vägar:"), el("ul", {}, post.vagar.map((v) => el("li", {}, v.namn))));
  if (post.osakerheter?.length) detaljer.append(el("p", { class: "hjalp" }, "Osäkerheter:"), el("ul", {}, post.osakerheter.map((o) => el("li", {}, o))));
  detaljer.append(el("p", { class: "hjalp" }, `Senast kontrollerad ${datum(post.kontroll.senast)}. Källor:`), kallLista(post));

  return el("li", { class: "rad" }, dagar,
    el("div", {},
      el("h3", {}, post.titel),
      el("p", { class: "fakta" }, fakta.join(". ") + "."),
      el("p", {}, post.sammanfattning),
      detaljer));
}

// ---------- Om ----------

function visaOm() {
  sattTitel("Om verktyget");
  vy.replaceChildren(
    el("h1", {}, "Om verktyget"),
    el("p", { class: "ingress" }, "Utlysningsradarn hjälper forskare, företag och offentliga aktörer att hitta forsknings- och innovationsutlysningar som passar en idé."),
    el("h2", {}, "Det du skriver stannar hos dig"),
    el("p", {}, "Sidan anropar ingen AI och skickar ingenting någonstans. Urvalet och prompten räknas fram i din webbläsare. Inget sparas, och det finns ingen besöksstatistik. När du stänger fliken är allt borta."),
    el("p", {}, "Först när du själv klistrar in prompten i en AI-tjänst lämnar idén din dator, och då gäller den tjänstens villkor."),
    el("h2", {}, "Vägledning, inte bedömning"),
    el("p", {}, "Underlaget är sammanställt från finansiärernas egna sidor, med länk till källan och datum för senaste kontroll. Det är inte finansiärernas bedömning, och uppgifter kan ha ändrats. Kontrollera alltid mot källan innan du söker."),
    el("p", {}, "Förhandsurvalet bygger på enkla regler. Ett osäkert svar sorterar aldrig bort något, och skälen visas alltid."),
    el("h2", {}, "Hur underlaget hålls aktuellt"),
    el("p", {}, "Finansiärernas sidor gås igenom varje vecka. Ändringar publiceras först efter manuell granskning. Finansiärer som inte tillåter automatisk hämtning kontrolleras för hand."),
    el("h2", {}, "Vem står bakom"),
    el("p", {}, "Verktyget drivs av Engströms Mickla AB. Koden och underlaget är öppna på GitHub."),
    el("p", {}, lank("https://github.com/EngstromsMickla/utlysning", "Se koden och underlaget på GitHub")),
  );
}

// ---------- Navigering ----------

function visa() {
  const vyNamn = (location.hash || "#ide").slice(1);
  for (const a of document.querySelectorAll("nav a")) {
    a.toggleAttribute("aria-current", a.dataset.vy === vyNamn);
    if (a.dataset.vy === vyNamn) a.setAttribute("aria-current", "page");
  }
  if (vyNamn === "radar") visaRadar();
  else if (vyNamn === "om") visaOm();
  else visaIde();
}

async function start() {
  try {
    const [p, f] = await Promise.all([
      fetch("data/poster.json", { cache: "no-cache" }).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
      fetch("data/fragor.json", { cache: "no-cache" }).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
    ]);
    DATA = p;
    FRAGOR = f;
  } catch {
    vy.replaceChildren(el("p", { class: "varning" }, "Underlaget kunde inte laddas. Ladda om sidan om en stund."));
    return;
  }
  const byggd = document.getElementById("byggd");
  if (byggd && DATA.byggd) byggd.textContent = `Underlaget publicerades ${datum(DATA.byggd)}.`;
  window.addEventListener("hashchange", () => { visa(); fokusera(); });
  visa();
}

start();
