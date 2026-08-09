"""
Footywire scraper — contract end years for every listed player.

footywire.com/afl/footy/out_of_contract_players?year={Y} lists the players
whose contracts expire at the end of season Y, one table per club, with years
of service and their FA class at expiry ("Unrestricted Free Agent",
"Restricted Free Agent", "Non-Free Agent", "Unknown"). Walking Y over the
next several seasons yields the contracted-through year for the whole league —
the piece Zerohanger's current-year page can't provide.

The player profile link slug (pp-{club-slug}--{player-slug}) is Footywire's
stable player id and is kept as footywire_id for cross-source reconciliation.
Club identity comes from that slug too (North Melbourne is "kangaroos").
"""
import re
import time

import requests

from identity import CLUBS

BASE = "https://www.footywire.com/afl/footy/out_of_contract_players"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ListTrac (github.com/jvanders33/ListTrac)"}

_SLUG_TO_CLUB = {v["footywire"]: canonical for canonical, v in CLUBS.items()}


def fetch_out_of_contract(year: int) -> dict[str, list[dict]]:
    """{canonical_club: [{name, footywire_id, years_service, fa_at_expiry}]}
    for players whose deals expire at the end of `year`.

    Best-effort by design: Footywire only *supplements* contract through-years
    (the primary status comes from Zerohanger/AFL.com.au), and it periodically
    503s automated clients. So a network/HTTP failure is retried a couple of
    times and then degrades to an empty result — it must never abort the whole
    database rebuild the way an uncaught raise_for_status would."""
    text = None
    for attempt in range(3):
        try:
            resp = requests.get(BASE, params={"year": year}, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            text = resp.text
            break
        except requests.RequestException as e:
            print(f"  [footywire] {year}: attempt {attempt + 1}/3 failed ({e})")
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    if text is None:
        print(f"  [footywire] {year}: unavailable — skipping (supplementary source)")
        return {}
    time.sleep(1)  # politeness delay

    clubs: dict[str, list[dict]] = {}
    pattern = re.compile(
        r'<a href="(pp-([a-z\-]+)--[a-z\-]+)">([^<]+)</a></td>\s*'
        r'<td align="center">(\d*)</td>\s*'
        r'<td align="center" id="status_\d+">([^<]*)</td>', re.S)
    for m in pattern.finditer(text):
        fw_id, club_slug, name, service, status = m.groups()
        club = _SLUG_TO_CLUB.get(club_slug)
        if club is None:
            continue
        clubs.setdefault(club, []).append({
            "name": name.strip(),
            "footywire_id": fw_id,
            "years_service": int(service) if service.isdigit() else None,
            "fa_at_expiry": status.strip() or None,
            "source_url": f"{BASE}?year={year}",
        })
    return clubs


if __name__ == "__main__":
    for y in (2027, 2028):
        clubs = fetch_out_of_contract(y)
        total = sum(len(p) for p in clubs.values())
        print(f"{y}: {len(clubs)} clubs, {total} players")
        first = next(iter(clubs.items()))
        print("  e.g.", first[0], first[1][:2])
