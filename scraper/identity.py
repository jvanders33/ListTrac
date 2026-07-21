"""
Player + club identity reconciliation across sources.

Every source spells things its own way: AFL Tables uses "Last, First" and
"Brisbane Lions"; Draftguru uses "First Last", slug ids, and "brisbane";
Zerohanger uses URL slugs and calls GWS "GWS". This module is the one place
that knows how to line them up, so loaders can attach afl_tables_id /
footywire_id / draftguru_id to a single player row.

Matching strategy, in order:
  1. exact normalized full name (lowercase, accents stripped, punctuation
     collapsed, "Last, First" flipped)
  2. last name + first initial — catches Mitchell/Mitch, Lachlan/Lachie etc.
Ambiguous fallback matches (two candidates sharing last name + initial) are
left unmatched rather than guessed; DOB from Draftguru lists can break those
ties at load time.
"""
import re
import unicodedata

# canonical club name -> guernsey colours (primary, secondary) for UI chrome
CLUB_COLORS: dict[str, tuple[str, str]] = {
    "Adelaide":               ("#002B5C", "#FFD200"),
    "Brisbane":               ("#69163A", "#FDBE57"),
    "Carlton":                ("#031A29", "#E9EDF0"),
    "Collingwood":            ("#101010", "#E9EDF0"),
    "Essendon":               ("#CC2031", "#101010"),
    "Fremantle":              ("#2A1A54", "#E9EDF0"),
    "Geelong":                ("#1C3C63", "#E9EDF0"),
    "Gold Coast":             ("#D93E39", "#FFC42D"),
    "Greater Western Sydney": ("#F47920", "#3E3E3E"),
    "Hawthorn":               ("#4D2004", "#FBBF15"),
    "Melbourne":              ("#061A33", "#CC2031"),
    "North Melbourne":        ("#013B9F", "#E9EDF0"),
    "Port Adelaide":          ("#008AAB", "#101010"),
    "Richmond":               ("#1A1A1A", "#FFD200"),
    "St Kilda":               ("#C1272D", "#101010"),
    "Sydney":                 ("#ED171F", "#E9EDF0"),
    "Tasmania":               ("#1B4D3E", "#F0C244"),
    "West Coast":             ("#003087", "#F2A900"),
    "Western Bulldogs":       ("#014896", "#DC2830"),
}

# canonical club name -> how each source refers to it
CLUBS: dict[str, dict[str, str]] = {
    "Adelaide":               {"abbrev": "ADE", "afltables": "Adelaide",               "draftguru": "adelaide",               "zerohanger": "Adelaide", "footywire": "adelaide-crows"},
    "Brisbane":               {"abbrev": "BRI", "afltables": "Brisbane Lions",         "draftguru": "brisbane",               "zerohanger": "Brisbane", "footywire": "brisbane-lions"},
    "Carlton":                {"abbrev": "CAR", "afltables": "Carlton",                "draftguru": "carlton",                "zerohanger": "Carlton", "footywire": "carlton-blues"},
    "Collingwood":            {"abbrev": "COL", "afltables": "Collingwood",            "draftguru": "collingwood",            "zerohanger": "Collingwood", "footywire": "collingwood-magpies"},
    "Essendon":               {"abbrev": "ESS", "afltables": "Essendon",               "draftguru": "essendon",               "zerohanger": "Essendon", "footywire": "essendon-bombers"},
    "Fremantle":              {"abbrev": "FRE", "afltables": "Fremantle",              "draftguru": "fremantle",              "zerohanger": "Fremantle", "footywire": "fremantle-dockers"},
    "Geelong":                {"abbrev": "GEE", "afltables": "Geelong",                "draftguru": "geelong",                "zerohanger": "Geelong", "footywire": "geelong-cats"},
    "Gold Coast":             {"abbrev": "GCS", "afltables": "Gold Coast",             "draftguru": "gold-coast",             "zerohanger": "Gold Coast", "footywire": "gold-coast-suns"},
    "Greater Western Sydney": {"abbrev": "GWS", "afltables": "Greater Western Sydney", "draftguru": "greater-western-sydney", "zerohanger": "GWS", "footywire": "greater-western-sydney-giants"},
    "Hawthorn":               {"abbrev": "HAW", "afltables": "Hawthorn",               "draftguru": "hawthorn",               "zerohanger": "Hawthorn", "footywire": "hawthorn-hawks"},
    "Melbourne":              {"abbrev": "MEL", "afltables": "Melbourne",              "draftguru": "melbourne",              "zerohanger": "Melbourne", "footywire": "melbourne-demons"},
    "North Melbourne":        {"abbrev": "NM", "afltables": "North Melbourne",        "draftguru": "north-melbourne",        "zerohanger": "North Melbourne", "footywire": "kangaroos"},
    "Port Adelaide":          {"abbrev": "PA", "afltables": "Port Adelaide",          "draftguru": "port-adelaide",          "zerohanger": "Port Adelaide", "footywire": "port-adelaide-power"},
    "Richmond":               {"abbrev": "RIC", "afltables": "Richmond",               "draftguru": "richmond",               "zerohanger": "Richmond", "footywire": "richmond-tigers"},
    "St Kilda":               {"abbrev": "STK", "afltables": "St Kilda",               "draftguru": "st-kilda",               "zerohanger": "St Kilda", "footywire": "st-kilda-saints"},
    "Sydney":                 {"abbrev": "SYD", "afltables": "Sydney",                 "draftguru": "sydney",                 "zerohanger": "Sydney", "footywire": "sydney-swans"},
    "Tasmania":               {"abbrev": "TAS", "afltables": "Tasmania",               "draftguru": "tasmania",               "zerohanger": "Tasmania", "footywire": "tasmania-devils"},
    "West Coast":             {"abbrev": "WCE", "afltables": "West Coast",             "draftguru": "west-coast",             "zerohanger": "West Coast", "footywire": "west-coast-eagles"},
    "Western Bulldogs":       {"abbrev": "WB", "afltables": "Western Bulldogs",       "draftguru": "western-bulldogs",       "zerohanger": "Bulldogs", "footywire": "western-bulldogs"},
}


