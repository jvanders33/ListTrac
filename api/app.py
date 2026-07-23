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
CURRENT_YEAR = 2026

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


CLUB_SOCIALS_PATH = Path(__file__).resolve().parent.parent / "data" / "club_socials.json"


@app.get("/api/club-socials")
def club_socials(abbrev: str):
    """Official social handles for a club, as ready-to-use profile URLs."""
    import json
    data = json.loads(CLUB_SOCIALS_PATH.read_text(encoding="utf-8")) if CLUB_SOCIALS_PATH.exists() else {}
    s = data.get(abbrev.upper())
    if not s:
        return {}
    return {
        "x": f"https://x.com/{s['x']}" if s.get("x") else None,
        "instagram": f"https://www.instagram.com/{s['instagram']}" if s.get("instagram") else None,
        "tiktok": f"https://www.tiktok.com/@{s['tiktok']}" if s.get("tiktok") else None,
        "website": s.get("website"),
    }


CLUB_INFO_PATH = Path(__file__).resolve().parent.parent / "data" / "club_info.json"
CLUB_HONOURS_PATH = Path(__file__).resolve().parent.parent / "data" / "club_honours.json"

# Our club abbreviation -> Champion Data ratings team code.
_RATINGS_TEAM = {
    "ADE": "ADEL", "BRI": "BL", "CAR": "CARL", "COL": "COLL", "ESS": "ESS",
    "FRE": "FRE", "GCS": "GCFC", "GEE": "GEEL", "GWS": "GWS", "HAW": "HAW",
    "MEL": "MELB", "NM": "NMFC", "PA": "PORT", "RIC": "RICH", "STK": "STK",
    "SYD": "SYD", "TAS": None, "WCE": "WCE", "WB": "WB",
}


