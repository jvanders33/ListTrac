"""
Zerohanger scraper — off-contract players by year, grouped by club.

zerohanger.com/afl/players/off-contract-{year} is a WordPress page whose main
content is one <div class="shadowBox"> per club: an <h4> club name and a <p>
of comma-separated <a href='/afl/players/{slug}/'> links, ending with
"N players off contract". Pages exist for the current year out to ~year+4
(2026-2030 as of July 2026), and include Tasmania from 2026 on.

This feeds the contract_status table: everyone here is out of contract at the
end of {year} (status refinement to restricted/unrestricted FA comes from the
AFL.com.au list — see afl_free_agents.py). The player slug is kept for
cross-source identity matching.
"""
import time

import requests
from bs4 import BeautifulSoup

BASE = "https://www.zerohanger.com"
HEADERS = {"User-Agent": "ListTrac (github.com/jvanders33/ListTrac)"}


def fetch_off_contract(year: int) -> dict[str, list[dict]]:
    """Returns {club_name: [{"name": ..., "zerohanger_slug": ...}, ...]}."""
    url = f"{BASE}/afl/players/off-contract-{year}/"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    time.sleep(1)  # politeness delay

    soup = BeautifulSoup(resp.text, "html.parser")

    clubs: dict[str, list[dict]] = {}
    for box in soup.find_all("div", class_="shadowBox"):
        h4 = box.find("h4")
        if h4 is None:
            continue  # sidebar widget, not a club block
        players = [
            {
                "name": a.get_text(strip=True),
                "zerohanger_slug": a["href"].strip("/").removeprefix("afl/players/"),
                "source_url": url,
            }
            for a in box.find_all("a", href=True)
            if a["href"].startswith("/afl/players/")
        ]
        if players:
            clubs[h4.get_text(strip=True)] = players
    return clubs


if __name__ == "__main__":
    clubs = fetch_off_contract(2026)
    total = sum(len(p) for p in clubs.values())
    print(f"2026 off-contract: {len(clubs)} clubs, {total} players")
    for club, players in list(clubs.items())[:2]:
        print(f"\n{club} ({len(players)})")
        for p in players[:3]:
            print(" ", p["name"], "-", p["zerohanger_slug"])
