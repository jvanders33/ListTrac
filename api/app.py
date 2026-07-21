"""
ListTrac read API — FastAPI over data/listtrac.db.

    uvicorn api.app:app --reload        (from repo root; build the DB first
                                         with python data/load.py)

Read-only by design: the DB is rebuilt by the loader, and trade-period manual
entry will get its own admin tool. No dollar figures anywhere — contract
status only, per project scope.
"""
import re
import sqlite3
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "listtrac.db"
# NOTE: must not be named "public" — Vercel special-cases that folder as
# static assets and strips it from Python function bundles
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="ListTrac API", version="0.1.0",
              description="AFL player movement, lists, contract status, and draft history. No salary data.")


def db() -> sqlite3.Connection:
    # mode=ro: the DB is a committed snapshot and serverless filesystems are
    # read-only anyway — never open it writable
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def rows(query: str, params: tuple = ()) -> list[dict]:
    with db() as conn:
        return [dict(r) for r in conn.execute(query, params)]


PLAYER_COLS = """p.id, p.first_name, p.last_name, p.dob, p.height_cm, p.jumper_number,
                 p.status player_status, c.name club, c.abbreviation club_abbrev,
                 c.primary_color club_primary, c.secondary_color club_secondary"""


@app.get("/clubs")
def clubs():
    return rows("""SELECT c.id, c.name, c.abbreviation, c.primary_color, c.secondary_color,
                          COUNT(p.id) listed_players
                   FROM club c LEFT JOIN player p
                        ON p.current_club_id = c.id AND p.status = 'listed'
                   GROUP BY c.id ORDER BY c.name""")


@app.get("/clubs/{abbrev}/list")
def club_list(abbrev: str):
    result = rows(f"""SELECT {PLAYER_COLS}, cs.status contract_status, cs.contracted_through_year,
                             dp.year draft_year, dp.draft_type, dp.pick_number
                      FROM player p
                      JOIN club c ON c.id = p.current_club_id
                      LEFT JOIN contract_status cs ON cs.player_id = p.id AND cs.is_current = 1
                      LEFT JOIN draft_pick dp ON dp.id = p.draft_pick_id
                      WHERE c.abbreviation = ? COLLATE NOCASE
                      ORDER BY p.jumper_number""", (abbrev,))
    if not result:
        raise HTTPException(404, f"no listed players for club '{abbrev}'")
    return result


@app.get("/players")
def search_players(q: str):
    like = f"%{q}%"
    return rows(f"""SELECT {PLAYER_COLS}
                    FROM player p LEFT JOIN club c ON c.id = p.current_club_id
                    WHERE p.first_name || ' ' || p.last_name LIKE ? COLLATE NOCASE
                    ORDER BY p.last_name LIMIT 25""", (like,))


@app.get("/players/{player_id}")
def player(player_id: int):
    found = rows(f"""SELECT {PLAYER_COLS}, p.draftguru_id
                     FROM player p LEFT JOIN club c ON c.id = p.current_club_id
                     WHERE p.id = ?""", (player_id,))
    if not found:
        raise HTTPException(404, "player not found")
    profile = found[0]

    profile["contract_status"] = rows(
        """SELECT cs.status, cs.contracted_through_year, c.name club,
                  cs.source_note, cs.source_url, cs.last_confirmed_date, cs.is_current
           FROM contract_status cs JOIN club c ON c.id = cs.club_id
           WHERE cs.player_id = ? ORDER BY cs.is_current DESC""", (player_id,))
    profile["transactions"] = rows(
        """SELECT pt.type, cf.name from_club, ct.name to_club, pt.date,
                  pt.trade_period_year, pt.notes, pt.source_url
           FROM player_transaction pt
           LEFT JOIN club cf ON cf.id = pt.from_club_id
           LEFT JOIN club ct ON ct.id = pt.to_club_id
           WHERE pt.player_id = ? ORDER BY pt.date""", (player_id,))
    profile["drafted"] = next(iter(rows(
        """SELECT dp.year, dp.draft_type, dp.pick_number, c.name club
           FROM draft_pick dp JOIN club c ON c.id = dp.original_club_id
           WHERE dp.player_selected_id = ?""", (player_id,))), None)
    rating = _ratings_by_name().get(_norm(f"{profile['first_name']} {profile['last_name']}"))
    profile["rating"] = {"rank": rating["rank"], "rating": rating["rating"]} if rating else None
    return profile