@app.get("/api/club-info")
def club_info(abbrev: str):
    """Header facts for a club: static history (founded, premierships, honour
    rolls — from data/club_info.json) merged with live-derived data (the club's
    top-rated players this season, from our own Champion Data ratings)."""
    import json
    key = abbrev.upper()
    data = json.loads(CLUB_INFO_PATH.read_text(encoding="utf-8")) if CLUB_INFO_PATH.exists() else {}
    info = {k: v for k, v in (data.get(key) or {}).items() if not k.startswith("_")}

    # honour roll — premierships + major medals, sourced (data/club_honours.json)
    if CLUB_HONOURS_PATH.exists():
        h = json.loads(CLUB_HONOURS_PATH.read_text(encoding="utf-8"))
        club_h = (h.get("clubs") or {}).get(key)
        if club_h:
            info["premierships"] = club_h["flags"]
            info["premiership_years"] = club_h["premierships"]
            info["last_flag"] = club_h["premierships"][0] if club_h["premierships"] else None
            info["honours"] = club_h["awards"]
            info["honours_sources"] = h.get("sources")
            # Link medallists to a player page only when the name matches a
            # currently-listed player (the pages with live content); prefer the
            # same club so same-name coincidences don't cross-link. Retired
            # greats stay as plain text — we have no meaningful page for them.
            with db() as conn:
                listed: dict = {}
                for r in conn.execute(
                        """SELECT p.id, p.first_name, p.last_name, c.abbreviation ab
                           FROM player p LEFT JOIN club c ON c.id = p.current_club_id
                           WHERE p.status = 'listed'"""):
                    listed.setdefault(_norm(f"{r['first_name']} {r['last_name']}"), []).append((r["id"], r["ab"]))
            for winners in info["honours"].values():
                for w in winners:
                    cands = listed.get(_norm(w["p"]))
                    if not cands:
                        continue
                    if len(cands) == 1:
                        w["player_id"] = cands[0][0]
                    else:
                        same = [pid for pid, ab in cands if (ab or "").upper() == key]
                        if same:
                            w["player_id"] = same[0]

    # top-rated players currently on the list, matched to player pages
    top_rated = []
    team = _RATINGS_TEAM.get(key)
    if team and RATINGS_PATH.exists():
        with db() as conn:
            pid = {_norm(f"{r['first_name']} {r['last_name']}"): r["id"]
                   for r in conn.execute("SELECT id, first_name, last_name FROM player")}
        ratings = json.loads(RATINGS_PATH.read_text(encoding="utf-8"))["ratings"]
        club_rows = sorted((r for r in ratings if r["team"].upper() == team and r.get("rank")),
                           key=lambda r: r["rank"])[:5]
        top_rated = [{"name": r["name"], "rank": r["rank"], "rating": r["rating"],
                      "player_id": pid.get(_norm(r["name"]))} for r in club_rows]

    info["top_rated"] = top_rated
    info["ratings_year"] = CURRENT_YEAR
    return info


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
    ov = _contract_overrides()
    rb = _ratings_by_name()
    for r in result:
        nm = _norm(f"{r['first_name']} {r['last_name']}")
        o = ov.get((nm, (r.get("club_abbrev") or "").upper()))
        if o and (r.get("contract_status") != "contracted"
                  or (r.get("contracted_through_year") or 0) < o["end_year"]):
            r["contract_status"] = "contracted"
            r["contracted_through_year"] = o["end_year"]
        rr = rb.get(nm)
        r["position"] = rr.get("position") if rr else None
        r["rating"] = rr.get("rating") if rr else None
        r["rating_rank"] = rr.get("rank") if rr else None
        tv = _trade_value_board().get("by_id", {}).get(r["id"])
        r["trade_value"] = tv.get("value") if tv else None
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
    key = _norm(f"{profile['first_name']} {profile['last_name']}")
    club_ab = (profile.get("club_abbrev") or "").upper()
    contracts = _contracts_by_name()
    events = contracts.get("_by_name", {}).get(key, [])
    # drop a same-name player's confirmed signing (club-tagged current events
    # must match this player's club); untagged historical events stay
    events = [e for e in events if not (e.get("club") and (e.get("current") or e.get("afl_official") or e.get("manual"))
                                        and e["club"].upper() != club_ab)]
    profile["contract_events"] = events
    profile["contract_source"] = contracts.get("_meta") if events else None
    # a confirmed `current` re-signing supersedes a stale free-agent/OOC status
    o = _contract_overrides().get((key, club_ab))
    cur = next((cs for cs in profile["contract_status"] if cs["is_current"]), None)
    if o and cur and (cur["status"] != "contracted" or (cur["contracted_through_year"] or 0) < o["end_year"]):
        cur["status"] = "contracted"
        cur["contracted_through_year"] = o["end_year"]
        cur["source_url"] = o.get("source_url") or cur.get("source_url")
        rep = o.get("reporter")
        cur["source_note"] = f"Re-signed — {rep} (supersedes earlier status)" if rep else "Re-signed (supersedes earlier status)"
    rating = _ratings_by_name().get(key)
    profile["rating"] = {"rank": rating["rank"], "rating": rating["rating"]} if rating else None
    fant = _fantasy_index().get(key)
    profile["fantasy"] = {"af_avg": fant["af_avg"], "position": fant.get("position")} if fant else None
    scout = _scouting_index()
    sc = scout.get("_players", {}).get(key)
    profile["scouting"] = {**sc, **scout.get("_meta", {})} if sc else None
    profile["trade_value"] = _trade_value_board().get("by_id", {}).get(player_id)
    profile["form"] = _form_index().get("_players", {}).get(key)
    # rating history — find the player's Champion Data timeline by matching the
    # current-season record's cd_id, else by name across the history file
    profile["rating_history"] = []
    hist = _load_history()
    if hist:
        target = _norm(f"{profile['first_name']} {profile['last_name']}")
        cd_id = rating.get("cd_id") if rating else None
        tl = hist["timelines"].get(str(cd_id)) if cd_id else None
        if tl is None:
            tl = next((t for t in hist["timelines"].values() if _norm(t["name"]) == target), None)
        if tl:
            profile["rating_history"] = tl["seasons"]
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


