"""
2026 U18 National Championships prospect pool — feeds the interactive mock draft.

Two sources, merged by normalized name:
  - Squads: Rookie Me Central's championships guide lists every player for all
    five teams (Vic Metro, Vic Country, SA, WA, Allies) as "N - Name (Club)"
    paragraphs. 178 players at time of writing.
  - Rankings: Reading the Play's rolling 2026 Top 50 power rankings (V1.0,
    April 2026) supplies rank, position, height, and club ties (father-son /
    NGA / academy). Spelling differs between sources occasionally
    (Aidan/Aiden McCartney), so matching falls back to surname + initial.

Run as a script to regenerate data/prospects_2026.json:
    python scraper/u18_champs.py
"""
import json
import re
import sys
from pathlib import Path

import requests

from identity import match_players

SQUADS_URL = ("https://central.rookieme.com/afl/2026/06/12/"
              "need-to-know-2026-afl-under-18-national-championships/")
RANKINGS_URL = "https://readingtheplay.wordpress.com/2026/04/19/rolling-2026-draft-power-rankings-1-50/"
HEADERS = {"User-Agent": "ListTrac (github.com/jvanders33/ListTrac)"}
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "prospects_2026.json"

# Reading the Play Top 50 V1.0 (19 Apr 2026): rank, name, position, height,
# club tie. Transcribed rather than scraped — WordPress themes shift and this
# is a point-in-time editorial list; bump manually when a new version drops.
RANKINGS = [
    (1, "Dougie Cochrane", "Key Forward/Utility", 195, None),
    (2, "Harry Van Hattum", "Ruck/Key Forward", 205, None),
    (3, "Cody Walker", "Midfielder", 184, "Carlton F/S"),
    (4, "Arki Butler", "Medium Forward/Midfielder", 182, None),
    (5, "Kodah Edwards", "Midfielder/Medium Forward", 183, None),
    (6, "Noah Williams", "Midfield/Rebounding Defender", 177, None),
    (7, "Clancy Snell", "Key Defender", 196, None),
    (8, "Lucas Robinson", "Inside Midfielder", 191, "Fremantle NGA"),
    (9, "Marlon Neocleous", "Small Forward", 168, None),
    (10, "Ethan Herbert", "Ruck/Key Forward", 200, None),
    (11, "Xavier Ladbrook", "Key Defender", 201, None),
    (12, "Gus Teixeira", "Midfielder/Medium Forward", 181, None),
    (13, "Gabriel Patterson", "Medium Forward", 184, None),
    (14, "Koby LeCras", "Medium Forward/Winger", 192, None),
    (15, "Ethan Drever", "Inside Midfielder", 188, None),
    (16, "Lewis Houndsome", "Key Forward/Ruck", 199, None),
    (17, "Jackson Phillips", "Midfielder/Forward", 182, None),
    (18, "Heath Mellody", "Winger/Rebounding Defender", 184, None),
    (19, "Darcy Szerszyn", "Medium Defender", 188, None),
    (20, "Aidan McCartney", "Medium Forward", 191, "Sydney Academy & North Melbourne F/S"),
    (21, "Jack Pickett", "Key Forward", 193, None),
    (22, "Blake Justice", "Midfielder/Medium Forward", 191, "Essendon NGA"),
    (23, "Jacob McNicol", "Midfielder", 177, None),
    (24, "Tanner Armstrong", "Midfielder/Small Utility", 177, "Richmond NGA"),
    (25, "Archie Van Dyk", "Midfielder", 185, None),
    (26, "Cody Templeton", "Midfielder/Small Forward", 180, None),
    (27, "Kale Matthews-Hampton", "Medium Defender/Midfielder", 189, None),
    (28, "Harrison Chapman", "Midfielder/Outside Utility", 189, None),
    (29, "Will Malady", "Medium Forward", 190, None),
    (30, "Khaled El Souki", "Small Forward/Midfielder", 175, "Western Bulldogs NGA"),
    (31, "Lachlan Hicks", "Midfielder", 183, None),
    (32, "Seb Marsic", "Key Forward", 194, None),
    (33, "Marcus Prasad", "Small Forward", 167, None),
    (34, "Harvie Cooke", "Midfielder/Small Forward", 176, None),
    (35, "Caylen Murray", "Rebounding Defender/Midfielder", 183, "Brisbane Academy"),
    (36, "Jack Gordon", "Midfielder/Medium Defender", 185, None),
    (37, "Albert MacGowan", "Midfielder", 187, None),
    (38, "Max Downes", "Medium Forward/Midfielder", 182, None),
    (39, "Jordan Knapp", "Midfielder", 179, None),
    (40, "Tate Hodgson", "Key Defender", 197, None),
    (41, "Garrison Kenh", "Medium Defender", 182, "West Coast NGA"),
    (42, "Gus Kennedy", "Utility", 186, None),
    (43, "Archie Hill", "Rebounding Defender", 182, "Gold Coast Academy"),
    (44, "Sam Gayfer", "Key Forward", 194, None),
    (45, "Ethan Matthews", "Winger/Small Defender", 185, "GWS Academy"),
    (46, "Benji Van Rooyen", "Ruck/Key Forward", 203, None),
    (47, "Archie Elliott", "Medium Forward", 182, None),
    (48, "Lachlan McGlade", "Small Forward", 175, "West Coast NGA"),
    (49, "George Gale", "Winger/Medium Defender", 187, None),
    (50, "Angus Tippett", "Inside Midfielder", 194, None),
]

