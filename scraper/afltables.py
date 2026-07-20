"""
AFL Tables scraper — current season player lists.

No API here, so this is real HTML scraping (unlike squiggle.py). Structure:
one <table> per club on https://afltables.com/afl/stats/{year}.html, first
row is the club name, second row is headers (#, Player, GM, ...), remaining
rows are players. Jumper number + name is enough to reconstruct the current
list; the other ~25 stat columns aren't needed for ListTrac's list/movement
use case but are there if useful later.
"""
import time
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "ListTrac (github.com/jvanders33/ListTrac)"}


def fetch_season_lists(year: int) -> dict[str, list[dict]]:
    """Returns {club_name: [{"jumper": int, "name": "Last, First"}, ...]}"""
    url = f"https://afltables.com/afl/stats/{year}.html"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    time.sleep(1)  # politeness delay — no robots.txt crawl-delay published, but don't hammer it

    soup = BeautifulSoup(resp.text, "html.parser")
    tables = soup.find_all("table")

    lists: dict[str, list[dict]] = {}
    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 3:
            continue  # not a club table

        # First row holds the club name (with extra link text appended — strip it)
        header_cell = rows[0].find_all(["td", "th"])
        if not header_cell:
            continue
        club_name = header_cell[0].get_text(strip=True).split("[")[0].strip()
        if not club_name:
            continue

        players = []
        for row in rows[2:]:  # skip club name row + column header row
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if len(cells) < 2 or not cells[0].isdigit():
                continue
            players.append({"jumper": int(cells[0]), "name": cells[1]})

        if players:
            lists[club_name] = players

    return lists


if __name__ == "__main__":
    lists = fetch_season_lists(2026)
    print(f"Fetched lists for {len(lists)} clubs")
    for club, players in list(lists.items())[:2]:
        print(f"\n{club} ({len(players)} players)")
        for p in players[:3]:
            print(" ", p)