def _news_items() -> list[dict]:
    """Up to 40 movement-news items from Google News RSS, newest first.
    Cached 15 minutes per serverless instance; shared by /api/news and the
    trending signal."""
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
            return items
        except requests.RequestException:
            return []  # feed down -> pages degrade gracefully
    return cached("news", 900, build)


@app.get("/api/news")
def news():
    """Movement news, headline + source + link out only. Paywalled outlets get
    linked like everyone else, never reproduced."""
    return _news_items()[:20]


MOVEMENT_NEWS_PATH = Path(__file__).resolve().parent.parent / "data" / "movement_news.json"


@app.get("/api/movement-watch")
def movement_watch(limit: int = 10):
    """Contract / free-agency / trade coverage from the AFL's own feed — the
    rumour-mill, headline + link out only (never reproduced)."""
    import json
    if not MOVEMENT_NEWS_PATH.exists():
        return {"items": []}
    data = json.loads(MOVEMENT_NEWS_PATH.read_text(encoding="utf-8"))
    return {"source": data.get("source"), "items": data.get("items", [])[:limit]}


@app.get("/api/trending-players")
def trending_players(limit: int = 10):
    """Players actually in the movement conversation — ranked by how many of
    the current news headlines mention them, newest headline attached. Padded
    with movement-signal players (RFA class, latest trades) if the feed is thin.
    (Click-through weighting is a future layer once a writable store exists.)"""
    items = _news_items()
    with db() as conn:
        players = [dict(r) for r in conn.execute(
            """SELECT p.id, p.first_name, p.last_name, c.name club, c.abbreviation abbrev
               FROM player p JOIN club c ON c.id = p.current_club_id
               WHERE p.current_club_id IS NOT NULL""")]
    # A full "First Last" match is unambiguous. A surname alone is only trusted
    # when it's distinctive: unique among listed players, 4+ chars, not a common
    # English word, appearing capitalised, and NOT followed by another capitalised
    # word (which would mean it's actually a first name, e.g. "Heath Mellody" or
    # the "Marsh"/"Coleman Medal" sponsor/award names).
    from collections import Counter
    surname_counts = Counter(p["last_name"].lower() for p in players)
    SURNAME_STOP = {"day", "king", "marsh", "heath", "green", "brown", "gray", "grey",
                    "little", "power", "love", "best", "sun", "gun", "english", "rush", "moore"}

    tally: dict[int, dict] = {}
    for item in items:
        title, title_l = item["title"], item["title"].lower()
        for p in players:
            full = f"{p['first_name']} {p['last_name']}".lower()
            surname = p["last_name"]
            hit = full in title_l or (
                surname_counts[surname.lower()] == 1 and len(surname) >= 4
                and surname.lower() not in SURNAME_STOP
                and re.search(rf"\b{re.escape(surname)}\b(?!\s+[A-Z])", title))
            if not hit:
                continue
            t = tally.setdefault(p["id"], {**p, "mentions": 0, "headline": None,
                                           "source": None, "url": None, "published": None})
            t["mentions"] += 1
            if t["published"] is None or (item["published"] or "") > (t["published"] or ""):
                t.update(headline=item["title"], source=item["source"],
                         url=item["url"], published=item["published"])

    ranked = sorted(tally.values(), key=lambda x: (x["mentions"], x["published"] or ""), reverse=True)

    if len(ranked) < limit:
        # pad with movement-signal players not already trending on news
        have = {t["id"] for t in ranked}
        for extra in trending():
            if extra["id"] not in have and len(ranked) < limit:
                ranked.append({**extra, "mentions": 0, "headline": None,
                               "reason": extra.get("reason"), "url": None, "source": None})
                have.add(extra["id"])
    return ranked[:limit]


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
RATINGS_HISTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "ratings_history.json"
FANTASY_PATH = Path(__file__).resolve().parent.parent / "data" / "fantasy_2026.json"
_fantasy_by_name: dict = {}


