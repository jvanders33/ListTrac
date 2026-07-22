"""Draft-pathway & second-tier stats, direct from the AFL (Champion Data).

Cracks the same api.afl.com.au statspro feed used for AFL Player Ratings, but
for the competitions a draft prospect actually plays in:

    CD_C011  Talent League Boys      (the Coates Talent League)
    CD_C019  U18 Boys Championships
    CD_C015  VFL                     (senior state league — where a top-ager
    CD_C016  SANFL                    plays on the way up; RMC misses these)

Season codes are CD_S{year}{comp}. A short-lived MIS token minted from the
public WMCTok endpoint (same call the AFL site makes) unlocks it.

Each prospect is identified by their stable Champion Data playerId from a
junior competition (a name match there is unambiguously the prospect), then
their senior VFL/SANFL rows are pulled by that same id — so "Cody Walker" the
prospect gets *his* Carlton VFL games, not another Walker's.

This is the direct source RMC aggregates from, and it's more complete: it has
the current season and senior football RMC lacks. It MERGES into the RMC
history in data/prospect_stats.json — RMC's richer older rows (which include
clearances, contested ball, plus WAFL and U16 championships the AFL feed
doesn't carry) are kept; the AFL feed adds every row RMC is missing.

    python scraper/afl_talent.py            # merge AFL stats into prospect_stats.json

Run AFTER prospect_stats.py (RMC) in the weekly job so it merges onto fresh RMC data.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

API = "https://api.afl.com.au"
HEADERS = {
    "User-Agent": "Mozilla/5.0 ListTrac (github.com/jvanders33/ListTrac)",
    "Origin": "https://www.afl.com.au", "Referer": "https://www.afl.com.au/",
}
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STATS_PATH = DATA_DIR / "prospect_stats.json"

# our league label -> (Champion Data competition code, is_junior_pathway)
COMPS = [
    ("Coates Talent League", "011", True),
    ("U18 Championships", "019", True),
    ("VFL", "015", False),
    ("SANFL League", "016", False),
]
YEARS = [2024, 2025, 2026]


def _norm(name: str) -> str:
    return re.sub(r"[^a-z]", "", (name or "").lower())


def mint_token() -> str:
    r = requests.post(f"{API}/cfs/afl/WMCTok", headers={**HEADERS, "Content-Length": "0"}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


def fetch_season(code: str, year: int, token: str):
    r = requests.get(f"{API}/statspro/playersStats/seasons/CD_S{year}{code}",
                     headers={**HEADERS, "x-media-mis-token": token}, timeout=30)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    time.sleep(0.6)
    return r.json().get("players", [])


def _int(v):
    return int(v) if isinstance(v, (int, float)) else None


def to_row(label: str, code: str, year: int, p: dict) -> dict | None:
    t = p.get("totals", {})
    games = int(p.get("gamesPlayed") or t.get("matchesPlayed") or 0)
    if games <= 0:
        return None
    disp, goals = _int(t.get("disposals")), _int(t.get("goals"))
    return {
        "league": label, "league_id": f"afl:{code}", "season": str(year),
        "team": (p.get("team") or {}).get("teamName", ""),
        "gamesplayed": games, "disposals": disp, "kicks": _int(t.get("kicks")),
        "handballs": _int(t.get("handballs")), "marks": _int(t.get("marks")),
        "tackles": _int(t.get("tackles")), "clr": None, "i": _int(t.get("inside50s")),
        "cp": None, "hitouts": _int(t.get("hitouts")), "goals": goals,
        "avg_disposals": round(disp / games, 1) if disp else None,
        "avg_goals": round(goals / games, 1) if goals else None,
        "source": "afl",
    }


def collect(token: str):
    """Returns (by_cd: cd_id -> rows[], junior_name_to_cd: norm -> set(cd))."""
    by_cd: dict[str, list] = {}
    junior_name_to_cd: dict[str, set] = {}
    for label, code, junior in COMPS:
        for year in YEARS:
            try:
                players = fetch_season(code, year, token)
            except requests.RequestException as e:
                print(f"  ! {label} {year}: {e}")
                continue
            print(f"  {label} {year}: {len(players)} players")
            for p in players:
                cd = p.get("playerId")
                if not cd:
                    continue
                row = to_row(label, code, year, p)
                if row:
                    by_cd.setdefault(cd, []).append(row)
                if junior:
                    d = p["playerDetails"]
                    nm = _norm(f"{d.get('givenName', '')}{d.get('surname', '')}")
                    junior_name_to_cd.setdefault(nm, set()).add(cd)
    return by_cd, junior_name_to_cd


def merge():
    if not STATS_PATH.exists():
        print("prospect_stats.json missing — run prospect_stats.py first")
        return
    stats = json.loads(STATS_PATH.read_text(encoding="utf-8"))
    players = stats.get("players", {})

    # prospect pool names (so we catch prospects RMC never matched)
    pool_names = {}
    for f in ("prospects_2026.json", "prospects_2027.json", "prospects_2028.json"):
        path = DATA_DIR / f
        if path.exists():
            for pr in json.loads(path.read_text(encoding="utf-8")).get("prospects", []):
                pool_names[pr["name"]] = True

    token = mint_token()
    print("collecting AFL Champion Data comps…")
    by_cd, junior_name_to_cd = collect(token)

    names = set(players) | set(pool_names)
    added_rows = added_players = 0
    for name in names:
        entry = players.get(name) or {"history": []}
        rmc_rows = entry.get("history", [])
        have = {(r["league"], str(r["season"])) for r in rmc_rows}
        cds = junior_name_to_cd.get(_norm(name), set())
        afl_rows = [r for cd in cds for r in by_cd.get(cd, [])]
        new = [r for r in afl_rows if (r["league"], r["season"]) not in have]
        if not new:
            continue
        # de-dupe AFL rows among themselves (same league+season)
        seen, deduped = set(), []
        for r in sorted(new, key=lambda r: (r["league"], r["season"])):
            k = (r["league"], r["season"])
            if k not in seen:
                seen.add(k)
                deduped.append(r)
        merged = rmc_rows + deduped
        merged.sort(key=lambda r: (str(r["season"]), r["league"]), reverse=True)
        if name not in players:
            added_players += 1
            entry = {"afl_cd_id": next(iter(cds), None)}
        entry["history"] = merged
        players[name] = entry
        added_rows += len(deduped)

    stats["players"] = players
    stats["source"] = "Rookie Me Central + AFL (Champion Data)"
    stats["source_url"] = "https://www.afl.com.au/stats"
    stats["leagues"] = sorted({r["league"] for e in players.values() for r in e.get("history", [])})
    stats["attribution"] = ("Playing history from Rookie Me Central, enriched with official "
                            "AFL/Champion Data stats for the Coates Talent League, U18 "
                            "Championships, VFL and SANFL — including current-season and "
                            "senior state-league games. No dollar figures; stats only.")
    STATS_PATH.write_text(json.dumps(stats, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"merged: +{added_rows} AFL rows across prospects, +{added_players} new prospects")


if __name__ == "__main__":
    merge()
