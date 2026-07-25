"""Milestone watch — the Coleman Medal race and players nearing a games milestone.

Two things fans track through a season that ListTrac didn't surface: who's
leading the goalkicking (the Coleman Medal), and who's about to bring up 50 /
100 / 150 / 200 games.

Season goals come from the AFL/Champion Data season feed (exact this-season
totals). Career games are summed from the ratings history — which only runs from
2015 — so games milestones are shown ONLY for players who debuted in 2015 or
later, where that sum equals their true career total. Veterans who debuted
earlier are left out rather than shown a wrong number; a real bulk career-games
source would extend it.

    python scraper/milestones.py     # -> data/milestones_2026.json
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "data" / "ratings_history.json"
OUT = ROOT / "data" / "milestones_2026.json"
API = "https://api.afl.com.au"
H = {"User-Agent": "Mozilla/5.0 ListTrac (github.com/jvanders33/ListTrac)",
     "Origin": "https://www.afl.com.au", "Referer": "https://www.afl.com.au/"}
YEAR = 2026
STEPS = [50, 100, 150, 200, 250, 300]
NEAR = 15                         # within this many games = "approaching"

CD_ABBR = {"ADEL": "ADE", "BL": "BRI", "CARL": "CAR", "COLL": "COL", "ESS": "ESS",
           "FRE": "FRE", "GEEL": "GEE", "GCFC": "GCS", "GWS": "GWS", "HAW": "HAW",
           "MELB": "MEL", "NMFC": "NM", "PORT": "PA", "RICH": "RIC", "STK": "STK",
           "SYD": "SYD", "WCE": "WCE", "WB": "WB"}


def _norm(name: str) -> str:
    import unicodedata
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]+", " ", name.lower()).strip()


def mint():
    r = requests.post(f"{API}/cfs/afl/WMCTok", headers={**H, "Content-Length": "0"}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


def build():
    token = mint()
    r = requests.get(f"{API}/statspro/playersStats/seasons/CD_S{YEAR}014",
                     headers={**H, "x-media-mis-token": token}, timeout=30)
    players = r.json().get("players", [])

    # career games from the ratings history (2015+), and debut year
    hist = json.loads(HIST.read_text(encoding="utf-8"))
    career_games = {}
    for arr in hist.get("by_season", {}).values():
        for p in arr:
            nm = _norm(p["name"])
            career_games[nm] = career_games.get(nm, 0) + (p.get("games") or 0)

    coleman, approaching = [], []
    for p in players:
        d, t = p["playerDetails"], p.get("totals", {})
        nm = _norm(f"{d['givenName']} {d['surname']}")
        club = CD_ABBR.get((p.get("team") or {}).get("teamAbbr"))
        goals = int(t.get("goals") or 0)
        gp = int(p.get("gamesPlayed") or 0)
        if goals:
            coleman.append({"name": f"{d['givenName']} {d['surname']}", "club": club,
                            "goals": goals, "games": gp,
                            "per_game": round(goals / gp, 1) if gp else 0})
        debut = int(d.get("debutYear") or 0)
        cg = round(career_games.get(nm, 0))
        if debut >= 2015 and cg > 0:      # 2015+ debut -> our sum is the true total
            nxt = next((s for s in STEPS if s > cg), None)
            if nxt and (nxt - cg) <= NEAR:
                approaching.append({"name": f"{d['givenName']} {d['surname']}", "club": club,
                                    "games": cg, "milestone": nxt, "away": nxt - cg})

    coleman.sort(key=lambda x: (-x["goals"], -x["per_game"]))
    for i, x in enumerate(coleman):
        x["rank"] = i + 1
    approaching.sort(key=lambda x: (x["away"], -x["milestone"]))

    payload = {
        "year": YEAR,
        "attribution": "Season goals from AFL/Champion Data; career games summed from the ratings history (2015+), so games milestones are limited to players who debuted 2015 or later.",
        "coleman": coleman[:25],
        "approaching": approaching,
    }
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT}: {len(coleman)} goalkickers, {len(approaching)} approaching a games milestone")
    print("Coleman top 3:", [(c["name"], c["goals"]) for c in coleman[:3]])
    print("nearest milestones:", [(a["name"], f"{a['away']} from {a['milestone']}") for a in approaching[:4]])


if __name__ == "__main__":
    build()