def _load_fantasy() -> dict:
    import json
    if not FANTASY_PATH.exists():
        return {}
    return json.loads(FANTASY_PATH.read_text(encoding="utf-8"))


def _fantasy_index() -> dict:
    if not _fantasy_by_name:
        data = _load_fantasy()
        for p in data.get("players", []):
            _fantasy_by_name[_norm(p["name"])] = p
    return _fantasy_by_name
_history_cache: dict = {}


def _load_history() -> dict:
    import json
    if not _history_cache and RATINGS_HISTORY_PATH.exists():
        _history_cache.update(json.loads(RATINGS_HISTORY_PATH.read_text(encoding="utf-8")))
    return _history_cache


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


CONTRACTS_PATH = Path(__file__).resolve().parent.parent / "data" / "contracts.json"
CONTRACTS_MANUAL_PATH = Path(__file__).resolve().parent.parent / "data" / "contracts_manual.json"
_contracts_cache: dict = {}
_overrides_cache = None


def _contract_overrides() -> dict:
    """`current` re-signings that supersede a stale contract status, keyed by
    normalised name → {end_year, source...}. Sourced from confirmed official
    signings in contracts.json (AFL.com.au) and hand-verified corrections in
    contracts_manual.json; the latest end year wins."""
    global _overrides_cache
    if _overrides_cache is None:
        import json
        _overrides_cache = {}

        def add(e):
            # keyed by (name, club) so same-name players at different clubs don't cross
            if e.get("current") and e.get("end_year") and e.get("club"):
                key = (_norm(e["name"]), e["club"].upper())
                prev = _overrides_cache.get(key)
                if not prev or e["end_year"] >= prev["end_year"]:
                    _overrides_cache[key] = {
                        "end_year": e["end_year"], "reporter": e.get("reporter"),
                        "source_url": e.get("source_url"), "date": e.get("date")}

        if CONTRACTS_PATH.exists():
            for e in json.loads(CONTRACTS_PATH.read_text(encoding="utf-8")).get("events", []):
                if e.get("afl_official"):
                    add(e)
        if CONTRACTS_MANUAL_PATH.exists():  # hand-verified wins last
            for e in json.loads(CONTRACTS_MANUAL_PATH.read_text(encoding="utf-8")).get("events", []):
                add(e)
    return _overrides_cache


SCOUTING_PATH = Path(__file__).resolve().parent.parent / "data" / "scouting_2026.json"
_scouting_cache: dict = {}


def _scouting_index() -> dict:
    """Percentile scouting reports keyed by normalised name, + the stat order/labels."""
    import json
    if not _scouting_cache and SCOUTING_PATH.exists():
        data = json.loads(SCOUTING_PATH.read_text(encoding="utf-8"))
        _scouting_cache["_players"] = data.get("players", {})
        _scouting_cache["_meta"] = {k: data[k] for k in ("order", "labels", "min_games", "attribution") if k in data}
    return _scouting_cache


FORM_PATH = Path(__file__).resolve().parent.parent / "data" / "form_2026.json"
_form_cache: dict = {}


def _form_index() -> dict:
    """Recent per-round form keyed by normalised name."""
    import json
    if not _form_cache and FORM_PATH.exists():
        _form_cache["_players"] = json.loads(FORM_PATH.read_text(encoding="utf-8")).get("players", {})
    return _form_cache


import datetime

_trade_value_cache: dict = {}


def _age_2026(dob):
    if not dob:
        return None
    try:
        d = datetime.date.fromisoformat(str(dob)[:10])
    except ValueError:
        return None
    ref = datetime.date(CURRENT_YEAR, 6, 30)
    return ref.year - d.year - ((ref.month, ref.day) < (d.month, d.day))


def _age_factor(age):
    if age is None:
        return 1.0
    if age <= 20:
        return 1.10
    if age <= 23:
        return 1.15
    if age <= 27:
        return 1.00
    if age <= 29:
        return 0.82
    if age <= 31:
        return 0.60
    return 0.40


