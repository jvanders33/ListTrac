"""Model scorecard — how well do ListTrac's models predict the real world?

Hawthorn's own player-valuation deck made the point that a ranking system is
only as good as its error against a ground truth: they scored each system by
mean error versus Best & Fairest, and found the Champion Data Player Rating the
best predictor. This does the same, publicly, for ListTrac.

The ground truth is the Brownlow Medal count (from AFL Tables) — the umpires'
season-long verdict on the best players, published after count night. For each
completed season we score four systems on how well they predict that vote order:

  * AFL Player Rating (season total)
  * AFL Player Rating per game (our quality measure)
  * AFL Fantasy (season average)
  * ListTrac's own Brownlow predictor (the per-match 3-2-1 model)

Metrics, over players with enough games: Spearman rank correlation with the vote
tally, and top-10 / top-25 hit rate (how many of the real top pollers the system
also ranks in its top). Averaged across seasons and reported per season, so the
numbers are honest and reproducible. No fabrication — real votes, real ratings.

    python scraper/scorecard.py     # -> data/scorecard.json
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "scorecard.json"
HIST = ROOT / "data" / "ratings_history.json"

API = "https://api.afl.com.au"
H = {"User-Agent": "Mozilla/5.0 ListTrac (github.com/jvanders33/ListTrac)",
     "Origin": "https://www.afl.com.au", "Referer": "https://www.afl.com.au/"}
AFLT = {"User-Agent": "ListTrac (github.com/jvanders33/ListTrac)"}

SEASONS = [2023, 2024, 2025]      # completed seasons with a counted Brownlow
MIN_GAMES = 8
MID = {"MIDFIELDER", "MIDFIELDER_FORWARD"}


def _norm(name: str) -> str:
    import unicodedata
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]+", " ", name.lower()).strip()


# ---- ground truth: Brownlow votes -----------------------------------------
def brownlow_votes(year: int) -> dict[str, int]:
    url = f"https://afltables.com/afl/brownlow/brownlow{year}.html"
    r = requests.get(url, headers=AFLT, timeout=25)
    r.raise_for_status()
    time.sleep(1)
    soup = BeautifulSoup(r.text, "html.parser")
    out = {}
    for t in soup.find_all("table"):
        links = t.find_all("a", href=lambda h: h and "players/" in h)
        if len(links) < 50:
            continue
        for row in t.find_all("tr")[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 3:
                continue
            name = cells[0].get_text(strip=True)          # "Rowell, Matt"
            votes = cells[2].get_text(strip=True)         # total votes column
            if "," in name and votes.isdigit():
                ln, fn = [s.strip() for s in name.split(",", 1)]
                out[_norm(f"{fn} {ln}")] = int(votes)
        break
    return out


# ---- systems --------------------------------------------------------------
def season_ratings(year: int) -> dict[str, dict]:
    hist = json.loads(HIST.read_text(encoding="utf-8"))
    out = {}
    for r in hist["by_season"].get(str(year), []):
        g = r.get("games") or 0
        if g:
            out[_norm(r["name"])] = {"rating": r.get("rating") or 0, "games": g,
                                     "rating_pg": (r.get("rating") or 0) / g}
    return out


def mint():
    r = requests.post(f"{API}/cfs/afl/WMCTok", headers={**H, "Content-Length": "0"}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


def season_fantasy(year: int, token: str) -> dict[str, float]:
    r = requests.get(f"{API}/statspro/playersStats/seasons/CD_S{year}014",
                     headers={**H, "x-media-mis-token": token}, timeout=30)
    out = {}
    if r.status_code == 200:
        for p in r.json().get("players", []):
            d, t = p["playerDetails"], p.get("totals", {})
            af = t.get("dreamTeamPoints")
            if af is not None:
                out[_norm(f"{d['givenName']} {d['surname']}")] = af
    return out


def predictor_votes(year: int, token: str) -> dict[str, float]:
    """Run ListTrac's per-match 3-2-1 Brownlow model on the season's rounds."""
    def vscore(p):
        t = p.get("totals", {})
        mid = (p["playerDetails"].get("position") or "") in MID
        return ((t.get("ratingPoints") or 0) + 0.09 * (t.get("disposals") or 0)
                + 1.2 * (t.get("goals") or 0) + (4.0 if (p.get("result") or "").startswith("W") else 0)
                + (2.0 if mid else 0))
    tally, empty = {}, 0
    for n in range(0, 31):
        rid = f"CD_R{year}014{n:02d}"
        r = requests.get(f"{API}/statspro/playersStats/rounds/{rid}",
                         headers={**H, "x-media-mis-token": token}, timeout=25)
        pl = r.json().get("players", []) if r.status_code == 200 else []
        played = [p for p in pl if (p.get("gamesPlayed") or 0) >= 1]
        if not played:
            empty += 1
            if empty >= 4 and n > 5:
                break
            continue
        empty = 0
        matches = {}
        for p in played:
            ta = (p.get("team") or {}).get("teamAbbr")
            oa = (p.get("opponent") or {}).get("teamAbbr")
            if ta and oa:
                matches.setdefault(frozenset((ta, oa)), []).append(p)
        for m in matches.values():
            for votes, p in zip((3, 2, 1), sorted(m, key=vscore, reverse=True)[:3]):
                d = p["playerDetails"]
                nm = _norm(f"{d['givenName']} {d['surname']}")
                tally[nm] = tally.get(nm, 0) + votes
        time.sleep(0.3)
    return tally


# ---- scoring --------------------------------------------------------------
def _spearman(pairs):
    """pairs: list of (system_value, truth_value). Spearman rho."""
    n = len(pairs)
    if n < 3:
        return None

    def ranks(vals):
        order = sorted(range(n), key=lambda i: vals[i])
        rk = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                rk[order[k]] = avg
            i = j + 1
        return rk
    rx, ry = ranks([p[0] for p in pairs]), ranks([p[1] for p in pairs])
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = sum((rx[i] - mx) ** 2 for i in range(n)) ** 0.5
    dy = sum((ry[i] - my) ** 2 for i in range(n)) ** 0.5
    return round(num / (dx * dy), 3) if dx and dy else None


def score_system(sysval: dict, votes: dict, pool: set):
    pairs = [(sysval.get(nm, 0), votes.get(nm, 0)) for nm in pool]
    rho = _spearman(pairs)
    truth_top = [nm for nm, _ in sorted(votes.items(), key=lambda kv: -kv[1]) if nm in pool]
    sys_rank = sorted(pool, key=lambda nm: -sysval.get(nm, 0))
    hits = lambda k: len(set(truth_top[:k]) & set(sys_rank[:k]))
    return {"spearman": rho, "top10": hits(10), "top25": hits(25)}


SYSTEMS = ["rating", "rating_pg", "fantasy", "predictor"]
LABELS = {"rating": "AFL Player Rating", "rating_pg": "Rating per game",
          "fantasy": "AFL Fantasy", "predictor": "ListTrac Brownlow model"}


def build():
    token = mint()
    per_season = {}
    for year in SEASONS:
        votes = brownlow_votes(year)
        sr = season_ratings(year)
        fant = season_fantasy(year, token)
        pred = predictor_votes(year, token)
        pool = {nm for nm, v in sr.items() if v["games"] >= MIN_GAMES}
        sysvals = {
            "rating": {nm: sr[nm]["rating"] for nm in sr},
            "rating_pg": {nm: sr[nm]["rating_pg"] for nm in sr},
            "fantasy": fant, "predictor": pred,
        }
        per_season[year] = {"voters": len([v for v in votes.values() if v > 0]),
                            "pool": len(pool),
                            "winner": max(votes.items(), key=lambda kv: kv[1])[0] if votes else None,
                            "systems": {s: score_system(sysvals[s], votes, pool) for s in SYSTEMS}}
        print(f"  {year}: pool {len(pool)}, voters {per_season[year]['voters']}")
        for s in SYSTEMS:
            print(f"    {LABELS[s]:26} rho {per_season[year]['systems'][s]['spearman']} "
                  f"top10 {per_season[year]['systems'][s]['top10']}/10")

    # aggregate: mean of each metric across seasons
    agg = {}
    for s in SYSTEMS:
        rhos = [per_season[y]["systems"][s]["spearman"] for y in SEASONS if per_season[y]["systems"][s]["spearman"] is not None]
        t10 = [per_season[y]["systems"][s]["top10"] for y in SEASONS]
        t25 = [per_season[y]["systems"][s]["top25"] for y in SEASONS]
        agg[s] = {"label": LABELS[s],
                  "spearman": round(sum(rhos) / len(rhos), 3) if rhos else None,
                  "top10": round(sum(t10) / len(t10), 1), "top25": round(sum(t25) / len(t25), 1)}
    ranked = sorted(agg.values(), key=lambda a: -(a["spearman"] or 0))
    for i, a in enumerate(ranked):
        a["rank"] = i + 1
    return {"seasons": SEASONS, "min_games": MIN_GAMES,
            "ground_truth": "Brownlow Medal votes (AFL Tables)",
            "metric_note": "Spearman rank correlation with the Brownlow vote tally, plus top-10 / top-25 hit rate, over players with >= %d games, averaged across seasons." % MIN_GAMES,
            "attribution": "Ground truth: Brownlow Medal votes from AFL Tables. Systems scored: Champion Data AFL Player Rating, AFL Fantasy, and ListTrac's own Brownlow model. Method after Hawthorn's player-valuation work (mean error vs a ground truth).",
            "systems": agg, "ranked": ranked, "per_season": per_season}


def main():
    data = build()
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {OUT}")
    print("OVERALL (by rank correlation with the Brownlow):")
    for a in data["ranked"]:
        print(f"  {a['rank']}. {a['label']:26} rho {a['spearman']} · top10 {a['top10']}/10 · top25 {a['top25']}/25")


if __name__ == "__main__":
    main()
