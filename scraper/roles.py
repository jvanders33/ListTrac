"""Player role archetypes — the roles the official position labels don't name.

Champion Data tags seven positions (key/medium forward, key/medium defender,
midfielder, midfielder-forward, ruck). Football has far more *roles*: the
pressure small forward, the contested inside mid, the running half-back, the
intercept key defender. The stats that separate them are already in hand — this
layer reads the fingerprint and names the role.

Method: exemplar-centroid classification in league-standardised stat space.
Each role is anchored by a handful of stereotypical players; we average their
z-scored profiles into a role centroid, then assign every player to their nearest
centroid. Crucially this runs on *raw, league-wide* per-game output — not the
position-relative percentiles — so a player is judged by how they actually play,
not by the pool the AFL filed them under. That's what lets Kysaiah Pickett read
as a small forward even though Champion Data lists him as a midfielder.

Role comps (nearest same-role players) are computed in the same z-space, so they
too cross official position pools. Everything here is ListTrac's own read on top
of official Champion Data output — an interpretation, clearly labelled, never an
official field. No dollars, no fabrication.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCOUTING = ROOT / "data" / "scouting_2026.json"
MANUAL = ROOT / "data" / "roles_manual.json"
OUT = ROOT / "data" / "roles_2026.json"

TOP_N = 8

# The twelve per-game stats, in a fixed order for the vector.
STATS = ["disposals", "contestedPossessions", "totalClearances", "metresGained",
         "inside50s", "scoreInvolvements", "goals", "marks", "intercepts",
         "rebound50s", "tackles", "pressureActs"]

# role key -> (label, macro group, stereotypical exemplars). Exemplars are
# well-known role archetypes; the centroid is their mean profile, so a couple of
# imperfect picks wash out. Names are matched loosely (letters only).
ROLES = {
    "ruck":         ("Ruck", "RUCK",
                     ["max gawn", "tim english", "tristan xerri", "rowan marshall"]),
    "key_fwd":      ("Marking key forward", "FWD",
                     ["charlie curnow", "jeremy cameron", "ben king", "aaron naughton"]),
    "small_fwd":    ("Pressure small forward", "FWD",
                     ["kysaiah pickett", "toby bedford", "charlie cameron", "cody weightman"]),
    "gen_fwd":      ("General forward", "FWD",
                     ["jake stringer", "jamie elliott", "mitch georgiades", "dylan moore"]),
    "inside_mid":   ("Contested inside midfielder", "MID",
                     ["tom liberatore", "matt rowell", "jack steele", "tim taranto"]),
    "outside_mid":  ("Outside / run midfielder", "MID",
                     ["errol gulden", "hugh mccluggage", "karl amon", "caleb daniel"]),
    "gun_mid":      ("Elite two-way midfielder", "MID",
                     ["marcus bontempelli", "nick daicos", "zach merrett", "caleb serong"]),
    "intercept_def": ("Intercept key defender", "DEF",
                      ["harris andrews", "sam taylor", "jacob weitering", "jake lever"]),
    "lockdown_def": ("Lockdown key defender", "DEF",
                     ["tom barrass", "sam collins", "sam de koning"]),
    "rebound_def":  ("Rebounding half-back", "DEF",
                     ["bailey dale", "jordan ridley", "jayden short", "nick vlastuin"]),
}


# official Champion Data position -> macro group; sub-roles are assigned only
# among their own group, so the reliable fwd/mid/def/ruck line is respected and
# forwards never get classified as defenders
POS_TO_GROUP = {
    "MIDFIELDER": "MID", "MIDFIELDER_FORWARD": "MID",
    "KEY_FORWARD": "FWD", "MEDIUM_FORWARD": "FWD", "GENERAL_FORWARD": "FWD",
    "KEY_DEFENDER": "DEF", "MEDIUM_DEFENDER": "DEF", "GENERAL_DEFENDER": "DEF",
    "RUCK": "RUCK",
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z]", " ", (s or "").lower()).strip()


def main():
    data = json.loads(SCOUTING.read_text(encoding="utf-8"))
    players = data["players"]

    # raw per-game vectors
    vec = {}
    for key, p in players.items():
        st = p["stats"]
        if all(s in st for s in STATS):
            vec[key] = [float(st[s]["avg"]) for s in STATS]

    # league-wide standardisation (z-score per stat)
    n = len(vec)
    mean = [sum(v[i] for v in vec.values()) / n for i in range(len(STATS))]
    std = []
    for i in range(len(STATS)):
        var = sum((v[i] - mean[i]) ** 2 for v in vec.values()) / n
        std.append(math.sqrt(var) or 1.0)
    z = {k: [(v[i] - mean[i]) / std[i] for i in range(len(STATS))] for k, v in vec.items()}

    # role centroids from exemplars (z-space)
    centroids, used = {}, {}
    for rk, (label, group, exemplars) in ROLES.items():
        found = [z[_norm(e)] for e in exemplars if _norm(e) in z]
        used[rk] = [e for e in exemplars if _norm(e) in z]
        if len(found) < 2:
            print(f"  ! role {rk}: only {len(found)} exemplars found — skipping")
            continue
        centroids[rk] = [sum(f[i] for f in found) / len(found) for i in range(len(STATS))]

    def dist(a, b):
        return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(len(STATS))))

    def cosine(a, b):
        # direction of the fingerprint, not its magnitude — so a player's ROLE
        # is judged by play-style shape, not by how prolific they are
        na = math.sqrt(sum(x * x for x in a)) or 1.0
        nb = math.sqrt(sum(x * x for x in b)) or 1.0
        return sum(a[i] * b[i] for i in range(len(STATS))) / (na * nb)

    # sub-roles available within each macro group
    group_roles = {}
    for rk, (label, group, _ex) in ROLES.items():
        if rk in centroids:
            group_roles.setdefault(group, []).append(rk)

    # Primary role: best-aligned sub-role within the player's official group, so
    # the reliable fwd/mid/def/ruck line is respected. Secondary trait: the
    # strongest resemblance to a role in a DIFFERENT group, surfaced only when
    # it's genuinely close — that's what captures hybrids like a midfielder who
    # also plays as a small forward.
    SECONDARY_MIN = 0.62      # the cross-line role must align at least this well
    SECONDARY_GAP = 0.14      # ...and be within this cosine of the primary
    assign = {}
    for k, zv in z.items():
        group = POS_TO_GROUP.get(players[k].get("position", ""), None)
        cand = group_roles.get(group)
        if not cand:
            continue
        allcos = {rk: cosine(zv, c) for rk, c in centroids.items()}
        cs = sorted(((allcos[rk], rk) for rk in cand), reverse=True)
        c1, rk1 = cs[0]
        c2 = cs[1][0] if len(cs) > 1 else c1 - 1
        margin = c1 - c2
        conf = "high" if len(cand) == 1 or margin >= 0.10 else "medium" if margin >= 0.04 else "low"
        # secondary: best role outside this group, if strong and close to primary
        others = sorted(((allcos[rk], rk) for rk in centroids
                         if ROLES[rk][1] != group), reverse=True)
        sec = None
        if others and others[0][0] >= SECONDARY_MIN and (c1 - others[0][0]) <= SECONDARY_GAP:
            sec = others[0][1]
        assign[k] = {"role": rk1, "align": round(c1, 3), "conf": conf, "secondary": sec}

    # hand-pinned overrides win over the classifier (football knowledge the raw
    # output misses). Applied before comps so role comps follow the pinned role.
    overrides = {}
    if MANUAL.exists():
        for o in json.loads(MANUAL.read_text(encoding="utf-8")).get("overrides", []):
            k = _norm(o["name"])
            if k not in assign:
                print(f"  ! override for '{o['name']}' — not in this season's data, skipped")
                continue
            if o.get("role") in centroids:
                assign[k]["role"] = o["role"]
                assign[k]["conf"] = "high"
            if "secondary_role" in o:
                sr = o["secondary_role"]
                assign[k]["secondary"] = sr if sr in centroids else None
            assign[k]["manual"] = True
            assign[k]["manual_note"] = o.get("note")
            overrides[k] = o["name"]

    # role comps: nearest same-role players in z-space
    by_role: dict[str, list[str]] = {}
    for k, a in assign.items():
        by_role.setdefault(a["role"], []).append(k)

    out = {}
    for k, a in assign.items():
        rk = a["role"]
        mates = []
        for ok in by_role[rk]:
            if ok == k:
                continue
            d = dist(z[k], z[ok])
            mates.append((d, ok))
        mates.sort()
        # map distance -> 0..100 similarity (tuned: ~0 dist = 99, ~4 dist = 60)
        comps = [{"name": players[ok]["name"],
                  "similarity": max(40, round(100 - d * 9, 1))}
                 for d, ok in mates[:TOP_N]]
        label, group, _ = ROLES[rk]
        sec = a.get("secondary")
        out[k] = {
            "name": players[k]["name"], "role": rk, "role_label": label,
            "role_group": group, "confidence": a["conf"],
            "secondary_role": sec, "secondary_label": ROLES[sec][0] if sec else None,
            "official_position": players[k]["position_label"],
            "manual": bool(a.get("manual")), "manual_note": a.get("manual_note"),
            "comps": comps,
        }

    role_defs = {rk: {"label": ROLES[rk][0], "group": ROLES[rk][1],
                      "exemplars": used.get(rk, []),
                      "count": len(by_role.get(rk, []))}
                 for rk in centroids}
    payload = {
        "year": data.get("year"),
        "attribution": "Player role archetypes are ListTrac's own read on top of official Champion Data per-game output — an exemplar-centroid classification in league-standardised stat space. Interpretation, not an official position field.",
        "stats": STATS,
        "roles": role_defs,
        "count": len(out),
        "players": out,
    }
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT}: {len(out)} players")
    print("role distribution:")
    for rk in ROLES:
        c = len(by_role.get(rk, []))
        print(f"  {ROLES[rk][0]:30} {c:3}   exemplars used: {', '.join(used.get(rk, [])) or 'NONE'}")
    print("spot checks:")
    for probe in ("kysaiah pickett", "max gawn", "nick daicos", "toby greene",
                  "errol gulden", "sam taylor", "bailey dale", "charlie curnow",
                  "isaac heeney", "bailey smith"):
        v = out.get(probe)
        if v:
            sec = f" + {v['secondary_label']}" if v['secondary_label'] else ""
            print(f"  {v['name']:22} -> {v['role_label']:30}{sec:26} ({v['confidence']}, official: {v['official_position']})")
    sec_count = sum(1 for v in out.values() if v['secondary_label'])
    print(f"players with a secondary trait: {sec_count}")


if __name__ == "__main__":
    main()