def _contract_factor(status, years_left):
    if status == "unrestricted_fa":
        return 0.62
    if status == "restricted_fa":
        return 0.80
    if status == "out_of_contract":
        return 0.85
    if years_left >= 3:
        return 1.20
    if years_left == 2:
        return 1.08
    if years_left == 1:
        return 0.98
    return 0.85


def _trade_value_board() -> dict:
    """League-wide player trade values: AFL Player Rating x age factor x
    contract factor. Ranked; cached. Contract re-signings (overrides) applied."""
    if _trade_value_cache:
        return _trade_value_cache
    rb = _ratings_by_name()
    ov = _contract_overrides()
    out = []
    with db() as conn:
        for r in conn.execute(
                """SELECT p.id, p.first_name, p.last_name, p.dob, c.abbreviation club, c.name club_name,
                          cs.status, cs.contracted_through_year
                   FROM player p JOIN club c ON c.id = p.current_club_id
                   LEFT JOIN contract_status cs ON cs.player_id = p.id AND cs.is_current = 1
                   WHERE p.status = 'listed'"""):
            nm = _norm(f"{r['first_name']} {r['last_name']}")
            rr = rb.get(nm)
            if not rr or not rr.get("rating"):
                continue
            status, through = r["status"], r["contracted_through_year"]
            o = ov.get((nm, (r["club"] or "").upper()))
            if o:  # a confirmed re-signing supersedes a stale status
                status, through = "contracted", o["end_year"]
            age = _age_2026(r["dob"])
            years_left = max(0, (through or CURRENT_YEAR) - CURRENT_YEAR)
            af, cf = _age_factor(age), _contract_factor(status, years_left)
            out.append({
                "id": r["id"], "name": f"{r['first_name']} {r['last_name']}",
                "club": r["club"], "club_name": r["club_name"],
                "rating": rr["rating"], "age": age, "years_left": years_left,
                "status": status or "unknown", "age_factor": af, "contract_factor": cf,
                "value": round(rr["rating"] * af * cf),
            })
    out.sort(key=lambda x: -x["value"])
    for i, x in enumerate(out):
        x["rank"] = i + 1
    _trade_value_cache["list"] = out
    _trade_value_cache["by_id"] = {x["id"]: x for x in out}
    _trade_value_cache["count"] = len(out)
    return _trade_value_cache


@app.get("/api/trade-values")
def trade_values(limit: int = 100, club: str | None = None):
    """Player trade-value board — rating x age x contract. Transparent weights."""
    board = _trade_value_board()["list"]
    if club:
        board = [x for x in board if (x["club"] or "").upper() == club.upper()]
    return {"count": len(board), "year": CURRENT_YEAR,
            "note": "Trade Value = AFL Player Rating x age factor x contract factor.",
            "players": board[:limit]}


@app.get("/api/form-movers")
def form_movers(limit: int = 6):
    """Biggest recent risers: last-5 AFL Fantasy vs season average."""
    fi = _form_index().get("_players", {})
    fant = _fantasy_index()
    with db() as conn:
        ident = {_norm(f"{r['first_name']} {r['last_name']}"): (r["id"], r["club"])
                 for r in conn.execute("""SELECT p.id, p.first_name, p.last_name, c.abbreviation club
                                          FROM player p LEFT JOIN club c ON c.id = p.current_club_id
                                          WHERE p.status = 'listed'""")}
    out = []
    for nm, f in fi.items():
        season = (fant.get(nm) or {}).get("af_avg")
        if (f.get("played") or 0) < 3 or f.get("l5_af") is None or not season:
            continue
        who = ident.get(nm)
        out.append({"name": f["name"], "player_id": who[0] if who else None, "club": who[1] if who else None,
                    "l5_af": f["l5_af"], "season_af": season, "delta": round(f["l5_af"] - season, 1),
                    "l5_disp": f.get("l5_disp")})
    out.sort(key=lambda x: -x["delta"])
    return {"players": out[:limit]}