@app.get("/drafts/{year}")
def draft(year: int, draft_type: str = "national"):
    result = rows("""SELECT dp.pick_number, dp.draft_type, dp.status,
                            c.name club, co.name original_club,
                            p.id player_id, p.first_name, p.last_name
                     FROM draft_pick dp
                     JOIN club c ON c.id = dp.current_owner_club_id
                     JOIN club co ON co.id = dp.original_club_id
                     LEFT JOIN player p ON p.id = dp.player_selected_id
                     WHERE dp.year = ? AND dp.draft_type = ?
                     ORDER BY dp.pick_number""", (year, draft_type))
    if not result:
        raise HTTPException(404, f"no {draft_type} draft data for {year}")

    # attach the trade chain to picks that arrived via trade
    chains: dict[int, list[str]] = {}
    for h in rows("""SELECT dp.pick_number, cf.abbreviation f, ct.abbreviation t
                     FROM draft_pick_trade_history h
                     JOIN draft_pick dp ON dp.id = h.draft_pick_id
                     JOIN club cf ON cf.id = h.from_club_id
                     JOIN club ct ON ct.id = h.to_club_id
                     WHERE dp.year = ? AND dp.draft_type = ? ORDER BY h.id""", (year, draft_type)):
        chains.setdefault(h["pick_number"], []).append(f"{h['f']} → {h['t']}")
    for r in result:
        r["trade_detail"] = "; ".join(chains.get(r["pick_number"], [])) or None
    return result


@app.get("/trades/{year}")
def trades(year: int):
    player_moves = rows(
        """SELECT pt.player_id, p.first_name, p.last_name, cf.name from_club,
                  ct.name to_club, pt.notes, pt.source_url
           FROM player_transaction pt
           JOIN player p ON p.id = pt.player_id
           LEFT JOIN club cf ON cf.id = pt.from_club_id
           LEFT JOIN club ct ON ct.id = pt.to_club_id
           WHERE pt.type = 'trade' AND pt.trade_period_year = ?""", (year,))
    pick_moves = rows(
        """SELECT h.description, cf.name from_club, ct.name to_club,
                  dp.pick_number resolved_pick, dp.year draft_year
           FROM draft_pick_trade_history h
           JOIN club cf ON cf.id = h.from_club_id
           JOIN club ct ON ct.id = h.to_club_id
           LEFT JOIN draft_pick dp ON dp.id = h.draft_pick_id
           WHERE h.date LIKE ?""", (f"{year}-%",))
    if not player_moves and not pick_moves:
        raise HTTPException(404, f"no trade data for {year}")
    return {"year": year, "players": player_moves, "picks": pick_moves}


# --- aggregation endpoints for the landing page ---------------------------

_cache: dict[str, tuple[float, object]] = {}


def cached(key: str, ttl: int, build):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    value = build()
    _cache[key] = (time.time(), value)
    return value


NEWS_FEED = ("https://news.google.com/rss/search"
             "?q=AFL%20(trade%20OR%20contract%20OR%20%22free%20agency%22%20OR%20draft)"
             "&hl=en-AU&gl=AU&ceid=AU:en")


@app.get("/api/news")
def news():
    """Movement news aggregated from Google News RSS. Headline + source +
    link out only — paywalled outlets get linked like everyone else, never
    reproduced. Cached 15 minutes per serverless instance."""
    def build():
        try:
            resp = requests.get(NEWS_FEED, headers={"User-Agent": "ListTrac (github.com/jvanders33/ListTrac)"},
                                timeout=10)
            resp.raise_for_status()
            items = []
            for it in ET.fromstring(resp.content).findall(".//item")[:40]:
                title = it.findtext("title") or ""
                source = it.find("source")
                source_name = source.text if source is not None else ""
                # Google News suffixes titles with " - Source" — strip the echo
                title = re.sub(r"\s+-\s+" + re.escape(source_name) + r"\s*$", "", title) if source_name else title
                published = None
                if it.findtext("pubDate"):
                    try:
                        published = parsedate_to_datetime(it.findtext("pubDate")).isoformat()
                    except ValueError:
                        pass
                items.append({"title": title, "source": source_name,
                              "url": it.findtext("link") or "", "published": published})
            items.sort(key=lambda x: x["published"] or "", reverse=True)
            return items[:20]
        except requests.RequestException:
            return []  # feed down -> landing page degrades gracefully
    return cached("news", 900, build)