def canonical_club(name: str) -> str | None:
    """Map any source's club label back to the canonical name."""
    wanted = name.strip().lower()
    for canonical, variants in CLUBS.items():
        if wanted == canonical.lower() or wanted in (v.lower() for v in variants.values()):
            return canonical
    return None


def normalize_name(name: str) -> str:
    """'Rankine, Izak' / 'Izak Rankine' / 'izak-rankine' -> 'izak rankine'."""
    if "," in name:
        last, _, first = name.partition(",")
        name = f"{first} {last}"
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    # AFL Tables drops apostrophes entirely ("OBrien") — remove rather than
    # split so O'Brien normalizes identically from every source
    name = name.replace("'", "").replace("’", "")
    norm = re.sub(r"[^a-z]+", " ", name.lower()).strip()
    # generational suffixes appear inconsistently across sources ("Hansen Jr")
    return re.sub(r"\s+(jr|snr|sr|jnr)$", "", norm)


def _initial_key(norm: str) -> str:
    parts = norm.split()
    return f"{parts[0][0]} {parts[-1]}" if parts else ""


def match_players(source_a: list[dict], source_b: list[dict],
                  name_key: str = "name") -> tuple[list[tuple[dict, dict]], list[dict], list[dict]]:
    """Match two player lists (same club, same season) by name.

    Returns (matched_pairs, unmatched_a, unmatched_b).
    """
    b_by_name: dict[str, dict] = {}
    b_by_initial: dict[str, list[dict]] = {}
    for p in source_b:
        norm = normalize_name(p[name_key])
        b_by_name[norm] = p
        b_by_initial.setdefault(_initial_key(norm), []).append(p)

    matched: list[tuple[dict, dict]] = []
    unmatched_a: list[dict] = []
    taken: set[int] = set()

    for p in source_a:
        norm = normalize_name(p[name_key])
        hit = b_by_name.get(norm)
        if hit is None:
            # last name + first initial, but only if unambiguous
            candidates = [c for c in b_by_initial.get(_initial_key(norm), []) if id(c) not in taken]
            hit = candidates[0] if len(candidates) == 1 else None
        if hit is not None and id(hit) not in taken:
            matched.append((p, hit))
            taken.add(id(hit))
        else:
            unmatched_a.append(p)

    unmatched_b = [p for p in source_b if id(p) not in taken]
    return matched, unmatched_a, unmatched_b


if __name__ == "__main__":
    # Cross-check AFL Tables vs Draftguru current lists, club by club
    from afltables import fetch_season_lists
    from draftguru import fetch_club_list

    YEAR = 2026
    afl_lists = fetch_season_lists(YEAR)
    total_matched = total_a = total_b = 0
    for canonical, variants in CLUBS.items():
        afl_players = afl_lists.get(variants["afltables"])
        if not afl_players:
            continue  # club not in this season (e.g. Tasmania pre-2028)
        dg_players = fetch_club_list(YEAR, variants["draftguru"])
        matched, only_afl, only_dg = match_players(afl_players, dg_players)
        total_matched += len(matched)
        total_a += len(afl_players)
        total_b += len(dg_players)
        flag = "" if not (only_afl or only_dg) else f"  | only-afltables: {[p['name'] for p in only_afl]}  only-draftguru: {[p['name'] for p in only_dg]}"
        print(f"{canonical:24s} matched {len(matched):3d} / afltables {len(afl_players):3d} / draftguru {len(dg_players):3d}{flag}")

    print(f"\nTotal: {total_matched} matched, {total_a - total_matched} unmatched afltables, {total_b - total_matched} unmatched draftguru")
