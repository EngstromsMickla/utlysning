"""Validerar alla poster mot schemat och kontrollerar att filtervärden finns i fragor.json.
Körs lokalt och i GitHub Actions före varje publicering:  python3 scripts/validera.py
"""
import json, sys, pathlib
from jsonschema import Draft202012Validator, FormatChecker

ROT = pathlib.Path(__file__).resolve().parent.parent
schema = json.loads((ROT / "schema/post.schema.json").read_text())
fragor = json.loads((ROT / "schema/fragor.json").read_text())
giltiga = {f["id"]: {a["id"] for a in f["alternativ"]} for f in fragor["fragor"]}
validator = Draft202012Validator(schema, format_checker=FormatChecker())

def kolla_regel(fil, plats, fraga, regel, fel):
    for lista in ("passar", "kanske"):
        for v in regel.get(lista, []):
            if v not in giltiga[fraga]:
                fel.append(f"{fil}: {plats}.{fraga}.{lista} har okänt svar '{v}'")
    for v in regel.get("skal", {}):
        if v != "ovrigt" and v not in giltiga[fraga]:
            fel.append(f"{fil}: {plats}.{fraga}.skal har okänt svar '{v}'")

fel, ids = [], set()
for fil in sorted((ROT / "data/poster").glob("*.json")):
    post = json.loads(fil.read_text())
    for e in validator.iter_errors(post):
        fel.append(f"{fil.name}: {'/'.join(map(str, e.absolute_path)) or '(rot)'}: {e.message}")
    if post.get("id") in ids:
        fel.append(f"{fil.name}: id '{post['id']}' finns redan")
    ids.add(post.get("id"))
    if fil.stem != post.get("id"):
        fel.append(f"{fil.name}: filnamnet ska vara id + .json")
    for fraga, regel in post.get("filter", {}).items():
        kolla_regel(fil.name, "filter", fraga, regel, fel)
    for v in post.get("vagar", []):
        for fraga, regel in v.get("villkor", {}).items():
            kolla_regel(fil.name, f"vagar[{v['id']}].villkor", fraga, regel, fel)
        if "fordelning" in v:
            f = v["fordelning"]["fraga"]
            for u in v["fordelning"]["utfall"]:
                for s in u["svar"]:
                    if s not in giltiga[f]:
                        fel.append(f"{fil.name}: fördelning '{u['namn']}' har okänt svar '{s}'")

if fel:
    print("\n".join(fel)); sys.exit(1)
print(f"OK: {len(ids)} poster validerade")