SQUIGGLE = "https://api.squiggle.com.au/"
SQUIGGLE_ALIASES = {"Brisbane Lions": "Brisbane"}  # Squiggle name -> DB club name


@app.get("/api/draft-order")
def draft_order():
    """Projected 2026 national draft order, rounds 1-4: live Squiggle ladder
    reversed for slot order, then recorded 2026 pick trades (from Draftguru's
    2025 trade-period blocks + admin entries) applied to ownership. Traded
    slots carry a "via" marker. Still excluded: academy/father-son bid
    compensation and priority picks. Cached 1 hour."""
    def build():
        resp = requests.get(SQUIGGLE, params={"q": "standings", "year": 2026},
                            headers={"User-Agent": "ListTrac (github.com/jvanders33/ListTrac)"}, timeout=10)
        resp.raise_for_status()
        ladder = sorted(resp.json()["standings"], key=lambda t: t["rank"])
        with db() as conn:
            club_info = {r["name"]: dict(r) for r in conn.execute(
                "SELECT name, abbreviation, primary_color, secondary_color FROM club")}
            # "2026 R2 (St Kilda)" records: latest transfer of each natural slot wins
            ownership: dict[tuple[int, str], str] = {}
            for h in conn.execute(
                    """SELECT h.description, ct.abbreviation owner
                       FROM draft_pick_trade_history h JOIN club ct ON ct.id = h.to_club_id
                       WHERE h.description LIKE '2026 R%' ORDER BY h.id"""):
                m = re.match(r"2026 R(\d) \((.+)\)", h["description"])
                origin = club_info.get(m.group(2)) if m else None
                if origin:
                    ownership[(int(m.group(1)), origin["abbreviation"])] = h["owner"]

        abbrev_info = {v["abbreviation"]: v for v in club_info.values()}
        slot_order = [SQUIGGLE_ALIASES.get(t["name"], t["name"]) for t in reversed(ladder)]
        DVI_LOCAL = [3000, 2481, 2178, 1962, 1795, 1659, 1543, 1443, 1355, 1276, 1205, 1140,
                     1080, 1024, 973, 924, 879, 836, 796, 757, 721, 686, 653, 621, 590, 561,
                     533, 505, 479, 454, 429, 405, 382, 360, 338, 317, 297, 277, 257, 238,
                     220, 202, 184, 167, 150, 134, 118, 102, 86, 71, 57, 42, 28, 14]

        rounds, pick_no = [], 0
        for rnd in (1, 2, 3, 4):
            rp = []
            for i, slot_name in enumerate(slot_order):
                pick_no += 1
                origin = club_info.get(slot_name, {}).get("abbreviation")
                owner = ownership.get((rnd, origin), origin)
                oinfo = abbrev_info.get(owner, {})
                team = ladder[len(ladder) - 1 - i]
                rp.append({
                    "pick": pick_no, "round": rnd,
                    "club": oinfo.get("name", slot_name), "abbrev": owner,
                    "primary_color": oinfo.get("primary_color"),
                    "via": origin if owner != origin else None,
                    "ladder_rank": team["rank"], "wins": team["wins"],
                    "losses": team["losses"], "percentage": round(team["percentage"], 1),
                    "dvi": DVI_LOCAL[pick_no - 1] if pick_no <= len(DVI_LOCAL) else 0,
                })
            rounds.append({"round": rnd, "picks": rp})

        games_played = max(t["wins"] + t["losses"] + t.get("draws", 0) for t in ladder)
        return {"year": 2026, "as_of_round": games_played,
                "picks": rounds[0]["picks"], "rounds": rounds,
                "traded_slots": len(ownership), "source": "api.squiggle.com.au",
                "method": ("reverse ladder + recorded 2026 pick trades; "
                           "no academy/father-son bid compensation or priority picks")}
    try:
        return cached("draft_order", 3600, build)
    except requests.RequestException:
        raise HTTPException(503, "Squiggle ladder unavailable")


