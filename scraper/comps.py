"""Similar-players engine — every serious football-stats site has one.

FBref's "most similar players", Basketball-Reference's similarity scores: given a
player, who plays most like them? We already compute, in scouting_2026.json, a
twelve-stat percentile profile for every player *relative to their own position
pool*. Because those percentiles are position-normalised, two players in the same
pool can be compared directly — the profile shape is a style fingerprint.

For each player we find the nearest fingerprints in their own position group. The
similarity score is 100 minus the mean absolute percentile gap across the twelve
stats: identical profiles score 100, a player who is 15 percentile points away on
average scores 85. Comparisons never cross position pools (a key forward's 90th
percentile for goals means nothing next to a midfielder's), so every comp is
genuinely like-for-like. Style only — calibre is left to the rating shown beside
each comp on the page.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCOUTING = ROOT / "data" / "scouting_2026.json"
OUT = ROOT / "data" / "comps_2026.json"

TOP_N = 8            # comps stored per player
MIN_SIM = 55         # drop weak matches — better to show fewer, closer comps


def main():
    data = json.loads(SCOUTING.read_text(encoding="utf-8"))
    order = data["order"]
    players = data["players"]

    # vector of the twelve percentiles, keyed by normalised name, grouped by pool
    groups: dict[str, list[tuple[str, dict]]] = {}
    vecs: dict[str, list[float]] = {}
    for key, p in players.items():
        vec = [p["stats"][s]["pct"] for s in order if s in p["stats"]]
        if len(vec) < len(order):     # need the full fingerprint to compare fairly
            continue
        vecs[key] = vec
        groups.setdefault(p["position"], []).append((key, p))

    def mad(a: list[float], b: list[float]) -> float:
        return sum(abs(x - y) for x, y in zip(a, b)) / len(a)

    out_players = {}
    for pos, members in groups.items():
        for key, p in members:
            va = vecs[key]
            sims = []
            for okey, op in members:
                if okey == key:
                    continue
                s = round(100 - mad(va, vecs[okey]), 1)
                if s >= MIN_SIM:
                    sims.append({"name": op["name"], "similarity": s})
            sims.sort(key=lambda x: -x["similarity"])
            out_players[key] = {
                "name": p["name"],
                "position_label": p["position_label"],
                "pool_size": p["pool_size"],
                "comps": sims[:TOP_N],
            }

    payload = {
        "year": data.get("year"),
        "attribution": "Similar-players engine: nearest twelve-stat percentile profiles within a player's own position pool. Style similarity only — from Champion Data / AFL per-game output. Calibre is shown separately via each comp's rating.",
        "method": {"stats": order, "score": "100 - mean absolute percentile gap",
                   "top_n": TOP_N, "min_similarity": MIN_SIM},
        "count": len(out_players),
        "players": out_players,
    }
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    withcomps = sum(1 for v in out_players.values() if v["comps"])
    print(f"wrote {OUT}: {len(out_players)} players, {withcomps} with >=1 comp")
    # a couple of spot checks
    for probe in ("marcus bontempelli", "max gawn", "nick daicos"):
        v = out_players.get(probe)
        if v and v["comps"]:
            top = ", ".join(f"{c['name']} ({c['similarity']})" for c in v["comps"][:3])
            print(f"  {v['name']} [{v['position_label']}] -> {top}")


if __name__ == "__main__":
    main()
