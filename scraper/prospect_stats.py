"""
Prospect playing history — full cross-competition stats from Rookie Me Central.

RMC runs on WordPress + SportsPress Pro, which exposes a REST API. Each player's
object carries a `statistics` block keyed by league then season, with the team
and a full stat line (disposals, goals, marks, tackles, clearances, inside-50s
...). Because RMC has already aggregated SANFL, WAFL, the Coates Talent League,
the national championships and more into one profile, a single search per
prospect returns their entire junior playing history.

    python scraper/prospect_stats.py           # all prospect classes -> data/prospect_stats.json
    python scraper/prospect_stats.py 2027 2028 # just those classes

Run weekly after matches — the numbers update as the season is played.
"""
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://central.rookieme.com/afl/wp-json/sportspress/v2"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ListTrac (github.com/jvanders33/ListTrac)"}
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_PATH = DATA_DIR / "prospect_stats.json"

# SportsPress league id -> display name (from /leagues). Order = display priority.
LEAGUES = {
    "12155": "AFL", "2963": "NEAFL", "7354": "VFL",
    "2970": "SANFL League", "2971": "SANFL Reserves", "2972": "SANFL U18",
    "2967": "WAFL League", "2968": "WAFL Reserves", "2969": "WAFL Colts",
    "19": "Coates Talent League", "2027": "U18 Championships",
    "20800": "U16 Championships", "23": "U16 Championships", "1982": "Academy",
}
# the stat columns worth surfacing, in order
STAT_KEYS = [("gamesplayed", "GM"), ("disposals", "D"), ("kicks", "K"), ("handballs", "HB"),
             ("marks", "M"), ("tackles", "T"), ("clr", "CLR"), ("i", "I50"),
             ("cp", "CP"), ("hitouts", "HO"), ("goals", "G")]


def _norm(name: str) -> str:
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]+", " ", name.lower()).strip()


def _get(path: str):
    req = urllib.request.Request(BASE + path, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_player_history(name: str) -> dict | None:
    """Search RMC for a prospect and return their cross-competition history,
    or None if not found. Matches on the full normalized name."""
    q = urllib.parse.quote(name.split()[-1])  # search by surname, then match full
    try:
        results = _get(f"/players?search={q}&per_page=10")
    except Exception:
        return None
    time.sleep(0.5)  # politeness delay

    target = _norm(name)
    match = next((p for p in results if _norm(p.get("title", {}).get("rendered", "")) == target), None)
    if match is None:
        return None

    history = []
    for league_id, seasons in (match.get("statistics") or {}).items():
        if not isinstance(seasons, dict):
            continue
        for season_id, vals in seasons.items():
            if not isinstance(vals, dict) or not str(vals.get("name", "")).isdigit():
                continue  # skip the "Total"/header rows
            games = int(vals.get("gamesplayed") or 0)
            if games <= 0:
                continue
            team = re.sub(r"<[^>]+>", "", vals.get("team", "") or "").strip()
            row = {"league": LEAGUES.get(league_id, f"League {league_id}"),
                   "league_id": league_id, "season": vals["name"], "team": team}
            for key, _ in STAT_KEYS:
                v = vals.get(key)
                row[key] = int(v) if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()) else None
            # per-game averages for the headline stats
            row["avg_disposals"] = round(row["disposals"] / games, 1) if row.get("disposals") else None
            row["avg_goals"] = round(row["goals"] / games, 1) if row.get("goals") else None
            history.append(row)

    history.sort(key=lambda r: (r["season"], r["league_id"]), reverse=True)
    return {"rmc_id": match["id"], "history": history} if history else {"rmc_id": match["id"], "history": []}


def prospect_names(years: list[int]) -> list[str]:
    names = []
    for year in years:
        path = DATA_DIR / ("prospects_2026.json" if year == 2026 else f"prospects_{year}.json")
        if path.exists():
            names += [p["name"] for p in json.loads(path.read_text(encoding="utf-8")).get("prospects", [])]
    return names


def main(years: list[int]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    names = prospect_names(years)
    print(f"Fetching playing history for {len(names)} prospects across {years}...")
    out = {}
    found = 0
    for i, name in enumerate(names, 1):
        rec = fetch_player_history(name)
        if rec and rec["history"]:
            out[name] = rec
            found += 1
        if i % 25 == 0:
            print(f"  {i}/{len(names)} ({found} with history)")

    payload = {
        "source": "Rookie Me Central (SportsPress)",
        "source_url": "https://central.rookieme.com/afl/",
        "leagues": list(dict.fromkeys(LEAGUES.values())),
        "players": out,
    }
    # merge with any existing file so a partial run doesn't drop other classes
    if OUT_PATH.exists():
        prev = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        merged = {**prev.get("players", {}), **out}
        payload["players"] = merged
    OUT_PATH.write_text(json.dumps(payload, indent=1), encoding="utf-8", newline="\n")
    print(f"wrote {OUT_PATH.name}: {found}/{len(names)} prospects with playing history")


if __name__ == "__main__":
    years = [int(a) for a in sys.argv[1:]] or [2026, 2027, 2028]
    main(years)