@app.get("/api/player-news")
def player_news(name: str):
    """Movement news for one player: Google News RSS scoped to their name +
    contract/trade context. Headline + source + link out only. 30-min cache
    per player name."""
    key = f"pnews:{name.lower().strip()}"
    def build():
        q = f'"{name}" AFL (contract OR trade OR "free agent" OR re-sign OR delist OR draft)'
        try:
            resp = requests.get(
                "https://news.google.com/rss/search",
                params={"q": q, "hl": "en-AU", "gl": "AU", "ceid": "AU:en"},
                headers={"User-Agent": "ListTrac (github.com/jvanders33/ListTrac)"}, timeout=10)
            resp.raise_for_status()
            items = []
            for it in ET.fromstring(resp.content).findall(".//item")[:10]:
                title = it.findtext("title") or ""
                source = it.find("source")
                source_name = source.text if source is not None else ""
                title = re.sub(r"\s+-\s+" + re.escape(source_name) + r"\s*$", "", title) if source_name else title
                published = None
                if it.findtext("pubDate"):
                    try:
                        published = parsedate_to_datetime(it.findtext("pubDate")).isoformat()
                    except ValueError:
                        pass
                items.append({"title": title, "source": source_name,
                              "url": it.findtext("link") or "", "published": published})
            return items
        except requests.RequestException:
            return []
    return cached(key, 1800, build)


@app.get("/api/trending")
def trending():
    """Players worth watching, from our own data signals — no traffic
    faked as popularity: the FA class, newest top picks, latest trades."""
    def build():
        out = []
        with db() as conn:
            for r in conn.execute(
                    """SELECT p.id, p.first_name, p.last_name, c.name club, c.abbreviation abbrev
                       FROM contract_status cs JOIN player p ON p.id = cs.player_id
                       JOIN club c ON c.id = cs.club_id
                       WHERE cs.is_current = 1 AND cs.status = 'restricted_fa' ORDER BY p.last_name"""):
                out.append({**dict(r), "reason": "Restricted free agent 2026", "kind": "rfa"})
            for r in conn.execute(
                    """SELECT p.id, p.first_name, p.last_name, c.name club, c.abbreviation abbrev,
                              dp.pick_number
                       FROM draft_pick dp JOIN player p ON p.id = dp.player_selected_id
                       JOIN club c ON c.id = dp.current_owner_club_id
                       WHERE dp.year = 2025 AND dp.draft_type = 'national' AND dp.pick_number <= 3
                       ORDER BY dp.pick_number"""):
                out.append({**{k: r[k] for k in ("id", "first_name", "last_name", "club", "abbrev")},
                            "reason": f"Pick {r['pick_number']}, 2025 national draft", "kind": "pick"})
            for r in conn.execute(
                    """SELECT p.id, p.first_name, p.last_name, c.name club, c.abbreviation abbrev
                       FROM player_transaction pt JOIN player p ON p.id = pt.player_id
                       JOIN club c ON c.id = pt.to_club_id
                       WHERE pt.type = 'trade' AND pt.trade_period_year = 2025
                         AND pt.from_club_id IS NOT NULL
                       ORDER BY pt.id LIMIT 3"""):
                out.append({**dict(r), "reason": f"Traded to {r['club']} in 2025", "kind": "trade"})
        return out
    return cached("trending", 3600, build)


ADMIN_JOURNAL = Path(__file__).resolve().parent.parent / "data" / "admin_entries.jsonl"


@app.get("/api/updates")
def updates():
    """First-party updates — the admin journal, newest first. These are moves
    ListTrac recorded directly (often ahead of the aggregated news cycle)."""
    import json
    if not ADMIN_JOURNAL.exists():
        return []
    out = []
    for line in ADMIN_JOURNAL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        p = e["payload"]
        verb = {"trade": "traded", "fa-sign": "signs as a free agent", "re-sign": "re-signs",
                "delist": "delisted", "pick-trade": "pick trade"}.get(e["action"], e["action"])
        out.append({
            "ts": e["ts"], "action": e["action"], "verb": verb,
            "player_name": p.get("player_name"), "player_club": p.get("player_club"),
            "to": p.get("to"), "through_year": p.get("through_year"),
            "notes": p.get("notes"), "source_url": p.get("source_url"),
        })
    return sorted(out, key=lambda x: x["ts"], reverse=True)[:10]