def _contracts_by_name() -> dict:
    """Contract/movement events (AFLRATINGS) grouped by normalised player name."""
    import json
    if not _contracts_cache and CONTRACTS_PATH.exists():
        data = json.loads(CONTRACTS_PATH.read_text(encoding="utf-8"))
        grouped: dict = {}
        for e in data.get("events", []):
            grouped.setdefault(_norm(e["name"]), []).append(e)
        _contracts_cache["_by_name"] = grouped
        _contracts_cache["_meta"] = {k: data[k] for k in ("source", "source_url", "attribution", "note") if k in data}
    return _contracts_cache


@app.get("/api/ratings")
def ratings(limit: int = 100, club: str | None = None, year: int | None = None):
    """Official AFL Player Ratings (Champion Data), ranked, for any season
    2015–current. Matched to ListTrac player pages by name so rows link through."""
    import json
    with db() as conn:
        pid = {_norm(f"{r['first_name']} {r['last_name']}"): r["id"]
               for r in conn.execute("SELECT id, first_name, last_name FROM player")}

    if year and year != CURRENT_YEAR:
        hist = _load_history()
        if not hist or str(year) not in hist.get("by_season", {}):
            raise HTTPException(404, f"no ratings for {year}")
        rows, attribution, source_url, total = (
            hist["by_season"][str(year)], hist["attribution"], hist["source_url"],
            len(hist["by_season"][str(year)]))
    else:
        if not RATINGS_PATH.exists():
            raise HTTPException(404, "ratings not built yet")
        data = json.loads(RATINGS_PATH.read_text(encoding="utf-8"))
        rows, attribution, source_url, total, year = (
            data["ratings"], data["attribution"], data["source_url"], len(data["ratings"]), data["year"])

    if club:
        rows = [r for r in rows if r["team"].upper() == club.upper()]
    rows = [{**r, "player_id": pid.get(_norm(r["name"]))} for r in rows[:limit]]
    return {"year": year, "attribution": attribution, "source_url": source_url,
            "years": _load_history().get("years", [CURRENT_YEAR]) or [CURRENT_YEAR],
            "count": total, "ratings": rows}


PROSPECTS_DIR = Path(__file__).resolve().parent.parent / "data"


def _bottom_ager_names() -> set:
    """Players who appear in a younger class's list are bottom-agers playing up
    a level — their true draft year is the younger class, and they are NOT
    eligible for the older draft. Reliable where we have the younger list;
    full coverage needs date-of-birth (not exposed by our current sources)."""
    import json
    names = set()
    for year in (2027, 2028):
        path = PROSPECTS_DIR / f"prospects_{year}.json"
        if path.exists():
            for p in json.loads(path.read_text(encoding="utf-8")).get("prospects", []):
                names.add((_norm(p["name"]), year))
    return names


@app.get("/api/prospects")
def prospects(year: int = 2026):
    """Draft prospect pool for a class. 2026 = U18 championships pool (Rookie
    Me Central + Reading the Play + Twomey). 2027/2028 = the U16-championships
    runway (All-Australian teams), preliminary this far out. Bottom-agers who
    belong to a younger class are tagged (not draft-eligible in this year)."""
    import json
    path = PROSPECTS_PATH if year == 2026 else PROSPECTS_DIR / f"prospects_{year}.json"
    if not path.exists():
        raise HTTPException(404, f"no prospect pool for {year}")
    pool = json.loads(path.read_text(encoding="utf-8"))
    younger = {name: y for name, y in _bottom_ager_names()}
    for p in pool.get("prospects", []):
        true_year = younger.get(_norm(p["name"]))
        if true_year and true_year > year:
            p["bottom_ager"] = True
            p["true_class"] = true_year
    return pool


PROSPECT_STATS_PATH = Path(__file__).resolve().parent.parent / "data" / "prospect_stats.json"
_prospect_stats: dict = {}


def _load_prospect_stats() -> dict:
    import json
    if not _prospect_stats and PROSPECT_STATS_PATH.exists():
        _prospect_stats.update(json.loads(PROSPECT_STATS_PATH.read_text(encoding="utf-8")))
    return _prospect_stats


