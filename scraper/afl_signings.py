"""Official contract signings from the AFL's own news content API.

Cracks the AFL content platform that powers afl.com.au and every club site:

    GET https://aflapi.afl.com.au/content/afl/news/en?pageSize=50&pageIndex=N

Articles carry tags ("contracts", "free-agency", "Trade"), an AFL_PLAYER
reference identifying the subject, and — crucially — a clean one-sentence
`summary` ("West Coast ruck Bailey Williams has penned a six-year contract
extension until the end of 2032") that the noisy ad-laden body does not give.

We keep only CONFIRMED signings (penned / re-signed / extended / signed a deal),
never speculation ("set to", "linked", "eyes"), require an AFL_PLAYER reference,
and read the subject + term straight from the summary. Output merges into the
contract timeline via contracts.py — this is the official source that catches
signings the AFLRATINGS aggregator misses.

    python scraper/afl_signings.py     # -> data/afl_signings.json

Coverage: the feed surfaces recent news only (no deep history), so this keeps
the current window fresh; AFLRATINGS + manual overrides cover the rest.
"""
from __future__ import annotations

import json
import re
import sqlite3
import urllib.request
from pathlib import Path

BASE = "https://aflapi.afl.com.au/content/afl/news/en"
DB = Path(__file__).resolve().parent.parent / "data" / "listtrac.db"
OUT = Path(__file__).resolve().parent.parent / "data" / "afl_signings.json"

CONFIRM = re.compile(r"\b(re-?sign|re-?commit|resign|extend|penned|pens|inked|inks|"
                     r"signs? (?:a )?(?:new|long-term|multi-year|\w+-year)|"
                     r"commits?|lock(?:s|ed)? in|new (?:deal|contract))\b", re.I)
SPECULATION = re.compile(r"\b(set to|linked|eyes|on .*radar|could|may |might|rumou?r|"
                         r"considering|weigh|push(?:es|ing)? for|wants?|hope|talks?|call looms)\b", re.I)
WORD = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
# club names / nicknames -> abbrev, longest-first so "west coast" beats "coast" etc.
CLUB_NAMES = [
    ("greater western sydney", "GWS"), ("western bulldogs", "WB"), ("north melbourne", "NM"),
    ("port adelaide", "PA"), ("gold coast", "GCS"), ("west coast", "WCE"), ("st kilda", "STK"),
    ("adelaide", "ADE"), ("brisbane", "BRI"), ("carlton", "CAR"), ("collingwood", "COL"),
    ("essendon", "ESS"), ("fremantle", "FRE"), ("geelong", "GEE"), ("hawthorn", "HAW"),
    ("melbourne", "MEL"), ("richmond", "RIC"), ("sydney", "SYD"),
    ("giants", "GWS"), ("bulldogs", "WB"), ("kangaroos", "NM"), ("power", "PA"), ("suns", "GCS"),
    ("eagles", "WCE"), ("saints", "STK"), ("crows", "ADE"), ("lions", "BRI"), ("blues", "CAR"),
    ("magpies", "COL"), ("bombers", "ESS"), ("dockers", "FRE"), ("cats", "GEE"), ("hawks", "HAW"),
    ("demons", "MEL"), ("tigers", "RIC"), ("swans", "SYD"),
]


def club_in(text: str):
    t = (text or "").lower()
    for name, ab in CLUB_NAMES:
        if name in t:
            return ab
    return None


def _get(url: str):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 ListTrac", "Referer": "https://www.afl.com.au/"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def _norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]+", " ", s.lower()).strip()