PROSPECTS_PATH = Path(__file__).resolve().parent.parent / "data" / "prospects_2026.json"
PICK_INTEL_PATH = Path(__file__).resolve().parent.parent / "data" / "pick_intel.json"
RATINGS_PATH = Path(__file__).resolve().parent.parent / "data" / "ratings_2026.json"


def _norm(name: str) -> str:
    import unicodedata
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]+", " ", name.lower()).strip()


def _ratings_by_name() -> dict:
    import json
    if not RATINGS_PATH.exists():
        return {}
    data = json.loads(RATINGS_PATH.read_text(encoding="utf-8"))
    return {_norm(r["name"]): r for r in data["ratings"]}


@app.get("/api/ratings")
def ratings(limit: int = 100, club: str | None = None):
    """Official AFL Player Ratings (Champion Data), ranked. Matched to
    ListTrac player pages by name so the table links through."""
    import json
    if not RATINGS_PATH.exists():
        raise HTTPException(404, "ratings not built yet")
    data = json.loads(RATINGS_PATH.read_text(encoding="utf-8"))
    with db() as conn:
        pid = {_norm(f"{r['first_name']} {r['last_name']}"): r["id"]
               for r in conn.execute("SELECT id, first_name, last_name FROM player")}
    rows = data["ratings"]
    if club:
        rows = [r for r in rows if r["team"].upper() == club.upper()]
    rows = [{**r, "player_id": pid.get(_norm(r["name"]))} for r in rows[:limit]]
    return {"year": data["year"], "attribution": data["attribution"],
            "source_url": data["source_url"], "count": len(data["ratings"]), "ratings": rows}


@app.get("/api/prospects")
def prospects():
    """2026 draft prospect pool: U18 championships squads (Rookie Me Central)
    merged with Reading the Play's Top 50. Regenerate: python scraper/u18_champs.py"""
    import json
    return json.loads(PROSPECTS_PATH.read_text(encoding="utf-8"))


@app.get("/api/pick-intel")
def pick_intel():
    """Historical outcome stats per pick number (1986-2020 cohort): DVI, avg
    games, AA%, premiership%, Rising Star%. Regenerate: python data/build_pick_intel.py"""
    import json
    if not PICK_INTEL_PATH.exists():
        raise HTTPException(404, "pick intel not built yet")
    return json.loads(PICK_INTEL_PATH.read_text(encoding="utf-8"))


@app.get("/api/debug")
def debug():
    """What actually made it into the serverless bundle (safe to expose: file names only)."""
    root = Path(__file__).resolve().parent.parent
    return {
        "root": str(root),
        "entries": sorted(p.name + ("/" if p.is_dir() else "") for p in root.iterdir()),
        "web_dir_exists": WEB_DIR.is_dir(),
        "db_exists": DB_PATH.exists(),
    }


@app.get("/api/summary")
def summary():
    with db() as conn:
        statuses = {r["status"]: r["n"] for r in conn.execute(
            "SELECT status, COUNT(*) n FROM contract_status WHERE is_current = 1 GROUP BY status")}
        counts = {t: conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
                  for t in ("player", "player_transaction", "draft_pick", "draft_pick_trade_history")}
        years = conn.execute("SELECT MIN(year) lo, MAX(year) hi FROM draft_pick").fetchone()
    return {"contract_statuses": statuses, "counts": counts,
            "draft_years": {"min": years["lo"], "max": years["hi"]}}


@app.get("/contract-status")
def contract_status(status: str | None = None, club: str | None = None):
    query = f"""SELECT {PLAYER_COLS}, cs.status contract_status,
                       cs.contracted_through_year, cs.source_url
                FROM contract_status cs
                JOIN player p ON p.id = cs.player_id
                JOIN club c ON c.id = cs.club_id
                WHERE cs.is_current = 1"""
    params: list = []
    if status:
        query += " AND cs.status = ?"
        params.append(status)
    if club:
        query += " AND c.abbreviation = ? COLLATE NOCASE"
        params.append(club)
    return rows(query + " ORDER BY c.name, p.last_name", tuple(params))


# static frontend — mounted last so API routes win. Guarded: if the directory
# is missing from a serverless bundle, degrade to API-only instead of crashing
# the whole function at import time (StaticFiles raises on a missing dir).
if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
