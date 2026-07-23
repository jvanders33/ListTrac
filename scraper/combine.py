"""Draft Combine athletic testing — pipeline scaffold.

The AFL National Draft Combine (20m sprint, agility, standing & running vertical
jumps, 2km time trial) is the athletic-testing showcase for draft prospects. We
want each prospect's results on their profile — but two facts shape this build:

  1. TIMING. The National Combine is held in OCTOBER. For the 2026 draft class
     it hasn't happened yet, so there is nothing to show until then. This
     scaffold stands the pipeline up now so results wire straight onto the 2026
     prospect pages the day they drop.

  2. ACCESS. The AFL's structured feed (api.afl.com.au/cfs/afl/combineResults)
     exists but is entitlement-locked — it returns 403 with the public token.
     Only per-test top-10 leaderboards are public, published as prose inside
     afl.com.au news articles. So the fill path is a hand-curated layer
     (data/combine_manual.json) into which top-10 results (or a future feed) are
     entered, each with its source. No fabrication — an empty combine is an
     honest "not tested yet", never invented numbers.

Run this any time: with no manual data it writes an honest placeholder
(available=false); once combine_manual.json is populated it merges those in and
flips available=true.

    python scraper/combine.py     # -> data/combine_2026.json
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANUAL = ROOT / "data" / "combine_manual.json"
OUT = ROOT / "data" / "combine_2026.json"

YEAR = 2026
HELD = "October 2026"

# canonical test definitions (key, label, unit, lower_is_better)
TESTS = [
    {"key": "sprint20m", "label": "20m sprint", "unit": "s", "lower_better": True},
    {"key": "agility", "label": "Agility test", "unit": "s", "lower_better": True},
    {"key": "standing_vert", "label": "Standing vertical", "unit": "cm", "lower_better": False},
    {"key": "running_vert", "label": "Running vertical", "unit": "cm", "lower_better": False},
    {"key": "time_trial_2km", "label": "2km time trial", "unit": "min:s", "lower_better": True},
]
TEST_KEYS = {t["key"] for t in TESTS}


def _norm(name: str) -> str:
    import unicodedata
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]+", " ", name.lower()).strip()


def load_manual() -> dict:
    """Hand-curated combine results. Shape:
        {"events": [{"name": "...", "year": 2026, "combine": "National",
                     "results": {"sprint20m": 2.82, ...}, "source_url": "..."}]}
    Only recognised test keys are kept; each player's results are merged."""
    if not MANUAL.exists():
        return {}
    players: dict[str, dict] = {}
    for e in json.loads(MANUAL.read_text(encoding="utf-8")).get("events", []):
        nm = e.get("name")
        if not nm:
            continue
        res = {k: v for k, v in (e.get("results") or {}).items() if k in TEST_KEYS}
        if not res:
            continue
        rec = players.setdefault(_norm(nm), {"name": nm, "combine": e.get("combine", "National"),
                                             "year": e.get("year", YEAR), "tests": {},
                                             "source_url": e.get("source_url")})
        rec["tests"].update(res)
    return players


def main():
    players = load_manual()
    payload = {
        "year": YEAR,
        "held": HELD,
        "available": bool(players),
        "tests": TESTS,
        "attribution": "AFL National Draft Combine athletic testing. The AFL's full per-participant feed is access-locked; results here are hand-verified from the public top-10 leaderboards (afl.com.au) until/if the feed opens. Empty means not yet tested — the 2026 combine is held in October.",
        "count": len(players),
        "players": players,
    }
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    state = f"{len(players)} players" if players else "placeholder (no results yet — combine held " + HELD + ")"
    print(f"wrote {OUT}: {state}")


if __name__ == "__main__":
    main()
