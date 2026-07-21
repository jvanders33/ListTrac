"""
Official AFL Player Ratings (Champion Data) scraper.

The AFL's stats site loads player ratings from api.afl.com.au's statspro feed,
gated by a short-lived MIS token that any client can mint from the public
WMCTok endpoint (same call the site's own JavaScript makes on load). Each
player record carries `totals.ratingPoints` — the Champion Data AFL Player
Rating — and `totals.ranking`, their official season rank.

This is Champion Data / AFL data: ListTrac surfaces the rating as a fact with
clear attribution and a link back, never as its own metric. Seasons are
addressed as CD_S{year}014 and history reaches back well over a decade.

    python scraper/afl_ratings.py           # current season -> data/ratings_2026.json
"""
import json
import time
from pathlib import Path

import requests

API = "https://api.afl.com.au"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ListTrac (github.com/jvanders33/ListTrac)",
    "Origin": "https://www.afl.com.au",
    "Referer": "https://www.afl.com.au/",
}
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "ratings_2026.json"
ATTRIBUTION = "Official AFL Player Ratings, powered by Champion Data"
SOURCE_URL = "https://www.afl.com.au/stats/player-ratings"


def mint_token() -> str:
    resp = requests.post(f"{API}/cfs/afl/WMCTok", headers={**HEADERS, "Content-Length": "0"}, timeout=15)
    resp.raise_for_status()
    return resp.json()["token"]


def fetch_season_ratings(year: int, token: str | None = None) -> list[dict]:
    """Every rated player for a season, ranked. Returns
    [{rank, rating, name, first_name, last_name, team, games, draft_year,
      draft_position}]."""
    token = token or mint_token()
    resp = requests.get(
        f"{API}/statspro/playersStats/seasons/CD_S{year}014",
        headers={**HEADERS, "x-media-mis-token": token}, timeout=20)
    resp.raise_for_status()
    time.sleep(1)  # politeness delay

    out = []
    for pl in resp.json()["players"]:
        d, t = pl["playerDetails"], pl["totals"]
        if t.get("ratingPoints") is None:
            continue
        out.append({
            "rank": int(t["ranking"]) if t.get("ranking") else None,
            "rating": round(t["ratingPoints"], 1),
            "first_name": d["givenName"], "last_name": d["surname"],
            "name": f"{d['givenName']} {d['surname']}",
            "team": pl["team"]["teamAbbr"], "team_name": pl["team"]["teamName"],
            "games": pl.get("gamesPlayed"),
            "draft_year": d.get("draftYear"), "draft_position": d.get("draftPosition"),
        })
    out.sort(key=lambda x: x["rating"], reverse=True)
    return out


if __name__ == "__main__":
    token = mint_token()
    ratings = fetch_season_ratings(2026, token)
    payload = {
        "year": 2026, "attribution": ATTRIBUTION, "source_url": SOURCE_URL,
        "count": len(ratings), "ratings": ratings,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=1), encoding="utf-8", newline="\n")
    print(f"wrote {OUT_PATH.name}: {len(ratings)} rated players")
    for r in ratings[:5]:
        print(f"  {r['rank']:>3}  {r['name']:<22} {r['team']}  {r['rating']}")