# Cal Twomey's Phantom Form Guide, July 2026 edition — the sharpest current
# read on the top of the order. Primary ranking; Reading the Play covers the
# tail. Bump when the next edition drops (they're roughly monthly).
TWOMEY_URL = ("https://www.afl.com.au/news/1565947/"
              "cal-twomeys-phantom-form-guide-top-draft-prospects-july-ranking")
TWOMEY_JULY = [
    "Dougie Cochrane", "Cody Walker", "Gus Teixeira", "Arki Butler",
    "Harry Van Hattum", "Ethan Drever", "Heath Mellody", "Ethan Matthews",
    "Clancy Snell", "Leo Steed", "Wil Malady", "Noah Williams",
    "Mitchell Harris", "Caylen Murray", "Kodah Edwards", "Jackson Phillips",
    "Jack Pickett", "Sam Gayfer", "Ethan Herbert", "Toby Krasna",
    "Tyson Bradley", "Jake Eime", "Jack Slattery", "Marlon Neocleous",
    "George Gale",
]

# ties confirmed by later reporting that the ranking lists missed
TIE_OVERRIDES = {"Dougie Cochrane": "Port Adelaide NGA"}

# Allies academies imply a club tie even without a top-50 note
ACADEMY_TIES = {
    "Giants Academy": "GWS Academy",
    "Swans Academy": "Sydney Academy",
    "Lions Academy": "Brisbane Academy",
    "Suns Academy": "Gold Coast Academy",
    "Tasmania Devils": "Tasmania priority access",
}

TEAM_NAMES = ["ALLIES", "SOUTH AUSTRALIA", "VIC COUNTRY", "VIC METRO", "WESTERN AUSTRALIA"]


def fetch_squads() -> dict[str, list[dict]]:
    """{team: [{jumper, name, club}]} from the championships guide."""
    resp = requests.get(SQUADS_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    html = resp.text.replace("&#8211;", "-").replace("&#8217;", "'").replace("&amp;", "&")

    teams: dict[str, list[dict]] = {}
    pattern = r'<p><strong>(' + "|".join(TEAM_NAMES) + r'):?</strong></p>\s*<p>(.*?)</p>'
    for m in re.finditer(pattern, html, re.S):
        blob = re.sub(r"<[^>]+>", "", m.group(2))
        teams[m.group(1).title()] = [
            {"jumper": int(pm.group(1)), "name": pm.group(2).strip(), "club": pm.group(3).strip()}
            for pm in re.finditer(r"(\d+)\s*-\s*([^(,]+?)\s*\(([^)]+)\)", blob)
        ]
    return teams


def build_pool() -> list[dict]:
    squads = fetch_squads()
    prospects = []
    for team, players in squads.items():
        for p in players:
            tie = ACADEMY_TIES.get(p["club"]) if team == "Allies" else None
            prospects.append({
                "name": p["name"], "state_team": team, "junior_club": p["club"],
                "jumper": p["jumper"], "rank": None, "position": None,
                "height_cm": None, "tie": tie,
            })

    ranked = [{"name": n, "rank": r, "position": pos, "height_cm": h, "tie": tie}
              for r, n, pos, h, tie in RANKINGS]
    matched, unmatched_rank, _ = match_players(ranked, prospects)
    for rank_row, prospect in matched:
        prospect["rank_rtp"] = rank_row["rank"]
        prospect.update({k: rank_row[k] for k in ("position", "height_cm")})
        if rank_row["tie"]:
            prospect["tie"] = rank_row["tie"]
    if unmatched_rank:
        print("! RTP-ranked players not found in any squad:", [r["name"] for r in unmatched_rank])

    ct = [{"name": n, "rank": i + 1} for i, n in enumerate(TWOMEY_JULY)]
    ct_matched, ct_unmatched, _ = match_players(ct, prospects)
    for row, prospect in ct_matched:
        prospect["rank_ct"] = row["rank"]
    if ct_unmatched:
        print("! Twomey-ranked players not found in any squad:", [r["name"] for r in ct_unmatched])

    for prospect in prospects:
        if prospect["name"] in TIE_OVERRIDES:
            prospect["tie"] = TIE_OVERRIDES[prospect["name"]]
        # display rank: Twomey July where he ranks them, RTP for the tail
        prospect["rank"] = prospect.get("rank_ct") or (
            (25 + prospect["rank_rtp"]) if prospect.get("rank_rtp") else None)

    prospects.sort(key=lambda p: (p["rank"] is None, p["rank"] or 0, p["name"]))
    return prospects


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    pool = build_pool()
    payload = {
        "year": 2026,
        "sources": {
            "squads": SQUADS_URL,
            "rankings": TWOMEY_URL,
            "rankings_note": "Cal Twomey's Phantom Form Guide (July 2026) first, "
                             "Reading the Play Top 50 (Apr 2026) for the tail",
            "rankings_secondary": RANKINGS_URL,
        },
        "prospects": pool,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=1), encoding="utf-8", newline="\n")
    ranked_n = sum(1 for p in pool if p["rank"])
    print(f"wrote {OUT_PATH.name}: {len(pool)} prospects, {ranked_n} ranked")
    for p in pool[:5]:
        print(" ", p["rank"], p["name"], "-", p["state_team"], p["position"])