@app.get("/api/prospect-stats")
def prospect_stats(name: str):
    """A prospect's full cross-competition playing history (Coates Talent
    League, SANFL, WAFL, national championships…), via Rookie Me Central."""
    data = _load_prospect_stats()
    rec = (data.get("players") or {}).get(name)
    return {"source": data.get("source"), "source_url": data.get("source_url"),
            "history": rec["history"] if rec else []}


def _find_prospect(name: str) -> dict | None:
    """Locate a prospect's pool metadata across the draft classes. A player can
    appear in more than one class (a bottom-ager plays up a level) — prefer the
    entry that carries an honour, since that's the more informative context."""
    import json
    matches = []
    for year in (2026, 2027, 2028):
        path = PROSPECTS_PATH if year == 2026 else PROSPECTS_DIR / f"prospects_{year}.json"
        if not path.exists():
            continue
        pool = json.loads(path.read_text(encoding="utf-8"))
        for p in pool.get("prospects", []):
            if _norm(p["name"]) == _norm(name):
                matches.append({**p, "draft_year": year, "stage": pool.get("stage", "u18"),
                                "sources": pool.get("sources", {}),
                                "also_in": [y for y in (2026, 2027, 2028)]})
    if not matches:
        return None
    matches.sort(key=lambda m: (bool(m.get("award")), m.get("stage") == "u16"), reverse=True)
    best = matches[0]
    best["also_in"] = sorted({m["draft_year"] for m in matches})
    return best


@app.get("/api/prospect")
def prospect(name: str):
    """Full prospect profile — pool metadata + cross-competition playing
    history. The prospect equivalent of a player page."""
    meta = _find_prospect(name)
    if meta is None:
        raise HTTPException(404, f"no prospect '{name}'")
    stats = _load_prospect_stats()
    rec = (stats.get("players") or {}).get(meta["name"]) or {"history": []}
    # a headline line: the most recent season with the most games
    hist = rec["history"]
    headline = max(hist, key=lambda r: (r["season"], r.get("gamesplayed") or 0)) if hist else None
    return {**meta, "history": hist, "headline": headline,
            "stats_source": stats.get("source"), "stats_source_url": stats.get("source_url")}


@app.get("/api/prospect-runway")
def prospect_runway():
    """The 3-year draft runway — one summary card per class."""
    import json
    out = []
    for year in (2026, 2027, 2028):
        path = PROSPECTS_PATH if year == 2026 else PROSPECTS_DIR / f"prospects_{year}.json"
        if not path.exists():
            continue
        d = json.loads(path.read_text(encoding="utf-8"))
        ps = d.get("prospects", [])
        top = sorted((p for p in ps if p.get("rank")), key=lambda p: p["rank"])[:3]
        out.append({
            "year": year,
            "stage": d.get("stage", "u18"),
            "forming": d.get("forming", False),
            "count": len(ps),
            "note": d.get("note", ""),
            "top": [{"name": p["name"], "state_team": p.get("state_team"),
                     "position": p.get("position"), "rank": p.get("rank")} for p in top],
        })
    return out


@app.get("/api/fantasy")
def fantasy(limit: int = 100, position: str | None = None, club: str | None = None):
    """AFL Fantasy (Dream Team) season averages, ranked. Matched to player
    pages by name. SuperCoach scoring is a separate feed (FootyWire) — a
    later addition."""
    data = _load_fantasy()
    if not data:
        raise HTTPException(404, "fantasy data not built yet")
    with db() as conn:
        pid = {_norm(f"{r['first_name']} {r['last_name']}"): r["id"]
               for r in conn.execute("SELECT id, first_name, last_name FROM player")}
    rows = data["players"]
    if position:
        # UI sends MID/FOR/DEF/RUC; CD positions are compound (MEDIUM_FORWARD etc.)
        kw = {"MID": "MIDFIELDER", "FOR": "FORWARD", "DEF": "DEFENDER", "RUC": "RUCK"}.get(
            position.upper(), position.upper())
        rows = [r for r in rows if kw in (r.get("position") or "").upper()]
    if club:
        rows = [r for r in rows if r["team"].upper() == club.upper()]
    rows = [{**r, "player_id": pid.get(_norm(r["name"]))} for r in rows[:limit]]
    return {"year": data["year"], "attribution": data["attribution"], "source_url": data["source_url"],
            "count": data["count"], "players": rows}


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


