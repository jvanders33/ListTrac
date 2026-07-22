"""
PlayHQ GraphQL client — direct-source ingestion for any AFL competition hosted
on PlayHQ (state leagues, community footy, talent pathways).

PlayHQ runs the AFL's community/state footy platform. Its public GraphQL API
(https://api.playhq.com/graphql) needs no key — only a `tenant: afl` header —
and exposes the full hierarchy down to per-player game statistics:

    organisation (by code) → seasons → grades → rounds → games → per-player stats

Traversal (all confirmed against the live schema):
    discoverOrganisation(code)            -> org + tenant
    discoverSeason(seasonID)  { grades }  -> the grades in a season
    discoverGrade(gradeID)    { rounds }  -> the rounds in a grade
    discoverFixtureByRound(roundID){games}-> the games in a round
    discoverGame(gameID){ statistics {    -> per-player stat lines
        home/away { players { playerNumber player{ profile{firstName lastName} }
                              statistics { count type{value} } } } } }

NOTE ON SCOPE: this is the reusable client. Point it at the right org/season.
The public "sanfl-juniors" org is community footy (U7–U15.5), NOT the draft
talent pathway (SANFL League/U18) — that competition must be located separately
(it may not be on PlayHQ). The prospects' primary comps (Coates Talent League,
national championships) are Champion Data, already ingested via Rookie Me
Central. Use this where a draft-relevant competition IS on PlayHQ.
"""
import json
import time
import urllib.request

ENDPOINT = "https://api.playhq.com/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "tenant": "afl",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ListTrac (github.com/jvanders33/ListTrac)",
    "Origin": "https://www.playhq.com",
    "Referer": "https://www.playhq.com/",
}


def query(gql: str, variables: dict | None = None) -> dict:
    body = json.dumps({"query": gql, "variables": variables or {}}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        payload = json.loads(r.read().decode())
    if payload.get("errors"):
        raise RuntimeError(payload["errors"][0]["message"])
    return payload["data"]


def season_grades(season_id: str) -> list[dict]:
    d = query("query($s:String!){ discoverSeason(seasonID:$s){ id name grades { id name } } }",
              {"s": season_id})
    return d["discoverSeason"]["grades"]


def grade_rounds(grade_id: str) -> list[dict]:
    d = query("query($g:ID!){ discoverGrade(gradeID:$g){ rounds { id name } } }", {"g": grade_id})
    return d["discoverGrade"]["rounds"]


def round_games(round_id: str) -> list[dict]:
    d = query("query($r:ID!){ discoverFixtureByRound(roundID:$r){ games { id status { value } } } }",
              {"r": round_id})
    return d["discoverFixtureByRound"]["games"]


_GAME_STATS = """
query($id:ID!){ discoverGame(gameID:$id){
  id status { value }
  statistics {
    home { players { playerNumber
      player { ... on DiscoverParticipant { profile { firstName lastName } } }
      statistics { count type { value } } } }
    away { players { playerNumber
      player { ... on DiscoverParticipant { profile { firstName lastName } } }
      statistics { count type { value } } } } } } }
"""


def game_player_stats(game_id: str) -> list[dict]:
    """Every player's stat line for a game: name + {statType: count}."""
    d = query(_GAME_STATS, {"id": game_id})
    game = d["discoverGame"]
    out = []
    for side in ("home", "away"):
        for p in (game.get("statistics", {}).get(side) or {}).get("players", []) or []:
            prof = (p.get("player") or {}).get("profile") or {}
            name = f"{prof.get('firstName', '')} {prof.get('lastName', '')}".strip()
            if not name:
                continue
            stats = {s["type"]["value"]: s["count"] for s in (p.get("statistics") or [])}
            out.append({"name": name, "number": p.get("playerNumber"), "side": side, "stats": stats})
    return out


def aggregate_grade(grade_id: str, max_rounds: int | None = None) -> dict:
    """Walk a grade's completed games and sum each player's stats into a
    season line. Returns {player_name: {games, totals{stat:sum}}}."""
    tally: dict[str, dict] = {}
    rounds = grade_rounds(grade_id)
    for rnd in (rounds[:max_rounds] if max_rounds else rounds):
        for game in round_games(rnd["id"]):
            if (game.get("status") or {}).get("value") == "UPCOMING":
                continue
            try:
                players = game_player_stats(game["id"])
            except RuntimeError:
                continue
            time.sleep(0.3)  # politeness
            for pl in players:
                rec = tally.setdefault(pl["name"], {"games": 0, "totals": {}})
                rec["games"] += 1
                for k, v in pl["stats"].items():
                    rec["totals"][k] = rec["totals"].get(k, 0) + (v or 0)
    return tally


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    # smoke test against the public SANFL Juniors org's 2026 season
    SEASON = "4fe4b7a3"
    grades = season_grades(SEASON)
    print(f"season {SEASON}: {len(grades)} grades; sampling one older grade")
    grade = next((g for g in grades if "Under 14 Division 1" in g["name"]), grades[0])
    print(f"  grade: {grade['name']} ({grade['id']})")
    agg = aggregate_grade(grade["id"], max_rounds=2)
    print(f"  {len(agg)} players with stats over 2 rounds")
    for name, rec in list(agg.items())[:5]:
        top = sorted(rec["totals"].items(), key=lambda x: -x[1])[:5]
        print(f"    {name}: {rec['games']}gm, {dict(top)}")