def _clean_body(html: str) -> str:
    t = re.sub(r"<script[^>]*>.*?</script>", " ", html or "", flags=re.S)
    t = re.sub(r"window\.\w+[^;]*;", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _end_year(text: str, year: int):
    for pat in (r"until the end of (20\d\d)", r"through (?:to )?(?:the end of )?(20\d\d)",
                r"until (20\d\d)", r"tied to .*?until (20\d\d)", r"end of (20\d\d)"):
        m = re.search(pat, text, re.I)
        if m and int(m.group(1)) >= year:
            return int(m.group(1))
    return None


def _length(text: str):
    m = re.search(r"\b(one|two|three|four|five|six|seven|eight|[1-8])[- ]year", text, re.I)
    if not m:
        return None
    w = m.group(1).lower()
    return WORD.get(w) or int(w)


def fetch_articles(pages: int = 4) -> list[dict]:
    seen, arts = set(), []
    for pi in range(pages):
        for a in _get(f"{BASE}?pageSize=50&pageIndex={pi}").get("content", []):
            if a["id"] not in seen:
                seen.add(a["id"])
                arts.append(a)
    return arts


def article_url(a: dict) -> str:
    seg = a.get("titleUrlSegment")
    return f"https://www.afl.com.au/news/{a['id']}/{seg}" if seg else (a.get("canonicalUrl") or "")


def build() -> list[dict]:
    con = sqlite3.connect(DB)
    listed: dict[str, list] = {}
    for pid, f, l, club in con.execute(
            """SELECT p.id, p.first_name, p.last_name, c.abbreviation
               FROM player p LEFT JOIN club c ON c.id = p.current_club_id
               WHERE p.status = 'listed'"""):
        listed.setdefault(_norm(f"{f} {l}"), []).append({"first": f, "last": l, "club": club})

    events = []
    for a in fetch_articles():
        refs = a.get("references") or []
        if not any(r.get("type") == "AFL_PLAYER" for r in refs):
            continue
        summary = a.get("summary") or ""
        title = a.get("title") or ""
        head = f"{title}. {summary}"
        if not CONFIRM.search(head) or SPECULATION.search(title):
            continue
        # subject = the listed player named in the (single-subject) summary;
        # disambiguate same-name players by the club named in the summary
        nsum = _norm(summary) or _norm(title)
        club = club_in(head)
        info = None
        for key, cands in listed.items():
            if key and key in nsum:
                info = next((c for c in cands if c["club"] == club), None) or (cands[0] if len(cands) == 1 else None)
                if info:
                    break
        if not info:
            continue
        year = int((a.get("date") or "2026")[:4])
        # read the lead of the article body too, where the end year is usually stated
        detail = f"{head} {_clean_body(a.get('body') or '')[:1500]}"
        end = _end_year(detail, year)
        length = _length(head) or _length(detail)
        estimated = end is None and length is not None
        if estimated:
            end = year + length
        info = {**info, "club": club or info["club"]}
        events.append({
            "name": f"{info['first']} {info['last']}",
            "norm": _norm(f"{info['first']} {info['last']}"),
            "date": (a.get("date") or "")[:10],
            "kind": "extension" if re.search(r"extend|re-?sign|re-?commit|new deal", head, re.I) else "signing",
            "club": info["club"], "length": length, "end_year": end,
            "end_estimated": estimated,
            "current": True, "reporter": a.get("author") or "AFL.com.au",
            "source_url": article_url(a),
        })
    # de-dupe by (player, date), newest kept
    dedup = {}
    for e in sorted(events, key=lambda e: e["date"]):
        dedup[(e["norm"], e["date"])] = e
    return sorted(dedup.values(), key=lambda e: e["date"], reverse=True)


def main():
    events = build()
    OUT.write_text(json.dumps({
        "source": "AFL.com.au (AFL content API)",
        "source_url": "https://www.afl.com.au/news",
        "note": "Confirmed contract signings extracted from the AFL news content API; recent window only.",
        "count": len(events), "events": events,
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(events)} confirmed signings -> {OUT}")
    for e in events:
        print(f"  {e['date']} {e['name']} ({e['club']}) -> end {e['end_year']} [{e['length']}yr] · {e['reporter']}")


if __name__ == "__main__":
    main()
