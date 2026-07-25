"""All-Australian teams — the real thing, from Wikipedia.

The All-Australian team is the AFL's team of the year: a 44-man squad each August,
cut to a final 22. It's the game's headline individual honour, and until now
ListTrac only had a rating-based proxy for it. This pulls the actual selections.

Each season has a "{year} All-Australian team" article on Wikipedia with a
`===Final team===` section (the 22) and an `===Initial squad===` section (the
44). We parse both per year and build a per-player honour roll — how many times,
and which years, each player was named — matched to ListTrac players by name.

    python scraper/all_australian.py     # -> data/all_australian.json
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parent.parent / "data" / "all_australian.json"
WIKI = "https://en.wikipedia.org/w/api.php"
H = {"User-Agent": "ListTrac (github.com/jvanders33/ListTrac)"}
YEARS = list(range(2015, 2026))          # ratings era


def _norm(name: str) -> str:
    import unicodedata
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]+", " ", name.lower()).strip()


def _clean(name: str) -> str:
    # drop Wikipedia disambiguators: "Mark Keane (footballer)" -> "Mark Keane"
    return re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()


def _section(wt: str, header: str) -> str | None:
    """Return the text of a === header === section, up to the next heading."""
    m = re.search(rf"==+\s*{re.escape(header)}\s*==+", wt)
    if not m:
        return None
    rest = wt[m.end():]
    nxt = re.search(r"\n==+[^=]", rest)
    return rest[:nxt.start()] if nxt else rest


def _players(section: str) -> list[str]:
    """Player names from a section: wikilinks first, else comma/newline split."""
    if not section:
        return []
    links = re.findall(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]", section)
    names = [ _clean(n) for n in links
              if " " in n and not n.startswith(("File:", "Category:", "Image:")) ]
    if len(names) >= 15:
        return names
    # fallback: strip refs/templates and split the prose list
    txt = re.sub(r"<ref.*?</ref>|<ref[^>]*/>|\{\{[^}]*\}\}|\[\[|\]\]", "", section, flags=re.S)
    txt = re.sub(r"\([^)]*\)", "", txt)
    parts = re.split(r",|\n|;", txt)
    out = []
    for p in parts:
        p = p.strip()
        if re.fullmatch(r"[A-Z][A-Za-z'\-]+ [A-Z][A-Za-z'\-. ]+", p):
            out.append(_clean(p))
    return out


def fetch_year(year: int) -> dict:
    r = requests.get(WIKI, params={"action": "parse", "page": f"{year} All-Australian team",
                                   "prop": "wikitext", "format": "json"}, headers=H, timeout=25)
    wt = r.json().get("parse", {}).get("wikitext", {}).get("*", "")
    team = _players(_section(wt, "Final team") or "")
    squad = _players(_section(wt, "Initial squad") or "")
    # de-dupe, keep order
    team = list(dict.fromkeys(team))
    squad = list(dict.fromkeys(squad)) or team
    return {"team": team, "squad": squad}


def main():
    by_year = {}
    players: dict[str, dict] = {}
    for y in YEARS:
        d = fetch_year(y)
        by_year[y] = d
        print(f"  {y}: final team {len(d['team'])}, squad {len(d['squad'])}")
        for nm in d["team"]:
            rec = players.setdefault(_norm(nm), {"name": nm, "team_years": [], "squad_years": []})
            rec["team_years"].append(y)
        for nm in d["squad"]:
            rec = players.setdefault(_norm(nm), {"name": nm, "team_years": [], "squad_years": []})
            if y not in rec["squad_years"]:
                rec["squad_years"].append(y)
        time.sleep(0.4)
    for rec in players.values():
        rec["team_count"] = len(rec["team_years"])
        rec["squad_count"] = len(rec["squad_years"])
    payload = {
        "years": YEARS,
        "attribution": "All-Australian teams from Wikipedia — the AFL's official team of the year (44-man squad, final 22) each season.",
        "source_url": "https://en.wikipedia.org/wiki/All-Australian_team",
        "count": len(players),
        "by_year": by_year,
        "players": players,
    }
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {OUT}: {len(players)} players honoured")
    mult = sorted((v for v in players.values() if v["team_count"] >= 4), key=lambda v: -v["team_count"])[:6]
    print("most-decorated (final team):", [(v["name"], v["team_count"]) for v in mult])


if __name__ == "__main__":
    main()
