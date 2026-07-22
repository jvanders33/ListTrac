"""Contract-event history from AFLRATINGS.

The AFL discloses no contract terms, and no site holds a structured contract
database. But AFLRATINGS publishes a dated post for every reported signing,
extension, trade request, delisting and retirement under one WordPress
category ("AFL TRADE NEWS", id 38647). That archive is effectively a
chronological log of player movement — the missing middle of a player's
timeline between draft and free agency.

This pulls the whole category via the WP REST API (same technique as the
Rookie Me Central prospect scraper), parses each post into a structured
event, and writes data/contracts.json. Events are matched to ListTrac
players at API request time by normalised name — nothing here writes the DB.

Coverage: the category runs from late 2021, so it captures recent deals, not
a player's entire career. Every event links back to its AFLRATINGS post, and
each post cites the breaking reporter — provenance is preserved end to end.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path

BASE = "https://aflratings.com.au/wp-json/wp/v2"
TRADE_NEWS_CAT = 38647
OUT = Path(__file__).resolve().parent.parent / "data" / "contracts.json"
MANUAL = Path(__file__).resolve().parent.parent / "data" / "contracts_manual.json"

# AFLRATINGS team category id -> our club abbreviation
TEAM_CAT = {
    38291: "ADE", 38292: "BRI", 38293: "CAR", 38294: "COL", 38295: "ESS",
    38296: "FRE", 38297: "GEE", 38298: "GCS", 38299: "GWS", 38300: "HAW",
    38301: "MEL", 38302: "NM", 38303: "PA", 38304: "RIC", 38305: "STK",
    38306: "SYD", 38307: "WCE", 38308: "WB",
}
WORD = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8}
ENTITIES = [("&amp;", "&"), ("&#8217;", "'"), ("&#8216;", "'"), ("&#8221;", '"'),
            ("&#8220;", '"'), ("&#8211;", "-"), ("&#8212;", "-"), ("&#8230;", "...")]


def _get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)


def _clean(html: str) -> str:
    t = re.sub("<[^>]+>", " ", html or "")
    for a, b in ENTITIES:
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t).strip()


def _norm(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())


def _end_year(body: str, signed_year: int) -> int | None:
    for pat in (r"until the end of (20\d\d)",
                r"through(?: to)?(?: the end of)? (20\d\d)",
                r"contracted (?:to|until|through)(?: the end of)? (20\d\d)",
                r"(?:tied|commit\w*|locked|signed|remain\w*|stay\w*|keeps? him)[^.]{0,60}?until(?: the end of)? (20\d\d)",
                r"until(?: the end of)? (20\d\d)", r"end of (20\d\d)"):
        m = re.search(pat, body, re.I)
        if m and int(m.group(1)) >= signed_year:
            return int(m.group(1))
    return None


def _length(body: str) -> int | None:
    m = re.search(r"\b(one|two|three|four|five|six|seven|eight|[1-8])[\-\s]?year", body, re.I)
    if not m:
        return None
    w = m.group(1).lower()
    return WORD.get(w) or int(w)


def _kind(body: str) -> str:
    b = body.lower()
    if "delist" in b:
        return "delist"
    if "retire" in b:
        return "retire"
    if "extension" in b or "re-sign" in b or "re-commit" in b or "recommit" in b:
        return "extension"
    if "traded" in b or "trade to" in b or "trade request" in b or "requested a trade" in b:
        return "trade"
    return "signing"


def _reporter(body: str) -> str | None:
    m = re.search(r"Source:\s*([A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+)?)", body)
    if not m:
        return None
    # trim a trailing club/section token the parser may absorb (…"Image", club name)
    r = re.sub(r"\s+(Image|Hawthorn|Carlton|Essendon|Geelong|Richmond|Sydney|Adelaide|"
               r"Melbourne|Fremantle|Collingwood|Brisbane|Giants|Suns|Eagles|Bulldogs|"
               r"Kangaroos|Power|Saints|Demons|Blues|Bombers|Cats|Tigers|Swans|Crows|"
               r"Dockers|Magpies|Lions|Hawks|Roos|Docker)$", "", m.group(1)).strip()
    return r or None


def parse_post(p: dict) -> dict | None:
    title = _clean(p["title"]["rendered"])
    name = re.sub(r"^(AFL Trade News|Contract Update|Trade News|AFL News)\s*[:\-]\s*",
                  "", title, flags=re.I).strip()
    if not name or len(name) > 40:
        return None
    body = _clean(p["content"]["rendered"])
    signed_year = int(p["date"][:4])
    end = _end_year(body, signed_year)
    length = _length(body)
    end_est = False
    if end is None and length and _kind(body) in ("signing", "extension"):
        end = signed_year + length          # e.g. 4-year deal signed 2022 -> end 2026
        end_est = True
    club = next((TEAM_CAT[c] for c in p.get("categories", []) if c in TEAM_CAT), None)
    return {
        "name": name,
        "norm": _norm(name),
        "date": p["date"][:10],
        "kind": _kind(body),
        "club": club,
        "length": length,
        "end_year": end,
        "end_estimated": end_est,
        "reporter": _reporter(body),
        "source_url": p.get("link"),
    }


def fetch_all() -> list[dict]:
    posts, page = [], 1
    while True:
        batch = _get(f"{BASE}/posts?categories={TRADE_NEWS_CAT}&per_page=100&page={page}"
                     "&_fields=date,title,link,categories,content")
        posts += batch
        if len(batch) < 100:
            break
        page += 1
        time.sleep(0.3)
    events = [e for e in (parse_post(p) for p in posts) if e]
    events.sort(key=lambda e: e["date"])
    return events


def load_manual() -> list[dict]:
    """Hand-curated events that fill gaps in the AFLRATINGS feed. Normalised to
    the same shape and flagged manual=true; current=true also corrects status."""
    if not MANUAL.exists():
        return []
    out = []
    for e in json.loads(MANUAL.read_text(encoding="utf-8")).get("events", []):
        out.append({
            "name": e["name"], "norm": _norm(e["name"]), "date": e["date"],
            "kind": e.get("kind", "signing"), "club": e.get("club"),
            "length": e.get("length"), "end_year": e.get("end_year"),
            "end_estimated": bool(e.get("end_estimated", False)),
            "reporter": e.get("reporter"), "source_url": e.get("source_url"),
            "manual": True, "current": bool(e.get("current", False)),
        })
    return out


def load_afl_signings() -> list[dict]:
    """Confirmed signings from the AFL's own content API (scraper/afl_signings.py)."""
    path = MANUAL.parent / "afl_signings.json"
    if not path.exists():
        return []
    out = []
    for e in json.loads(path.read_text(encoding="utf-8")).get("events", []):
        out.append({**e, "afl_official": True})
    return out