import os

# Star/like counters need a writable store (the DB is a read-only snapshot).
# Uses an Upstash Redis REST endpoint — set UPSTASH_REDIS_REST_URL +
# UPSTASH_REDIS_REST_TOKEN (or Vercel KV's KV_REST_API_URL/TOKEN) in the
# environment. Absent → the API reports unconfigured and the UI hides stars.
_KV_URL = os.environ.get("UPSTASH_REDIS_REST_URL") or os.environ.get("KV_REST_API_URL")
_KV_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN") or os.environ.get("KV_REST_API_TOKEN")


def _kv(*command: str):
    """Run one Redis command via the Upstash REST API. Returns the result, or
    None if no store is configured / the call fails."""
    if not (_KV_URL and _KV_TOKEN):
        return None
    try:
        resp = requests.post(_KV_URL.rstrip("/"), json=list(command),
                             headers={"Authorization": f"Bearer {_KV_TOKEN}"}, timeout=6)
        resp.raise_for_status()
        return resp.json().get("result")
    except requests.RequestException:
        return None


def _star_key(kind: str, ident: str) -> str:
    kind = "player" if kind == "player" else "club"
    return f"stars:{kind}:{re.sub(r'[^A-Za-z0-9_-]', '', ident)}"


@app.get("/api/stars")
def stars(kind: str, ids: str):
    """Current star counts for a comma-separated list of player/club ids."""
    id_list = [i for i in ids.split(",") if i][:100]
    if not (_KV_URL and _KV_TOKEN) or not id_list:
        return {"configured": bool(_KV_URL and _KV_TOKEN), "counts": {}}
    keys = [_star_key(kind, i) for i in id_list]
    result = _kv("MGET", *keys) or []
    counts = {i: int(v) for i, v in zip(id_list, result) if v is not None}
    return {"configured": True, "counts": counts}


@app.post("/api/star")
def star(payload: dict):
    """Add or remove a star for a player/club. `delta` is +1 (default) or -1."""
    kind, ident = payload.get("kind"), str(payload.get("id", ""))
    if kind not in ("player", "club") or not ident:
        raise HTTPException(400, "kind (player|club) and id required")
    if not (_KV_URL and _KV_TOKEN):
        raise HTTPException(503, "star store not configured")
    delta = -1 if payload.get("delta") == -1 else 1
    new = _kv("INCRBY", _star_key(kind, ident), str(delta))
    return {"count": int(new) if new is not None else 0}


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
    result = rows(query + " ORDER BY c.name, p.last_name", tuple(params))
    ov = _contract_overrides()
    rb = _ratings_by_name()
    out = []
    for r in result:
        nm = _norm(f"{r['first_name']} {r['last_name']}")
        o = ov.get((nm, (r.get("club_abbrev") or "").upper()))
        if o and (r.get("contract_status") != "contracted"
                  or (r.get("contracted_through_year") or 0) < o["end_year"]):
            r["contract_status"] = "contracted"
            r["contracted_through_year"] = o["end_year"]
        if status and r["contract_status"] != status:
            continue  # re-signed out of the requested bucket
        rr = rb.get(nm)
        r["rating"] = rr.get("rating") if rr else None
        r["rating_rank"] = rr.get("rank") if rr else None
        r["position"] = rr.get("position") if rr else None
        out.append(r)
    return out


# static frontend — mounted last so API routes win. Guarded: if the directory
# is missing from a serverless bundle, degrade to API-only instead of crashing
# the whole function at import time (StaticFiles raises on a missing dir).
if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
