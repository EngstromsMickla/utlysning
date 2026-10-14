// Filtrering i webbläsaren. Inget skickas någonstans; funktionerna räknar bara
// på posterna och användarens svar. Samma fil körs i testerna med Node.

const RANG = { passar: 0, kanske: 1, passar_inte: 2 };
const varst = (a, b) => (RANG[a] >= RANG[b] ? a : b);


// Antal dagar från i dag som respektive tidsalternativ motsvarar (se fragor.json).
export const TIDSHORISONT_DAGAR = {
  inom_1_man: 0,
  "1_till_3_man": 30,
  "3_till_6_man": 90,
  over_6_man: 180,
};

function skalFor(regel, svarId) {
  if (!regel.skal) return null;
  return regel.skal[svarId] ?? regel.skal.ovrigt ?? null;
}

// Bedömer ett svar (eller flera vid flervalsfrågor) mot en filterregel.
// vet_ej ger alltid kanske. Vid flera valda svar räknas det bästa.
export function bedomRegel(regel, svar) {
  const lista = Array.isArray(svar) ? svar : [svar];
  let utfall = null;
  let text = null;
  for (const s of lista) {
    let u;
    if (s === "vet_ej") u = "kanske";
    else if ((regel.passar || []).includes(s)) u = "passar";
    else if ((regel.kanske || []).includes(s)) u = "kanske";
    else u = "passar_inte";
    if (utfall === null || RANG[u] < RANG[utfall]) {
      utfall = u;
      text = skalFor(regel, s);
    }
  }
  return { utfall: utfall ?? "passar_inte", text };
}

function iso(d) {
  return d.toISOString().slice(0, 10);
}

function plusDagar(idag, dagar) {
  const d = new Date(idag + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + dagar);
  return iso(d);
}

// Nästa sista ansökningsdag från och med idag.
export function nastaSistaDag(post, idag) {
  return (post.tidpunkter || [])
    .filter((t) => t.typ === "sista_dag" && t.datum >= idag)
    .sort((a, b) => a.datum.localeCompare(b.datum))[0] || null;
}

function bedomTid(post, svar, idag) {
  const nasta = nastaSistaDag(post, idag);
  if (!nasta) {
    if (post.typ === "lopande") {
      return { utfall: "kanske", text: "Nästa inlämningstid är inte publicerad än." };
    }
    return { utfall: "passar_inte", text: "Det finns ingen kommande sista ansökningsdag." };
  }
  const dagar = TIDSHORISONT_DAGAR[svar];
  const datumText = `${nasta.datum}${nasta.tid ? " kl. " + nasta.tid : ""}${nasta.steg ? " (" + nasta.steg + ")" : ""}`;
  if (svar === undefined || svar === null) return null;
  if (dagar === undefined) {
    return { utfall: "kanske", text: `Nästa sista dag är ${datumText}.` };
  }
  const tidigast = plusDagar(idag, dagar);
  if (nasta.datum >= tidigast) {
    return { utfall: "passar", text: `Nästa sista dag är ${datumText}.` };
  }
  // Finns det en senare inlämningstid som hinns med?
  const senare = (post.tidpunkter || [])
    .filter((t) => t.typ === "sista_dag" && t.datum >= tidigast)
    .sort((a, b) => a.datum.localeCompare(b.datum))[0];
  if (senare && post.typ === "lopande") {
    return { utfall: "passar", text: `Ni hinner till inlämningen ${senare.datum}.` };
  }
  if (post.typ === "lopande") {
    return { utfall: "kanske", text: `Nästa kända inlämning (${datumText}) är för tidig. Senare datum är inte publicerade än.` };
  }
  return { utfall: "passar_inte", text: `Sista dag ${datumText} infaller innan ni kan lämna in.` };
}

// Bedömer en utlysning eller löpande kanal mot alla svar.
// Returnerar { utfall, precision, skal: [{ fraga, utfall, text }] }.
export function bedomPost(post, svar, idag) {
  if (post.typ === "vagvisare") return bedomVagvisare(post, svar);

  const skal = [];
  let utfall = "passar";

  for (const [fraga, regel] of Object.entries(post.filter || {})) {
    const s = svar[fraga];
    if (s === undefined || s === null || (Array.isArray(s) && s.length === 0)) continue;
    const r = bedomRegel(regel, s);
    utfall = varst(utfall, r.utfall);
    skal.push({ fraga, utfall: r.utfall, text: r.text });
  }

  for (const k of post.kombinationer || []) {
    const traffar = Object.entries(k.nar).every(([fraga, varden]) => {
      const s = svar[fraga];
      const lista = Array.isArray(s) ? s : [s];
      return lista.some((v) => varden.includes(v));
    });
    if (traffar) {
      utfall = varst(utfall, k.utfall);
      skal.push({ fraga: "kombination", utfall: k.utfall, text: k.skal });
    }
  }

  const tid = bedomTid(post, svar.tidshorisont, idag);
  if (tid) {
    utfall = varst(utfall, tid.utfall);
    skal.push({ fraga: "tidshorisont", ...tid });
  }

  return { id: post.id, typ: post.typ, utfall, precision: post.precision, skal };
}

// Vägvisare: varje väg bedöms för sig. Utfallet säger om vägen är värd att
// undersöka, aldrig om användaren är behörig.
export function bedomVagvisare(post, svar) {
  const vagar = post.vagar.map((v) => {
    let utfall = "passar";
    const skal = [];
    for (const [fraga, regel] of Object.entries(v.villkor || {})) {
      const s = svar[fraga];
      if (s === undefined || s === null || (Array.isArray(s) && s.length === 0)) continue;
      const r = bedomRegel(regel, s);
      utfall = varst(utfall, r.utfall);
      skal.push({ fraga, utfall: r.utfall, text: r.text });
    }
    let fordelning = null;
    if (v.fordelning) {
      const s = svar[v.fordelning.fraga];
      const traff = v.fordelning.utfall.find((u) => u.svar.includes(s));
      fordelning = traff
        ? { ...traff, kontrollerad: v.fordelning.kontrollerad }
        : null;
    }
    return { id: v.id, namn: v.namn, utfall, skal, fordelning, leder_till: v.leder_till, besked: v.besked };
  });
  return { id: post.id, typ: post.typ, utfall: "vagvisare", precision: "ingen", besked: post.besked, vagar };
}

// Sorterar fram det som ska visas: passar först, sedan kanske. passar_inte
// returneras separat så att sidan kan visa varför något föll bort.
export function filtrera(poster, svar, idag) {
  const resultat = poster.map((p) => ({ post: p, bedomning: bedomPost(p, svar, idag) }));
  const ordning = { passar: 0, kanske: 1, vagvisare: 2, passar_inte: 3 };
  resultat.sort((a, b) => ordning[a.bedomning.utfall] - ordning[b.bedomning.utfall]);
  return {
    aktuella: resultat.filter((r) => r.bedomning.utfall !== "passar_inte"),
    bortfallna: resultat.filter((r) => r.bedomning.utfall === "passar_inte"),
  };
}