def _dedupe_key(e):
    # same signing from two feeds (same player + end year) collapses to one
    return (e["norm"], e["end_year"]) if e.get("end_year") else (e["norm"], e["date"])


def main():
    # priority low->high so higher-trust sources overwrite on the same key
    by_key = {}
    for e in fetch_all():            # AFLRATINGS aggregator (base)
        by_key[_dedupe_key(e)] = e
    for e in load_afl_signings():    # AFL.com.au official content API
        by_key[_dedupe_key(e)] = e
    for e in load_manual():          # hand-verified corrections win outright
        by_key[_dedupe_key(e)] = e
    events = sorted(by_key.values(), key=lambda e: e["date"])
    payload = {
        "source": "AFL.com.au + AFLRATINGS",
        "source_url": "https://www.afl.com.au/news",
        "attribution": "Contract & movement events from the AFL's own content API and AFLRATINGS' reporting, with hand-verified corrections; each event links to its source. The AFL does not disclose contract terms — no dollar figures are tracked.",
        "note": "Coverage runs from late 2021. end_estimated=true means the end year was inferred from the stated deal length, not quoted directly.",
        "count": len(events),
        "events": events,
    }
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    kinds = {}
    for e in events:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    print(f"wrote {len(events)} events -> {OUT}")
    print("kinds:", kinds)
    print("date range:", events[0]["date"], "->", events[-1]["date"])


if __name__ == "__main__":
    main()
