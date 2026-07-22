"""Build the full pool of potential draftees for each class, direct from the AFL.

The curated pools only held All-Australians / award winners. This pulls every
player in the elite pathway from the AFL Champion Data feed — the Coates Talent
League (CD_C011) and U18 National Championships (CD_C019) — and classifies each
by the draft they're eligible for using their date of birth (born 2008 → 2026
draft, 2009 → 2027, 2010 → 2028). The existing curated honour tags (rank,
All-Australian, medal) are merged back on so the standouts still stand out.

    python scraper/draft_pool.py     # rebuild prospects_2027.json / _2028.json

Coverage note: Coates is Victoria's talent league, so the pool skews Victorian;
interstate players enter via the national championships. SA/WA state-league
underage competitions aren't in this feed (they'd come from RMC) — a known gap.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

API = "https://api.afl.com.au"
H = {"User-Agent": "Mozilla/5.0 ListTrac (github.com/jvanders33/ListTrac)",
     "Origin": "https://www.afl.com.au", "Referer": "https://www.afl.com.au/"}
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# competitions to sweep (year fetched = 2026, the current pathway season)
COMPS = [("Coates Talent League", "011"), ("U18 Championships", "019")]
YEAR = 2026
CLASSES = {2009: 2027, 2010: 2028}  # birth year -> draft class we (re)build

# U18-champ state team -> our short state label
CHAMP_STATE = {
    "victoria metro": "Vic Metro", "victoria country": "Vic Country",
    "south australia": "South Australia", "western australia": "Western Australia",
    "allies": "Allies", "tasmania": "Tasmania",
}
# Coates (Victorian) club -> metro/country region
COATES_REGION = {
    "calder cannons": "Vic Metro", "eastern ranges": "Vic Metro", "northern knights": "Vic Metro",
    "oakleigh chargers": "Vic Metro", "sandringham dragons": "Vic Metro", "western jets": "Vic Metro",
    "bendigo pioneers": "Vic Country", "dandenong stingrays": "Vic Country", "geelong falcons": "Vic Country",
    "gippsland power": "Vic Country", "gwv rebels": "Vic Country", "greater western victoria rebels": "Vic Country",
    "murray bushrangers": "Vic Country", "bachar houli academy": "Vic Metro",
    # interstate academies + Tasmania now play in the Coates comp
    "tasmania devils": "Tasmania", "gws giants academy": "GWS Academy",
    "sydney swans academy": "Sydney Academy", "brisbane lions academy": "Brisbane Academy",
    "gold coast suns academy": "Gold Coast Academy", "northern territory academy": "Northern Territory",
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", (s or "").lower())


def _year(dob: str):
    m = re.search(r"(\d{4})", dob or "")
    return int(m.group(1)) if m else None


def mint():
    r = requests.post(f"{API}/cfs/afl/WMCTok", headers={**H, "Content-Length": "0"}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


def fetch(code, token):
    r = requests.get(f"{API}/statspro/playersStats/seasons/CD_S{YEAR}{code}",
                     headers={**H, "x-media-mis-token": token}, timeout=30)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    time.sleep(0.6)
    return r.json().get("players", [])


def build():
    token = mint()
    # cd_id -> aggregated player {name, draft_class, state, club, position, games}
    people: dict[str, dict] = {}
    for label, code in COMPS:
        players = fetch(code, token)
        print(f"  {label} {YEAR}: {len(players)} players")
        is_champ = code == "019"
        for p in players:
            cd = p.get("playerId")
            d = p["playerDetails"]
            by = _year(d.get("dateOfBirth"))
            if not cd or by not in CLASSES:
                continue
            games = int(p.get("gamesPlayed") or 0)
            team = (p.get("team") or {}).get("teamName", "")
            rec = people.setdefault(cd, {
                "name": f"{d.get('givenName', '')} {d.get('surname', '')}".strip(),
                "draft_class": CLASSES[by], "dob": d.get("dateOfBirth"),
                "position": d.get("position"), "state_team": None, "junior_club": None, "games": 0,
            })
            rec["games"] = max(rec["games"], games)
            rec["position"] = rec["position"] or d.get("position")
            if is_champ:
                rec["state_team"] = CHAMP_STATE.get((team or "").lower(), team)
            else:
                rec["junior_club"] = team
                if not rec["state_team"]:
                    rec["state_team"] = COATES_REGION.get((team or "").lower())
    return people


def rebuild_class(draft_class: int, people: dict):
    path = DATA_DIR / f"prospects_{draft_class}.json"
    curated = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"prospects": []}
    # index curated honours by normalised name
    honours = {_norm(p["name"]): p for p in curated.get("prospects", [])}

    by_name: dict[str, dict] = {}
    # start from AFL people of this class (played at least one game)
    for rec in people.values():
        if rec["draft_class"] != draft_class or rec["games"] < 1:
            continue
        key = _norm(rec["name"])
        entry = {"name": rec["name"], "state_team": rec["state_team"],
                 "position": rec["position"], "junior_club": rec["junior_club"],
                 "games": rec["games"], "source": "afl"}
        c = honours.get(key)
        if c:  # carry the curated honour tags
            for f in ("rank", "award", "tie"):
                if c.get(f) is not None:
                    entry[f] = c[f]
            entry["state_team"] = entry["state_team"] or c.get("state_team")
            entry["position"] = entry["position"] or c.get("position")
        by_name[key] = entry
    # add curated players the AFL feed didn't have (e.g. SA/WA state-league only)
    added_curated = 0
    for key, c in honours.items():
        if key not in by_name:
            by_name[key] = {**c, "source": "curated"}
            added_curated += 1

    prospects = sorted(by_name.values(),
                       key=lambda p: (p.get("rank") or 999, -(p.get("games") or 0), p["name"]))
    out = {
        "year": draft_class, "stage": "u18" if draft_class == 2026 else "pool",
        "note": (f"The {draft_class} potential-draftee pool — every talent-league and national-"
                 f"championship player eligible for the {draft_class} draft (classified by date of "
                 f"birth). Award winners and All-Australians are tagged; this is a wide pool this "
                 f"far out, not a ranking."),
        "sources": {**curated.get("sources", {}),
                    "afl": "https://www.afl.com.au/stats",
                    "rankings_note": "Pathway pool: AFL/Champion Data (Coates Talent League + U18 "
                                     "Championships) by DOB, plus curated All-Australian/award honours."},
        "prospects": prospects,
    }
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"  {draft_class}: {len(prospects)} prospects "
          f"({sum(1 for p in prospects if p.get('source') == 'afl')} from AFL, +{added_curated} curated-only)")


def main():
    print("sweeping AFL pathway comps…")
    people = build()
    for dc in sorted(set(CLASSES.values())):
        rebuild_class(dc, people)


if __name__ == "__main__":
    main()
