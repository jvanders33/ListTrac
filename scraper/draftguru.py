"""
Draftguru scraper — historical draft picks, trades, and club lists by year.

Draftguru (www.draftguru.com.au) chapters everything by year, which makes it
the backbone of ListTrac's historical data. Three page types matter:

  /years/{year}          one big <table class="general sortable big-pick-movements">
                         covering every player movement that year: FA signings,
                         trades, and every draft (National/Rookie/Pre-Season/
                         Mid-Season, plus Pre-Draft/Post-Draft signings).
  /trades/year/{year}    <table class="all-trades"> of trade blocks: a header row
                         linking to /trades/{slug}, then one row per club showing
                         what that club gave up. Pick components ("#53") carry an
                         <span class="extra"> with what the pick resolved to.
  /lists/{year}/{club}   club list for a season: jumper, player, grade, DOB,
                         height + per-season stats. DOB is gold for reconciling
                         player identity across sources.

Player links are /players/{slug}/{n} — slug+n is stable and is stored as
draftguru_id for cross-source matching. The bare domain 301s to www, so BASE
includes it. No API, no auth, no Cloudflare challenge as of July 2026.
"""
import re
import time

import requests
from bs4 import BeautifulSoup

BASE = "https://www.draftguru.com.au"
HEADERS = {"User-Agent": "ListTrac (github.com/jvanders33/ListTrac)"}

# td.draft text → schema draft_type for rows that are actual draft selections.
# The rest (Free Agency, Trade, Pre-Draft, Post-Draft) are transactions, not picks.
DRAFT_TYPE_MAP = {
    "National": "national",
    "Rookie": "rookie",
    "Pre-Season": "pre_season",
    "Mid-Season": "mid_season",
}

# /years/{year}/{slug} sub-link -> movement label, for years where the table
# omits the Draft column because only one movement category existed (e.g. 1987)
MOVEMENT_SLUGS = {
    "national_draft": "National",
    "rookie_draft": "Rookie",
    "preseason_draft": "Pre-Season",
    "midseason_draft": "Mid-Season",
    "free-agency": "Free Agency",
    "pre-draft": "Pre-Draft",
    "post-draft": "Post-Draft",
}


