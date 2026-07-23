"""Vs-opponent splits — how a player performs against each club.

Cricinfo has player-vs-opposition splits; AFL sites don't. The cracked
round-level endpoint carries each game's opponent, so aggregating a few seasons
of game lines gives a real "who do they feast on, who keeps them quiet" table.

    GET https://api.afl.com.au/statspro/playersStats/rounds/{roundId}
    roundId = CD_R{year}014{NN}

For every player we roll up games by opponent across a multi-season window
(disposals, AF points, rating points, goals, and games met), plus an overall
line so the page can flag over- and under-performance. Venue/home-away isn't in
this feed, so that split waits on a fixture source. Champion Data / AFL only,
no fabrication.

    python scraper/splits.py     # -> data/splits_2026.json
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
OUT = Path(__file__).resolve().parent.parent / "data" / "splits_2026.json"

SEASONS = [2022, 2023, 2024, 2025, 2026]   # window for the splits
MIN_GAMES_VS = 2                            # opponents met fewer times are dropped

# Champion Data team abbreviation -> our club abbreviation
CD_ABBR = {
    "ADEL": "ADE", "BL": "BRI", "CARL": "CAR", "COLL": "COL", "ESS": "ESS",
    "FRE": "FRE", "GEEL": "GEE", "GCFC": "GCS", "GCS": "GCS", "GWS": "GWS",
    "HAW": "HAW", "MELB": "MEL", "NMFC": "NM", "PORT": "PA", "RICH": "RIC",
    "STK": "STK", "SYD": "SYD", "WCE": "WCE", "WB": "WB",
}


def _norm(name: str) -> str:
    import unicodedata
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]+", " ", name.lower()).strip()


def mint():
    r = requests.post(f"{API}/cfs/afl/WMCTok", headers={**H, "Content-Length": "0"}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


def fetch_round(year: int, n: int, token: str):
    rid = f"CD_R{year}014{n:02d}"
    r = requests.get(f"{API}/statspro/playersStats/rounds/{rid}",
                     headers={**H, "x-media-mis-token": token}, timeout=25)
    return r.json().get("players", []) if r.status_code == 200 else []


def build():
    token = mint()
    # accumulator: name -> {"name", opp_abbr -> [ (disp, af, rating, goals) ]}
    games: dict[str, dict] = {}
    seasons_seen = set()
    for year in SEASONS:
        empty_streak = 0
        for n in range(0, 31):
            players = fetch_round(year, n, token)
            played = [p for p in players if (p.get("gamesPlayed") or 0) >= 1]
            if not played:
                empty_streak += 1
                if empty_streak >= 4 and n > 5:   # past the end of the season
                    break
                continue
            empty_streak = 0
            seasons_seen.add(year)
            for p in played:
                d, t = p["playerDetails"], p.get("totals", {})
                opp = (p.get("opponent") or {}).get("teamAbbr")
                opp = CD_ABBR.get(opp, opp)
                if not opp:
                    continue
                nm = _norm(f"{d['givenName']} {d['surname']}")
                rec = games.setdefault(nm, {"name": f"{d['givenName']} {d['surname']}", "opp": {}})
                rec["opp"].setdefault(opp, []).append((
                    int(t.get("disposals") or 0),
                    int(t.get("dreamTeamPoints") or 0) or None,
                    round(t["ratingPoints"], 1) if t.get("ratingPoints") is not None else None,
                    int(t.get("goals") or 0),
                ))
            time.sleep(0.3)
        print(f"  {year}: done ({len([1 for s in seasons_seen if s == year])})")

    def agg(lines):
        n = len(lines)
        def m(i):
            v = [x[i] for x in lines if x[i] is not None]
            return round(sum(v) / len(v), 1) if v else None
        return {"games": n, "disp": m(0), "af": m(1), "rating": m(2), "goals": m(3)}

    out = {}
    for nm, rec in games.items():
        all_lines = [ln for lines in rec["opp"].values() for ln in lines]
        vs = {opp: agg(lines) for opp, lines in rec["opp"].items()
              if len(lines) >= MIN_GAMES_VS}
        if not vs:
            continue
        out[nm] = {"name": rec["name"], "overall": agg(all_lines), "vs": vs}
    return {"seasons": sorted(seasons_seen), "min_games_vs": MIN_GAMES_VS,
            "attribution": "Vs-opponent splits from AFL/Champion Data round-level data.",
            "count": len(out), "players": out}


def main():
    data = build()
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote splits for {len(data['players'])} players -> {OUT} (seasons {data['seasons']})")
    for nm in ("marcus bontempelli", "nick daicos", "jeremy cameron"):
        p = data["players"].get(nm)
        if p:
            best = max(p["vs"].items(), key=lambda kv: kv[1]["disp"] or 0)
            print(f"  {p['name']}: overall {p['overall']['disp']} disp · best vs {best[0]} "
                  f"({best[1]['disp']} over {best[1]['games']})")


if __name__ == "__main__":
    main()
