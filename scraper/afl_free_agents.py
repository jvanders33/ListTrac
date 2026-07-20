"""
AFL.com.au free agents scraper — restricted/unrestricted FA by club.

The AFL publishes its official free agent list as a news article that gets
re-issued at a new URL whenever it's updated, so the article URL is an input
here, not a constant. Find the latest via afl.com.au search ("free agents
list") and pass it in; DEFAULT_URL is the newest known at time of writing.

Article body embeds one <table>: a club header row (colspan cell, bold,
ALL-CAPS club name), a "Restricted | Unrestricted" label row, then data rows
with restricted names in column 0 and unrestricted in column 1 (blank cells
are non-breaking spaces). "*" after a name denotes a previously delisted
player. This is the authority for restricted_fa/unrestricted_fa in
contract_status; zerohanger.py covers plain out-of-contract.
"""
import time

import requests
from bs4 import BeautifulSoup

DEFAULT_URL = "https://www.afl.com.au/news/1484077/2026afl-free-agentslist"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ListTrac (github.com/jvanders33/ListTrac)"}


def _clean(text: str) -> str:
    return text.replace("\xa0", " ").strip()


def fetch_free_agents(article_url: str = DEFAULT_URL) -> dict[str, dict[str, list[dict]]]:
    """Returns {club: {"restricted": [...], "unrestricted": [...]}} where each
    entry is {"name", "previously_delisted", "source_url"}."""
    resp = requests.get(article_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    time.sleep(1)  # politeness delay

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if table is None:
        raise ValueError(f"No table found in article — layout changed? {article_url}")

    clubs: dict[str, dict[str, list[dict]]] = {}
    current: dict[str, list[dict]] | None = None
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        texts = [_clean(c.get_text(" ", strip=True)) for c in cells]

        if len(cells) == 1 or (cells and cells[0].get("colspan")):
            # club header row
            club = texts[0]
            if club:
                current = {"restricted": [], "unrestricted": []}
                clubs[club.title()] = current
            continue
        if current is None or len(texts) < 2 or texts[:2] == ["Restricted", "Unrestricted"]:
            continue

        for column, text in zip(("restricted", "unrestricted"), texts):
            name = text.rstrip("*").strip()
            if not name or not any(ch.isalpha() for ch in name):
                continue
            current[column].append({
                "name": name,
                "previously_delisted": text.endswith("*"),
                "source_url": article_url,
            })
    return clubs


if __name__ == "__main__":
    clubs = fetch_free_agents()
    n_r = sum(len(c["restricted"]) for c in clubs.values())
    n_u = sum(len(c["unrestricted"]) for c in clubs.values())
    print(f"{len(clubs)} clubs, {n_r} restricted, {n_u} unrestricted")
    for club, fas in list(clubs.items())[:3]:
        print(f"\n{club}")
        print("  restricted:", [p["name"] for p in fas["restricted"]])
        print("  unrestricted:", [p["name"] + ("*" if p["previously_delisted"] else "") for p in fas["unrestricted"]][:5])
