"""Resolved AFL national draft order (post-trade-period), from Wikipedia.

Why this exists: the weekly rebuild can only *project* the order (reverse
ladder + recorded futures trades). Draftguru's trade-period blocks reference
this year's picks by the AFL's live pick number ("#15"), and that number
drifts as free-agency compensation picks are inserted during the period —
so replaying them is unreliable (the same "#25" can be four different slots).

Wikipedia's "{year} AFL draft" page publishes the official resolved order:
every slot with its current owner, the full "<-" trade chain back to the
natural owner, and the compensation picks in place. Once the trade period
closes, that is the source of truth for the draft board. This writes
data/draft_order_{year}.json; /api/draft-order prefers it over the
projection when present.

Each pick: pick, round, owner, origin (natural-slot owner = last club in the
chain), via (origin when traded, else null), chain, kind
(natural|traded|compensation), compensation_for (the free agent lost), note.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

OUT_DIR = Path(__file__).resolve().parent.parent / "data"
UA = {"User-Agent": "ListTrac (github.com/jvanders33/ListTrac)"}

# Wikipedia's club link text -> our abbreviation
WIKI_CLUB = {
    "Adelaide": "ADE", "Brisbane Lions": "BRI", "Brisbane": "BRI", "Carlton": "CAR",
    "Collingwood": "COL", "Essendon": "ESS", "Fremantle": "FRE", "Geelong": "GEE",
    "Gold Coast": "GCS", "Greater Western Sydney": "GWS", "GWS Giants": "GWS", "GWS": "GWS",
    "Hawthorn": "HAW", "Melbourne": "MEL", "North Melbourne": "NM", "Port Adelaide": "PA",
    "Richmond": "RIC", "St Kilda": "STK", "Sydney": "SYD", "West Coast": "WCE",
    "Western Bulldogs": "WB", "Tasmania": "TAS",
}
COMP_RE = re.compile(r"free agency compensation pick\s*\(\s*([^)]*?)\s*\)", re.I)
YEAR_RE = re.compile(r"\(\s*(\d{4})\s*\)")


def _club(name: str) -> str | None:
    name = re.sub(r"\s+", " ", name).strip()
    return WIKI_CLUB.get(name)


def _parse_notes(notes: str, owner: str) -> dict:
    """Decode the Notes cell: a '<-' chain of previous owners (oldest last), with
    optional '( YYYY )' trade-year markers and/or a compensation-pick marker."""
    comp_for = None
    m = COMP_RE.search(notes)
    if m:
        comp_for = m.group(1).strip() or None
        notes = COMP_RE.sub("", notes)
    chain = []
    parts = [s for s in re.split(r"←|<-", notes) if s.strip()]
    for seg in parts:
        year = YEAR_RE.search(seg)
        name = YEAR_RE.sub("", seg)
        ab = _club(name)
        if ab:
            chain.append({"club": ab, "year": int(year.group(1)) if year else None})
    if comp_for is not None:
        kind = "compensation"
        origin = chain[0]["club"] if chain else owner   # the club it was awarded to
    elif chain:
        kind = "traded"
        origin = chain[-1]["club"]                      # the natural-slot owner
    else:
        kind = "natural"
        origin = owner
    return {"kind": kind, "origin": origin, "chain": chain, "compensation_for": comp_for}


def fetch_order(year: int) -> list[dict]:
    url = f"https://en.wikipedia.org/wiki/{year}_AFL_draft"
    html = requests.get(url, headers=UA, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")
    # The resolved national order is the big table with a Notes column (the
    # mid-season rookie draft table has "Pick due to" and ~20 rows instead).
    best, best_rows = None, 0
    for t in soup.find_all("table"):
        heads = [h.get_text(" ", strip=True) for h in t.find_all("th")]
        if any(h.startswith("Pick") for h in heads) and any(h == "Notes" for h in heads):
            n = len(t.find_all("tr"))
            if n > best_rows:
                best, best_rows = t, n
    if best is None:
        return []
    picks, rnd = [], None
    for tr in best.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        text = [c.get_text(" ", strip=True) for c in cells]
        if not text or not any(x.isdigit() for x in text[:2]):
            continue
        if len(text) >= 7 and text[0].isdigit() and text[1].isdigit():
            rnd, pick_s, club_s, notes = int(text[0]), text[1], text[3], text[-1]
        elif len(text) >= 6 and text[0].isdigit():
            pick_s, club_s, notes = text[0], text[2], text[-1]
        else:
            continue
        owner = _club(club_s)
        if rnd is None or not owner:
            continue
        info = _parse_notes(notes, owner)
        picks.append({
            "pick": int(pick_s), "round": rnd,
            "club": owner, "origin": info["origin"],
            "via": info["origin"] if info["origin"] != owner else None,
            "chain": info["chain"], "kind": info["kind"],
            "compensation_for": info["compensation_for"],
            "note": notes or None,
        })
    picks.sort(key=lambda p: p["pick"])
    return picks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    a = ap.parse_args()
    picks = fetch_order(a.year)
    if len(picks) < 18:
        print(f"draft_order: only {len(picks)} picks parsed for {a.year} — not writing (page not yet published or layout changed)")
        return 0  # don't clobber a good file; the API falls back to the projection
    out = OUT_DIR / f"draft_order_{a.year}.json"
    kinds = {}
    for p in picks:
        kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
    payload = {
        "year": a.year,
        "source": "Wikipedia",
        "source_url": f"https://en.wikipedia.org/wiki/{a.year}_AFL_draft",
        "attribution": f"Official {a.year} national draft order as published on Wikipedia (post-trade-period), "
                       "including free-agency compensation picks and each slot's trade chain.",
        "fetched_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "count": len(picks), "rounds": max(p["round"] for p in picks), "kinds": kinds,
        "picks": picks,
    }
    out.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(picks)} picks ({kinds}) -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
