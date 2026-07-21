"""
Per-pick outcome intelligence — what history says each draft slot is worth.

    python data/build_pick_intel.py

For national-draft picks 1..40, aggregates every selection ever made at that
number (Draftguru /picks/{n}) into:
  - avg_games:  average career games — 1986-2020 draft cohort only, so
                still-active recent draftees don't drag the average down
  - aa_pct:     % of the cohort who made an All-Australian team (AA/AA40)
  - prem_pct:   % who played in a premiership ("Prem" honour)
  - rs_pct:     % who earned a Rising Star nomination (Wikipedia per-year
                nominee tables, matched by normalized name)
  - dvi:        the pick's official Draft Value Index points

Output: data/pick_intel.json, served at /api/pick-intel.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scraper"))
sys.stdout.reconfigure(encoding="utf-8")

from draftguru import fetch_pick_history
from identity import normalize_name
from rising_star import fetch_all as fetch_rising_star

MAX_PICK = 72  # covers all four projected rounds; cohorts stay ≥20 this deep
COHORT = (1986, 2020)  # national draft era, mature careers only

# Official AFL Draft Value Index (current 54-pick revision)
DVI = [3000, 2481, 2178, 1962, 1795, 1659, 1543, 1443, 1355, 1276, 1205, 1140,
       1080, 1024, 973, 924, 879, 836, 796, 757, 721, 686, 653, 621, 590, 561,
       533, 505, 479, 454, 429, 405, 382, 360, 338, 317, 297, 277, 257, 238,
       220, 202, 184, 167, 150, 134, 118, 102, 86, 71, 57, 42, 28, 14]

OUT_PATH = Path(__file__).resolve().parent / "pick_intel.json"


def main() -> None:
    print("Fetching Rising Star nominees (Wikipedia)...")
    nominees = fetch_rising_star(2025)
    nominee_names = {normalize_name(n) for names in nominees.values() for n in names}
    print(f"  {len(nominee_names)} distinct nominees since 1994")

    intel = {}
    print(f"Fetching pick histories 1..{MAX_PICK} (Draftguru)...")
    for pick in range(1, MAX_PICK + 1):
        rows = [r for r in fetch_pick_history(pick)
                if COHORT[0] <= r["year"] <= COHORT[1] and r["games"] is not None]
        if not rows:
            continue
        n = len(rows)
        aa = sum(1 for r in rows if any(h.startswith("AA") for h in r["honours"]))
        prem = sum(1 for r in rows if "Prem" in r["honours"])
        # Rising Star began 1994 — only 1994+ draftees could be nominated
        rs_rows = [r for r in rows if r["year"] >= 1994]
        rs = sum(1 for r in rs_rows if normalize_name(r["name"]) in nominee_names)
        intel[pick] = {
            "dvi": DVI[pick - 1] if pick <= len(DVI) else 0,
            "cohort_n": n,
            "avg_games": round(sum(r["games"] for r in rows) / n),
            "aa_pct": round(100 * aa / n),
            "prem_pct": round(100 * prem / n),
            "rs_pct": round(100 * rs / len(rs_rows)) if rs_rows else None,
        }
        print(f"  pick {pick:2d}: n={n:2d} avg {intel[pick]['avg_games']:3d} games, "
              f"AA {intel[pick]['aa_pct']}%, Prem {intel[pick]['prem_pct']}%, RS {intel[pick]['rs_pct']}%")

    payload = {
        "cohort": {"from": COHORT[0], "to": COHORT[1],
                   "note": "national drafts only; games/honours as recorded by Draftguru; "
                           "Rising Star rates use 1994+ draftees (award introduced 1994)"},
        "sources": {
            "pick_histories": "https://www.draftguru.com.au/picks/{n}",
            "rising_star": "https://en.wikipedia.org/wiki/{year}_AFL_Rising_Star",
            "dvi": "official AFL Draft Value Index (54-pick revision)",
        },
        "picks": intel,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=1), encoding="utf-8", newline="\n")
    print(f"wrote {OUT_PATH.name}: {len(intel)} picks")


if __name__ == "__main__":
    main()
