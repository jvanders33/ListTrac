"""Empirical aging curves from twelve seasons of AFL Player Ratings.

Every sport that models player value eventually builds an aging curve — the
population-level answer to "how does output rise and fall with age at each
position?" FanGraphs does it for baseball, PFF for the NFL. AFL sites don't,
yet the raw material is sitting in ratings_history.json: a per-season Official
Player Rating for ~2,000 players back to 2015.

This joins each player's rating timeline to their date of birth (from the
Draftguru-sourced player table) to get an (age, rating) point for every
player-season. Two things are computed from that:

  * population — mean and percentile rating of everyone *in the league* at each
    age. Descriptive only: it is survivorship-biased (a 33-year-old still
    playing is, by definition, good), so it must NOT be read as an aging curve.

  * aging — the delta / matched-pairs curve, which IS the aging curve. For each
    player who played two consecutive seasons we take the rating change and
    attribute it to the age transition, then average those deltas by age and
    chain them into a trajectory. Because every player is compared only to
    themselves, survivorship cancels out and the true rise-peak-decline shows.
    A normalised value_index (trajectory / peak) is the empirical analogue of
    the Trade Value age multiplier, computed overall and per position group
    (MID / FWD / DEF / RUCK).

Nothing here is fabricated: ages come from real DOBs, ratings from Champion
Data, and thin buckets are dropped.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "listtrac.db"
HIST = ROOT / "data" / "ratings_history.json"
RATINGS = ROOT / "data" / "ratings_2026.json"
OUT = ROOT / "data" / "aging_curves.json"

MIN_BUCKET = 10         # drop age buckets thinner than this (noise)
TRIM = 0.10             # trim this fraction off each tail before averaging deltas
LOWCONF_N = 20          # buckets below this are flagged lower-confidence
AGE_LO, AGE_HI = 17, 37

POS_GROUP = {
    "MIDFIELDER": "MID", "MIDFIELDER_FORWARD": "MID",
    "KEY_FORWARD": "FWD", "MEDIUM_FORWARD": "FWD", "GENERAL_FORWARD": "FWD",
    "KEY_DEFENDER": "DEF", "MEDIUM_DEFENDER": "DEF", "GENERAL_DEFENDER": "DEF",
    "RUCK": "RUCK",
}
GROUP_LABEL = {"ALL": "All positions", "MID": "Midfielders",
               "FWD": "Forwards", "DEF": "Defenders", "RUCK": "Rucks"}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", (s or "").lower())


def _dob_map() -> dict[str, tuple[int, int, int]]:
    c = sqlite3.connect(DB)
    out = {}
    for fn, ln, dob in c.execute("select first_name,last_name,dob from player where dob is not null"):
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", dob or "")
        if m:
            out[_norm((fn or "") + (ln or ""))] = (int(m[1]), int(m[2]), int(m[3]))
    c.close()
    return out


def _pos_map() -> dict[str, str]:
    """cd_id -> position group, from current-season Champion Data positions."""
    out = {}
    for r in json.loads(RATINGS.read_text(encoding="utf-8"))["ratings"]:
        g = POS_GROUP.get(r.get("position", ""))
        if g:
            out[r["cd_id"]] = g
    return out


def _age_at(year: int, dob: tuple[int, int, int]) -> int:
    # age at 30 June of the season (mid-year), the fair midpoint of a Mar-Sep season
    by, bm, bd = dob
    age = year - by
    if (bm, bd) > (6, 30):
        age -= 1
    return age


def _pct(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    i = min(len(sorted_vals) - 1, int(round(q * (len(sorted_vals) - 1))))
    return sorted_vals[i]


def _population(points: dict[int, list[float]]) -> list[dict]:
    """Descriptive: rating distribution of players in the league at each age.
    Survivorship-biased — not an aging curve, but shows who is still out there."""
    rows = []
    for age in range(AGE_LO, AGE_HI + 1):
        vals = sorted(points.get(age, []))
        if len(vals) < MIN_BUCKET:
            continue
        rows.append({
            "age": age, "n": len(vals),
            "mean": round(sum(vals) / len(vals), 1),
            "p25": round(_pct(vals, 0.25), 1), "p50": round(_pct(vals, 0.50), 1),
            "p75": round(_pct(vals, 0.75), 1),
        })
    return rows


FIRST_Y, LAST_Y = 2015, 2026


def _recency_w(year: int) -> float:
    """Recent seasons weigh more, so the curve reflects today's game rather than
    a decade ago. Peer-reviewed work (Journal of Science & Medicine in Sport,
    2026) shows AFL peak age has come forward 2-3 years since 2012, so an equally
    weighted twelve-year pool anchors the peak too old."""
    return 0.35 + 0.65 * (year - FIRST_Y) / (LAST_Y - FIRST_Y)


def _wtrimmed_mean(pairs: list[tuple], weighted: bool = True, trim: float = TRIM) -> float:
    """Weighted mean after dropping the top and bottom `trim` fraction by delta —
    robust to outlier seasons (a Gawn or a Bontempelli), and recency-weighted so
    the current game dominates. pairs = [(delta, year), ...]."""
    v = sorted(pairs, key=lambda p: p[0])
    k = int(len(v) * trim)
    core = v[k:len(v) - k] if len(v) - 2 * k >= 3 else v
    if weighted:
        num = sum(d * _recency_w(y) for d, y in core)
        den = sum(_recency_w(y) for _, y in core) or 1.0
        return num / den
    return sum(d for d, _ in core) / len(core)


def _aging(deltas: dict[int, list[tuple]], weighted: bool = True) -> list[dict]:
    """The delta / matched-pairs aging curve. deltas[a] = list of (one-season
    rating change, season) for players making the age a -> a+1 transition. Trim
    outliers, recency-weighted-average by age, chain, normalise so peak = 1.0."""
    ages = [a for a in range(AGE_LO, AGE_HI) if len(deltas.get(a, [])) >= MIN_BUCKET]
    if not ages:
        return []
    lo, hi = min(ages), max(ages) + 1
    mean_delta = {a: (_wtrimmed_mean(deltas[a], weighted) if len(deltas.get(a, [])) >= MIN_BUCKET else 0.0)
                  for a in range(lo, hi)}
    # chain: trajectory[lo] = 0, each step adds that age's mean delta
    traj, cum = {}, 0.0
    traj[lo] = 0.0
    for a in range(lo, hi):
        cum += mean_delta.get(a, 0.0)
        traj[a + 1] = round(cum, 1)
    peak = max(traj.values())
    lo_v = min(traj.values())
    span = (peak - lo_v) or 1.0
    rows = []
    for a in range(lo, hi + 1):
        n = len(deltas.get(a, [])) if a < hi else len(deltas.get(a - 1, []))
        rows.append({
            "age": a, "trajectory": traj[a],
            # value_index scaled 0..1 across the observed span, 1.0 at peak age
            "value_index": round((traj[a] - lo_v) / span, 3),
            "mean_delta": round(mean_delta.get(a, 0.0), 1) if a < hi else None,
            "n": n, "low_conf": n < LOWCONF_N,
        })
    return rows


def main():
    dob = _dob_map()
    pos = _pos_map()
    hist = json.loads(HIST.read_text(encoding="utf-8"))
    tl = hist["timelines"]

    all_pts: dict[int, list[float]] = {}
    grp_pts: dict[str, dict[int, list[float]]] = {g: {} for g in ("MID", "FWD", "DEF", "RUCK")}
    all_delta: dict[int, list[float]] = {}
    grp_delta: dict[str, dict[int, list[float]]] = {g: {} for g in ("MID", "FWD", "DEF", "RUCK")}
    matched_players = 0

    for cd, t in tl.items():
        d = dob.get(_norm(t["name"]))
        if not d:
            continue
        matched_players += 1
        g = pos.get(cd)
        by_year = {}
        for s in t["seasons"]:
            age = _age_at(s["year"], d)
            rating = s.get("rating")
            if rating is None or not (AGE_LO <= age <= AGE_HI):
                continue
            by_year[s["year"]] = (age, rating)
            all_pts.setdefault(age, []).append(rating)
            if g:
                grp_pts[g].setdefault(age, []).append(rating)
        # matched consecutive-season pairs -> (delta, season) keyed by starting age
        for yr, (age, rating) in by_year.items():
            nxt = by_year.get(yr + 1)
            if nxt:
                dlt = nxt[1] - rating
                all_delta.setdefault(age, []).append((dlt, yr))
                if g:
                    grp_delta[g].setdefault(age, []).append((dlt, yr))

    population = {"ALL": _population(all_pts)}
    aging = {"ALL": _aging(all_delta, weighted=True)}
    for g in ("MID", "FWD", "DEF", "RUCK"):
        population[g] = _population(grp_pts[g])
        aging[g] = _aging(grp_delta[g], weighted=True)

    def peak_age(curve):
        return max(curve, key=lambda r: r["value_index"])["age"] if curve else None

    # peak-age shift: the all-time (equally weighted) peak vs the recency-weighted
    # peak, so we can show the article's "peak age is coming forward" with our data
    grp_delta_all = {"ALL": all_delta, **grp_delta}
    peak_shift = {}
    for g in ("ALL", "MID", "FWD", "DEF", "RUCK"):
        alltime = peak_age(_aging(grp_delta_all[g], weighted=False))
        current = peak_age(aging[g])
        peak_shift[g] = {"all_time": alltime, "current": current,
                         "shift": (alltime - current) if (alltime and current) else None}

    # empirical value multipliers off the delta-method ALL curve (Trade Value tie-in)
    def bracket(lo, hi):
        xs = [r["value_index"] for r in aging["ALL"] if lo <= r["age"] <= hi]
        return round(sum(xs) / len(xs), 3) if xs else None

    peaks = {g: peak_age(aging[g]) for g in ("ALL", "MID", "FWD", "DEF", "RUCK")}
    empirical_factors = {
        "21-23": bracket(21, 23), "24-27": bracket(24, 27),
        "28-29": bracket(28, 29), "30-31": bracket(30, 31), "32+": bracket(32, 40),
    }

    payload = {
        "source": "Official AFL Player Ratings (Champion Data), 2015-2026",
        "source_url": "https://www.afl.com.au/afl-player-ratings",
        "attribution": "Aging curves derived from twelve seasons of Official AFL Player Ratings joined to player dates of birth. Age is taken at 30 June of each season. The aging curve uses the delta / matched-pairs method (each player compared only to themselves across consecutive seasons) so survivorship bias cancels out, and is recency-weighted so it reflects the current game. The population view is descriptive only and is survivorship-biased.",
        "citation": "Recency weighting follows the finding of Journal of Science & Medicine in Sport (2026) that AFL peak-performance age has come forward 2-3 years and converged across positions since 2012.",
        "method": {
            "min_bucket": MIN_BUCKET, "age_range": [AGE_LO, AGE_HI],
            "players_matched": matched_players,
            "aging": "delta/matched-pairs: recency-weighted mean one-season rating change by age, chained into a trajectory and normalised 0..1 (1.0 = peak age)",
            "population": "mean & quartile rating of players active at each age (survivorship-biased, descriptive)",
            "recency_weight": "season weight 0.35 (2015) -> 1.0 (2026), linear",
        },
        "labels": GROUP_LABEL,
        "peak_age": peaks,
        "peak_shift": peak_shift,
        "empirical_age_factors": empirical_factors,
        "aging": aging,
        "population": population,
    }
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT}")
    print("players matched:", matched_players)
    print("peak age by group:", peaks)
    for g in ("ALL", "MID", "FWD", "DEF", "RUCK"):
        print(f"  {g:4} aging buckets:", len(aging[g]), "| population buckets:", len(population[g]))
    print("empirical age factors (delta method):", empirical_factors)


if __name__ == "__main__":
    main()
