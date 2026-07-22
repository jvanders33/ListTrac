"""Recent form — per-round player lines from the AFL (Champion Data).

The season feed gives averages; this cracks the round-level endpoint

    GET https://api.afl.com.au/statspro/playersStats/rounds/{roundId}

(roundId = CD_R{year}014{NN}) for each player's game-by-game output, so a
player page can show a last-few-games form line and a hot/cold read against
their season. Same WMCTok token as the ratings scraper.

    python scraper/form.py     # -> data/form_2026.json (last ~8 rounds)
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
OUT = Path(__file__).resolve().parent.parent / "data" / "form_2026.json"
YEAR = 2026
WINDOW = 8   # most recent rounds to keep


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
    if r.status_code != 200:
        return []
    return r.json().get("players", [])


def build():
    token = mint()
    rounds = []            # (round_number, players) newest-first, played only
    for n in range(30, -1, -1):   # walk back from a high round number
        players = fetch_round(n, token)
        played = [p for p in players if (p.get("gamesPlayed") or 0) >= 1]
        if played:
            rounds.append((n, played))
            time.sleep(0.4)
        if len(rounds) >= WINDOW:
            break
    rounds.reverse()       # oldest-first
    print(f"rounds with data: {[n for n, _ in rounds]}")

    by_player: dict[str, dict] = {}
    for n, players in rounds:
        for p in players:
            d, t = p["playerDetails"], p.get("totals", {})
            nm = _norm(f"{d['givenName']} {d['surname']}")
            rec = by_player.setdefault(nm, {"name": f"{d['givenName']} {d['surname']}", "games": []})
            rec["games"].append({
                "rnd": n, "opp": (p.get("opponent") or {}).get("teamAbbr"),
                "result": (p.get("result") or "")[:1].upper() or None,
                "disp": int(t.get("disposals") or 0),
                "af": int(t.get("dreamTeamPoints") or 0) or None,
                "rating": round(t["ratingPoints"], 1) if t.get("ratingPoints") is not None else None,
                "goals": int(t.get("goals") or 0),
            })

    def avg(games, key):
        vals = [g[key] for g in games if g.get(key) is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    out = {}
    for nm, rec in by_player.items():
        g = sorted(rec["games"], key=lambda x: x["rnd"])
        last5 = g[-5:]
        out[nm] = {
            "name": rec["name"], "games": g,
            "l5_disp": avg(last5, "disp"), "l5_af": avg(last5, "af"), "l5_rating": avg(last5, "rating"),
            "l5_goals": avg(last5, "goals"), "played": len(g),
        }
    return {"year": YEAR, "rounds": [n for n, _ in rounds],
            "attribution": "Round-by-round from AFL/Champion Data.", "players": out}


def main():
    data = build()
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote form for {len(data['players'])} players -> {OUT}")
    for nm in ("marcus bontempelli", "nick daicos"):
        p = data["players"].get(nm)
        if p:
            print(f"  {p['name']}: last5 {p['l5_disp']} disp, {p['l5_af']} AF · "
                  + " ".join(str(g["disp"]) for g in p["games"]))


if __name__ == "__main__":
    main()
