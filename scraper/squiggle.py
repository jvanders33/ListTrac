"""
Squiggle API ingestion — the cleanest legal footing of any AFL data source,
since it's an intentionally public API (not scraped HTML).

Docs: https://squiggle.com.au/#api
Rate limit: be polite — 1 request/sec is the community norm, no official cap published.
"""
import time
import requests

BASE_URL = "https://api.squiggle.com.au/"
HEADERS = {"User-Agent": "ListTrac (github.com/jvanders33/ListTrac)"}  # Squiggle asks for a UA identifying your app


def _get(params: dict) -> dict:
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    time.sleep(1)  # politeness delay between calls
    return resp.json()


def get_teams() -> list[dict]:
    """Returns all AFL teams — id, name, abbrev, logo."""
    return _get({"q": "teams"})["teams"]


def get_season_games(year: int) -> list[dict]:
    """Returns fixture/results for a given season."""
    return _get({"q": "games", "year": year})["games"]


def get_standings(year: int, round_num: int | None = None) -> list[dict]:
    """Returns ladder for a season, optionally at a specific round."""
    params = {"q": "standings", "year": year}
    if round_num is not None:
        params["round"] = round_num
    return _get(params)["standings"]


if __name__ == "__main__":
    teams = get_teams()
    print(f"Fetched {len(teams)} teams")
    for t in teams[:3]:
        print(t)