def _get_soup(path: str) -> BeautifulSoup:
    # a full backfill is ~100 requests — transient resets happen, so retry
    # with backoff before giving up (matters most for the weekly CI refresh)
    for attempt in range(3):
        try:
            resp = requests.get(BASE + path, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            break
        except (requests.ConnectionError, requests.Timeout):
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    time.sleep(1)  # politeness delay, same as afltables.py
    return BeautifulSoup(resp.text, "html.parser")


def _player_ref(a) -> dict:
    """From an <a href="/players/{slug}/{n}"> anchor: name + stable draftguru id."""
    return {
        "name": a.get_text(strip=True).replace("\xa0", " "),
        "draftguru_id": a["href"].removeprefix("/players/"),
    }


def fetch_year_movements(year: int) -> list[dict]:
    """All player movements for a year — one dict per row of the movements table.

    movement: "Free Agency" | "Trade" | "National" | "Rookie" | "Pre-Season" |
              "Mid-Season" | "Pre-Draft" | "Post-Draft"
    draft_type: schema value if the row is a draft selection, else None
    """
    soup = _get_soup(f"/years/{year}")
    table = soup.find("table", class_="big-pick-movements")
    if table is None:
        return []

    # single-category years drop the Draft column; the sub-nav tells us which
    categories = {MOVEMENT_SLUGS[a["href"].rsplit("/", 1)[-1]]
                  for a in soup.find_all("a", href=True)
                  if a["href"].startswith(f"/years/{year}/")
                  and a["href"].rsplit("/", 1)[-1] in MOVEMENT_SLUGS}
    sole_category = categories.pop() if len(categories) == 1 else None

    movements = []
    for row in table.find_all("tr"):
        player_cell = row.find("td", class_="player")
        if player_cell is None or player_cell.a is None:
            continue  # header row

        draft_cell = row.find("td", class_="draft")
        movement = draft_cell.get_text(strip=True) if draft_cell else sole_category
        if movement is None:
            continue  # no Draft column and no unambiguous category to infer
        number_text = row.find("td", class_="number").get_text(strip=True)
        club_a = row.find("td", class_="club").a
        # Two td.category cells: the first is the "Pick" column (usually empty),
        # the second is "Signing" — e.g. "FA(Restricted)" on free agency rows.
        categories = row.find_all("td", class_="category")
        signing = categories[1].get_text(" ", strip=True) if len(categories) > 1 else ""

        height_cell = row.find("td", class_="height")
        grade_cell = row.find("td", class_="grade")
        origin = [a.get_text(strip=True) for a in row.find("td", class_="from-club").find_all("a")]

        movements.append({
            "year": year,
            "movement": movement,
            "draft_type": DRAFT_TYPE_MAP.get(movement),
            "pick_number": int(number_text) if number_text.isdigit() else None,
            "club": club_a.get_text(strip=True),
            "club_slug": club_a["href"].removeprefix("/clubs/"),
            "signing": signing,
            **_player_ref(player_cell.a),
            "height_cm": int(h) if (h := height_cell.get("data-sorttable_customkey", "")).isdigit() else None,
            "grade": grade_cell.get_text(strip=True) if grade_cell else None,
            "origin_clubs": origin,
            "source_url": f"{BASE}/years/{year}",
        })
    return movements


def _parse_trade_component(text: str, extra: str | None) -> dict:
    """One side-component of a trade: a current-year pick ("#53"), a future
    pick ("#2026R2 (St Kilda)" — round + the club whose natural pick it is),
    or a player (anything else)."""
    comp = {"type": "player", "text": text, "pick_number": None, "resolved": extra}
    if m := re.fullmatch(r"#(\d+)", text):
        comp.update(type="pick", pick_number=int(m.group(1)))
    elif m := re.fullmatch(r"#(\d{4})R(\d)\s*\((.+?)\)", text):
        comp.update(type="future_pick", future_year=int(m.group(1)),
                    future_round=int(m.group(2)), origin_club=m.group(3).strip())
    elif "round" in text.lower() or "pick" in text.lower():
        comp["type"] = "future_pick"
    return comp


def fetch_year_trades(year: int) -> list[dict]:
    """All trades for a year as blocks: {slug, title, source_url, sides},
    sides = [{club, components}] where each component says what that club
    RECEIVED (verified against known trades: Reidy appears on Carlton's row
    of the 2025 deal that sent him Fremantle -> Carlton)."""
    soup = _get_soup(f"/trades/year/{year}")
    table = soup.find("table", class_="all-trades")
    if table is None:
        return []

    trades: list[dict] = []
    for row in table.find_all("tr"):
        classes = row.get("class", [])
        if "trade-header" in classes:
            a = row.a
            trades.append({
                "year": year,
                "slug": a["href"].removeprefix("/trades/"),
                "title": a.get_text(strip=True),
                "source_url": BASE + a["href"],
                "sides": [],
            })
        elif "trade-club" in classes and trades:
            desc = row.find("td", class_="description")
            # span.extra holds each component's resolution (e.g. what a pick
            # became); pull them out in order, then split the remaining text on +
            extras = [
                s.get_text(" ", strip=True).replace("\xa0", " ").strip("()")
                for s in desc.find_all("span", class_="extra")
            ]
            for s in desc.find_all("span", class_="extra"):
                s.decompose()
            parts = [p.strip() for p in desc.get_text(" ", strip=True).replace("\xa0", " ").split("+") if p.strip()]
            components = [
                _parse_trade_component(part, extras[i] if i < len(extras) else None)
                for i, part in enumerate(parts)
            ]
            trades[-1]["sides"].append({
                "club": row.find("td", class_="club-name").get_text(strip=True),
                "components": components,
            })
    return trades


def fetch_pick_history(pick_number: int) -> list[dict]:
    """Every national-draft selection ever made at a pick number, from
    /picks/{n}: year, player, career games, honour codes (AA, Prem, B&F,
    Coleman, Norm Smith, AFLCA...). Feeds the per-pick outcome stats."""
    soup = _get_soup(f"/picks/{pick_number}")
    table = soup.find("table", class_="general")
    if table is None:
        return []

    history = []
    for row in table.find_all("tr"):
        year_cell = row.find("td", class_="year")
        name_cell = row.find("td", class_="name")
        if year_cell is None or name_cell is None or name_cell.a is None:
            continue
        games_cell = row.find("td", class_="games")
        games = games_cell.get("data-sorttable_customkey", "") if games_cell else ""
        honours_cell = row.find("td", class_="honours")
        honours = [s.get_text(strip=True) for s in honours_cell.find_all("span", class_="honour")] if honours_cell else []
        history.append({
            "pick_number": pick_number,
            "year": int(year_cell.get_text(strip=True)),
            **_player_ref(name_cell.a),
            "games": int(games) if games.lstrip("-").isdigit() else None,
            "honours": honours,
        })
    return history


def fetch_club_list(year: int, club_slug: str) -> list[dict]:
    """A club's list for a season: jumper, name, draftguru_id, DOB, height, grade."""
    soup = _get_soup(f"/lists/{year}/{club_slug}")
    table = soup.find("table", class_="general")
    if table is None:
        return []

    players = []
    for row in table.find_all("tr"):
        name_cell = row.find("td", class_="name")
        if name_cell is None or name_cell.a is None:
            continue

        number_text = row.find("td", class_="number").get_text(strip=True)
        dob_cell = row.find("td", class_="dob")
        height_cell = row.find("td", class_="height")
        grade_cell = row.find("td", class_="rating")
        list_type = row.find("td", class_="listtype").get_text(strip=True)

        players.append({
            "jumper": int(number_text) if number_text.isdigit() else None,
            **_player_ref(name_cell.a),
            "dob": dob_cell.get("data-sorttable_customkey") if dob_cell else None,
            "height_cm": int(h) if (h := height_cell.get("data-sorttable_customkey", "").lstrip("-")).isdigit() else None,
            "grade": grade_cell.get_text(strip=True) if grade_cell else None,
            "list_type": list_type or None,  # blank = senior list
            "source_url": f"{BASE}/lists/{year}/{club_slug}",
        })
    return players


if __name__ == "__main__":
    movements = fetch_year_movements(2025)
    print(f"2025 movements: {len(movements)}")
    by_type: dict[str, int] = {}
    for m in movements:
        by_type[m["movement"]] = by_type.get(m["movement"], 0) + 1
    print(" ", by_type)
    for m in movements[:3]:
        print(" ", m["movement"], m["pick_number"], m["club"], "-", m["name"], m["signing"])

    trades = fetch_year_trades(2025)
    print(f"\n2025 trades: {len(trades)}")
    for t in trades[:2]:
        print(" ", t["title"])
        for side in t["sides"]:
            print("   ", side["club"], "gave:", [c["text"] for c in side["components"]])

    roster = fetch_club_list(2026, "adelaide")
    print(f"\nAdelaide 2026 list: {len(roster)} players")
    for p in roster[:3]:
        print(" ", p["jumper"], p["name"], p["dob"], p["draftguru_id"])
