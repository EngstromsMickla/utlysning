"""Slår ihop alla poster till en fil som sidan läser. Körs av GitHub Actions före publicering.
   python3 scripts/bygg.py
"""
import json, pathlib, datetime
ROT = pathlib.Path(__file__).resolve().parent.parent
ut = ROT / "publik/data"
ut.mkdir(parents=True, exist_ok=True)
poster = [json.loads(f.read_text()) for f in sorted((ROT / "data/poster").glob("*.json"))]
(ut / "poster.json").write_text(json.dumps(
    {"byggd": datetime.date.today().isoformat(), "poster": poster}, ensure_ascii=False), encoding="utf-8")
(ut / "fragor.json").write_text((ROT / "schema/fragor.json").read_text(), encoding="utf-8")
print(f"Byggde publik/data med {len(poster)} poster")
