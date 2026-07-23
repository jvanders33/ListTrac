"""Brownlow Medal predictor — a running 3-2-1 projection, the AFL's MVP ladder.

The Brownlow is umpire-voted 3-2-1 in every home-and-away match, so a predictor
has to work match by match: score every player in a game, award a predicted
3, 2 and 1, and accumulate across the season. This pulls each round's player
lines from the cracked round-level endpoint, groups them into matches, and runs
that model.

The vote score leans on Champion Data's per-game rating (the best single public
predictor of umpire votes) and layers on the umpire biases the count is famous
for: a premium on goals, and a premium on winning (historically roughly two in
three votes go to players from the winning side), plus a small midfield lean.
It's a model, clearly labelled — not a leak of real votes, which stay secret
until count night. Champion Data / AFL only.

    python scraper/brownlow.py     # -> data/brownlow_2026.json
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
OUT = Path(__file__).resolve().parent.parent / "data" / "brownlow_2026.json"
YEAR = 2026
SEASON_GAMES = 22          # H&A games a fit player gets, for the projection

CD_ABBR = {
    "ADEL": "ADE", "BL": "BRI", "CARL": "CAR", "COLL": "COL", "ESS": "ESS",
    "FRE": "FRE", "GEEL": "GEE", "GCFC": "GCS", "GCS": "GCS", "GWS": "GWS",
    "HAW": "HAW", "MELB": "MEL", "NMFC": "NM", "PORT": "PA", "RICH": "RIC",
    "STK": "STK", "SYD": "SYD", "WCE": "WCE", "WB": "WB",
}
MID = {"MIDFIELDER", "MIDFIELDER_FORWARD"}


def _norm(name: str) -> str:
    import unicodedata
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]+", " ", name.lower()).strip()


def mint():
    r = requests.post(f"{API}/cfs/afl/WMCTok", headers={**H, "Content-Length": "0"}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


def fetch_round(n: int, token: str):
    rid = f"CD_R{YEAR}014{n:02d}"
    r = requests.get(f"{API}/statspro/playersStats/rounds/{rid}",
                     headers={**H, "x-media-mis-token": token}, timeout=25)
    return r.json().get("players", []) if r.status_code == 200 else []


def vote_score(p) -> float:
    t = p.get("totals", {})
    rating = t.get("ratingPoints") or 0.0
    goals = t.get("goals") or 0
    disp = t.get("disposals") or 0
    win = (p.get("result") or "").startswith("W")
    mid = (p["playerDetails"].get("position") or "") in MID
    # Rating is the backbone. A disposal term + a midfield lean reflect the count's
    # heavy bias to ball-winning midfielders; goals help but don't dominate; and
    # winning matters a lot (~2 in 3 votes go to the winning side).
    return (rating
            + 0.09 * disp
            + 1.2 * goals
            + (4.0 if win else 0.0)
            + (3.0 if mid else 0.0))


def build():
    token = mint()
    players: dict[str, dict] = {}
    rounds_done = []
    empty = 0
    for n in range(0, 31):
        pl = fetch_round(n, token)
        played = [p for p in pl if (p.get("gamesPlayed") or 0) >= 1]
        if not played:
            empty += 1
            if empty >= 4 and n > 5:
                break
            continue
        empty = 0
        rounds_done.append(n)
        # group into matches by the unordered {team, opponent} pair
        matches: dict[frozenset, list] = {}
        for p in played:
            ta = (p.get("team") or {}).get("teamAbbr")
            oa = (p.get("opponent") or {}).get("teamAbbr")
            if not ta or not oa:
                continue
            matches.setdefault(frozenset((ta, oa)), []).append(p)
        # award predicted 3-2-1 within each match
        for match in matches.values():
            ranked = sorted(match, key=vote_score, reverse=True)
            for votes, p in zip((3, 2, 1), ranked[:3]):
                d = p["playerDetails"]
                nm = _norm(f"{d['givenName']} {d['surname']}")
                rec = players.setdefault(nm, {
                    "name": f"{d['givenName']} {d['surname']}",
                    "club": CD_ABBR.get((p.get("team") or {}).get("teamAbbr"), None),
                    "votes": 0, "polls": 0, "threes": 0, "by_round": {}})
                rec["votes"] += votes
                rec["polls"] += 1
                rec["threes"] += 1 if votes == 3 else 0
                rec["by_round"][str(n)] = votes
        # keep each player's games-played tally for the projection
        for p in played:
            d = p["playerDetails"]
            nm = _norm(f"{d['givenName']} {d['surname']}")
            gp = players.get(nm)
            if gp is not None:
                gp["games"] = gp.get("games", 0) + 1
        time.sleep(0.35)

    board = [r for r in players.values() if r["votes"] > 0]
    for r in board:
        g = max(r.get("games", 0), r["polls"])
        r["projected"] = round(r["votes"] / g * SEASON_GAMES) if g else r["votes"]
    board.sort(key=lambda r: (-r["votes"], -r["threes"], r["name"]))
    for i, r in enumerate(board):
        r["rank"] = i + 1
    return {"year": YEAR, "rounds": rounds_done, "season_games": SEASON_GAMES,
            "attribution": "ListTrac's Brownlow Medal projection — a per-match 3-2-1 model built on Champion Data ratings with goal and winning-team weightings. A prediction, not the actual (secret) umpire votes.",
            "count": len(board), "players": board}


def main():
    data = build()
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote Brownlow projection -> {OUT} (rounds {data['rounds'][0]}-{data['rounds'][-1]})")
    print("predicted leaderboard (top 12):")
    for r in data["players"][:12]:
        print(f"  {r['rank']:2}. {r['name']:24} {r['club'] or '':4} {r['votes']:3} votes "
              f"({r['threes']} bogs, polled {r['polls']}x) · proj {r['projected']}")


if __name__ == "__main__":
    main()
