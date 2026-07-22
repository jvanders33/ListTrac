"""Percentile scouting reports — the FBref move, on AFL/Champion Data.

The AFL stats feed carries 60+ per-game metrics per player. This ranks each
player's output against their *position* peers across the whole league and
stores the percentile, so a player page can show a scouting radar ("elite
clearance winner, poor overhead marker") instead of raw numbers.

    python scraper/scouting.py     # -> data/scouting_2026.json

Percentiles are computed within the seven Champion Data position groups among
players with enough games; the same token/endpoint as the ratings scraper.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

API = "https://api.afl.com.au"
H = {"User-Agent": "Mozilla/5.0 ListTrac (github.com/jvanders33/ListTrac)",
     "Origin": "https://www.afl.com.au", "Referer": "https://www.afl.com.au/"}
OUT = Path(__file__).resolve().parent.parent / "data" / "scouting_2026.json"
YEAR = 2026
MIN_GAMES = 4  # players below this are excluded from the ranking pool

POS_LABEL = {
    "MIDFIELDER": "Midfielder", "MIDFIELDER_FORWARD": "Midfielder-Forward",
    "KEY_FORWARD": "Key forward", "MEDIUM_FORWARD": "Small/medium forward",
    "KEY_DEFENDER": "Key defender", "MEDIUM_DEFENDER": "Small/medium defender",
    "RUCK": "Ruck",
}
# (key, label, group) — 12 stats, four per group, all "more is better"
STATS = [
    ("disposals", "Disposals", "ball"),
    ("contestedPossessions", "Contested poss", "ball"),
    ("totalClearances", "Clearances", "ball"),
    ("metresGained", "Metres gained", "ball"),
    ("inside50s", "Inside 50s", "attack"),
    ("scoreInvolvements", "Score involv.", "attack"),
    ("goals", "Goals", "attack"),
    ("marks", "Marks", "attack"),
    ("intercepts", "Intercepts", "defence"),
    ("rebound50s", "Rebound 50s", "defence"),
    ("tackles", "Tackles", "defence"),
    ("pressureActs", "Pressure acts", "defence"),
]


def _norm(name: str) -> str:
    import unicodedata
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]+", " ", name.lower()).strip()


def mint():
    r = requests.post(f"{API}/cfs/afl/WMCTok", headers={**H, "Content-Length": "0"}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


def fetch():
    tok = mint()
    r = requests.get(f"{API}/statspro/playersStats/seasons/CD_S{YEAR}014",
                     headers={**H, "x-media-mis-token": tok}, timeout=30)
    r.raise_for_status()
    time.sleep(0.5)
    return r.json()["players"]


def percentile(sorted_vals: list[float], v: float) -> int:
    """Share of the pool with a value <= v (0-100)."""
    if not sorted_vals:
        return 0
    import bisect
    lo = bisect.bisect_left(sorted_vals, v)
    hi = bisect.bisect_right(sorted_vals, v)
    return round((lo + hi) / 2 / len(sorted_vals) * 100)


def build():
    players = fetch()
    rows = []
    for p in players:
        d, av = p["playerDetails"], p.get("averages") or {}
        pos = d.get("position")
        games = int(p.get("gamesPlayed") or av.get("matchesPlayed") or 0)
        if pos not in POS_LABEL or games < MIN_GAMES:
            continue
        rows.append({
            "name": f"{d['givenName']} {d['surname']}", "norm": _norm(f"{d['givenName']} {d['surname']}"),
            "pos": pos, "games": games,
            "vals": {k: (av.get(k) if isinstance(av.get(k), (int, float)) else None) for k, _, _ in STATS},
        })

    # per-position sorted value lists for each stat
    pools: dict[str, dict[str, list]] = {}
    for r in rows:
        pos = pools.setdefault(r["pos"], {k: [] for k, _, _ in STATS})
        for k in pos:
            if r["vals"].get(k) is not None:
                pos[k].append(r["vals"][k])
    for pos in pools.values():
        for k in pos:
            pos[k].sort()

    out = {}
    for r in rows:
        pos_pools = pools[r["pos"]]
        stats = {}
        for k, label, group in STATS:
            v = r["vals"].get(k)
            if v is None:
                continue
            stats[k] = {"label": label, "group": group, "avg": round(v, 1),
                        "pct": percentile(pos_pools[k], v)}
        out[r["norm"]] = {
            "name": r["name"], "position": r["pos"], "position_label": POS_LABEL[r["pos"]],
            "games": r["games"], "pool_size": sum(1 for x in rows if x["pos"] == r["pos"]),
            "stats": stats,
        }
    return out


def main():
    data = build()
    OUT.write_text(json.dumps({
        "year": YEAR, "min_games": MIN_GAMES,
        "attribution": "Percentiles vs same-position peers, from AFL/Champion Data per-game averages.",
        "order": [k for k, _, _ in STATS],
        "labels": {k: {"label": label, "group": group} for k, label, group in STATS},
        "players": data,
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote scouting for {len(data)} players -> {OUT}")
    # spot-check
    for nm in ("marcus bontempelli", "harry sheezel", "sam darcy"):
        p = data.get(nm)
        if p:
            top = sorted(p["stats"].values(), key=lambda s: -s["pct"])[:3]
            print(f"  {p['name']} ({p['position_label']}): " + ", ".join(f"{s['label']} {s['pct']}%" for s in top))


if __name__ == "__main__":
    main()
