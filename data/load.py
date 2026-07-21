"""
DB loader — builds data/listtrac.db from the scrapers, via identity.py.

    python data/load.py --start 2015 --end 2026

Load order:
  1. clubs             from identity.CLUBS
  2. players           current-season Draftguru lists (full squads incl.
                       undebuted; DOB + height + jumper), keyed by draftguru_id
  3. contract_status   Zerohanger off-contract year + AFL.com.au FA list,
                       matched by name within club; everyone else on a current
                       list gets a derived 'contracted' row
  4. history           Draftguru year movements + trades for start..end:
                       draft selections -> draft_pick, signings/trades ->
                       player_transaction, pick swaps -> draft_pick_trade_history

Known approximations (all flagged in notes/source_note columns):
  - Draftguru is year-granular, so transaction dates are stored as Dec 31 of
    the trade-period year (mid-season drafts included).
  - draft_pick.original_club_id is set to the selecting club; reconstructing
    original ownership through pick-trade chains is a later refinement.
  - Pick components in trades link to draft_pick rows via their resolved final
    number (the "(#48 - ...)" extra); unresolved picks get history rows with a
    NULL draft_pick_id rather than a guessed one.
  - Historical players not on a current list are created with status
    'unattached' — delist/retire distinction needs a source we don't have yet.
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # player names break cp1252 consoles

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scraper"))

from afl_free_agents import fetch_free_agents
from draftguru import fetch_club_list, fetch_year_movements, fetch_year_trades
from footywire import fetch_out_of_contract as fetch_footywire_expiries
from identity import CLUB_COLORS, CLUBS, canonical_club, match_players, normalize_name
from zerohanger import fetch_off_contract

DB_PATH = Path(__file__).resolve().parent / "listtrac.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def split_name(full: str) -> tuple[str, str]:
    first, _, last = full.partition(" ")
    return first, last or first


def create_db() -> sqlite3.Connection:
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_PATH.read_text())
    conn.row_factory = sqlite3.Row
    return conn


def load_clubs(conn) -> dict[str, int]:
    ids = {}
    for name, v in CLUBS.items():
        primary, secondary = CLUB_COLORS[name]
        cur = conn.execute(
            "INSERT INTO club (name, abbreviation, primary_color, secondary_color) VALUES (?, ?, ?, ?)",
            (name, v["abbrev"], primary, secondary))
        ids[name] = cur.lastrowid
    return ids


def upsert_player(conn, name: str, draftguru_id: str | None = None, **fields) -> int:
    """Find by draftguru_id, else by normalized name; insert if new."""
    row = None
    if draftguru_id:
        row = conn.execute("SELECT id FROM player WHERE draftguru_id = ?", (draftguru_id,)).fetchone()
    if row is None:
        norm = normalize_name(name)
        for cand in conn.execute("SELECT id, first_name, last_name, draftguru_id FROM player"):
            if normalize_name(f"{cand['first_name']} {cand['last_name']}") == norm and (
                    draftguru_id is None or cand["draftguru_id"] in (None, draftguru_id)):
                row = cand
                break
    if row is not None:
        if draftguru_id:
            conn.execute("UPDATE player SET draftguru_id = COALESCE(draftguru_id, ?) WHERE id = ?",
                         (draftguru_id, row["id"]))
        for col, val in fields.items():
            if val is not None:
                conn.execute(f"UPDATE player SET {col} = COALESCE({col}, ?) WHERE id = ?", (val, row["id"]))
        return row["id"]

    first, last = split_name(name)
    cols = {"first_name": first, "last_name": last, "draftguru_id": draftguru_id,
            **{k: v for k, v in fields.items() if v is not None}}
    cur = conn.execute(
        f"INSERT INTO player ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
        list(cols.values()))
    return cur.lastrowid


def load_current_lists(conn, club_ids: dict[str, int], year: int) -> None:
    for club, v in CLUBS.items():
        roster = fetch_club_list(year, v["draftguru"])
        for p in roster:
            upsert_player(conn, p["name"], p["draftguru_id"],
                          current_club_id=club_ids[club], jumper_number=p["jumper"],
                          dob=p["dob"], height_cm=p["height_cm"], status="listed")
        print(f"  {club}: {len(roster)} listed")


def _club_players(conn, club_id: int) -> list[dict]:
    return [{"name": f"{r['first_name']} {r['last_name']}", "id": r["id"]}
            for r in conn.execute("SELECT id, first_name, last_name FROM player WHERE current_club_id = ?", (club_id,))]


def load_contract_status(conn, club_ids: dict[str, int], year: int) -> None:
    status_by_player: dict[int, tuple[str, str, str]] = {}  # id -> (status, url, note)

    for zh_club, players in fetch_off_contract(year).items():
        canon = canonical_club(zh_club)
        if canon is None:
            print(f"  ! unknown zerohanger club {zh_club}")
            continue
        matched, missed, _ = match_players(players, _club_players(conn, club_ids[canon]))
        for src, db in matched:
            status_by_player[db["id"]] = ("out_of_contract", src["source_url"], "")
        if missed:
            print(f"  ! {canon}: no player match for {[p['name'] for p in missed]}")

    for afl_club, fas in fetch_free_agents().items():
        canon = canonical_club(afl_club)
        if canon is None:
            print(f"  ! unknown AFL club {afl_club}")
            continue
        pool = _club_players(conn, club_ids[canon])
        for status_key in ("restricted", "unrestricted"):
            matched, missed, _ = match_players(fas[status_key], pool)
            for src, db in matched:
                note = "previously delisted" if src["previously_delisted"] else ""
                status_by_player[db["id"]] = (f"{status_key}_fa", src["source_url"], note)
            if missed:
                print(f"  ! {canon} ({status_key}): no match for {[p['name'] for p in missed]}")

    n = 0
    for row in conn.execute("SELECT id, current_club_id FROM player WHERE current_club_id IS NOT NULL"):
        status, url, note = status_by_player.get(
            row["id"], ("contracted", None, f"derived: not on {year} off-contract or FA lists"))
        conn.execute(
            """INSERT INTO contract_status (player_id, club_id, contracted_through_year, status,
                                            source_note, source_url, last_confirmed_date, is_current)
               VALUES (?, ?, ?, ?, ?, ?, date('now'), 1)""",
            (row["id"], row["current_club_id"], year if status != "contracted" else None,
             status, note or None, url))
        n += 1
    print(f"  contract_status rows: {n}")


def load_contract_years(conn, club_ids: dict[str, int], current_year: int) -> None:
    """Footywire's future out-of-contract pages give each contracted player's
    actual expiry year (+ FA class at expiry, + footywire_id). Current-year
    statuses from Zerohanger/AFL.com.au stay authoritative — this pass only
    fills the NULL through-years of players marked 'contracted'."""
    for year in range(current_year + 1, current_year + 7):
        data = fetch_footywire_expiries(year)
        if not data:
            continue
        updated = 0
        for club, players in data.items():
            if club not in club_ids:
                continue
            matched, _, _ = match_players(players, _club_players(conn, club_ids[club]))
            for src, dbp in matched:
                conn.execute("UPDATE player SET footywire_id = COALESCE(footywire_id, ?) WHERE id = ?",
                             (src["footywire_id"], dbp["id"]))
                cur = conn.execute(
                    """UPDATE contract_status
                       SET contracted_through_year = ?, source_url = ?,
                           source_note = ?
                       WHERE player_id = ? AND is_current = 1 AND status = 'contracted'
                         AND contracted_through_year IS NULL""",
                    (year, src["source_url"],
                     f"{src['fa_at_expiry'] or 'FA status unknown'} at {year} expiry",
                     dbp["id"]))
                updated += cur.rowcount
        print(f"  footywire {year}: {updated} through-years set")


TRANSACTION_TYPE = {"Free Agency": "sign_fa", "Trade": "trade",
                    "Pre-Draft": "sign_rookie", "Post-Draft": "sign_rookie"}
# Anything else (expansion-era oddities like "Training Squad Selection",
# "Zone Selection") is recorded as sign_rookie with the original label in notes.


def load_year_history(conn, club_ids: dict[str, int], year: int) -> None:
    movements = fetch_year_movements(year)
    date = f"{year}-12-31"
    note = "date approximate (year-level from Draftguru)"
    trade_moves = []  # kept for from-club resolution via trade blocks

    for m in movements:
        club_id = club_ids.get(canonical_club(m["club"]) or "")
        if club_id is None:
            continue
        pid = upsert_player(conn, m["name"], m["draftguru_id"],
                            height_cm=m["height_cm"], status="unattached")
        if m["draft_type"]:
            cur = conn.execute(
                """INSERT INTO draft_pick (year, draft_type, original_club_id, current_owner_club_id,
                                           pick_number, status, player_selected_id)
                   VALUES (?, ?, ?, ?, ?, 'used', ?)""",
                (year, m["draft_type"], club_id, club_id, m["pick_number"], pid))
            conn.execute("UPDATE player SET draft_pick_id = COALESCE(draft_pick_id, ?) WHERE id = ?",
                         (cur.lastrowid, pid))
        elif m["movement"] == "Trade":
            trade_moves.append((m, pid, club_id))
        else:
            conn.execute(
                """INSERT INTO player_transaction (player_id, type, to_club_id, date,
                                                   trade_period_year, source_url, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (pid, TRANSACTION_TYPE.get(m["movement"], "sign_rookie"), club_id, date, year,
                 m["source_url"],
                 "; ".join(x for x in (
                     m["movement"] if m["movement"] not in TRANSACTION_TYPE else "",
                     m["signing"], note) if x)))

    trades = fetch_year_trades(year)
    linked = set()
    for t in trades:
        two_sided = len(t["sides"]) == 2
        for i, side in enumerate(t["sides"]):
            # a side's components are what that club RECEIVED; the giver is
            # the other side (only resolvable for two-club trades)
            receiver = canonical_club(side["club"])
            giver = canonical_club(t["sides"][1 - i]["club"]) if two_sided else None
            receiver_id = club_ids.get(receiver or "")
            giver_id = club_ids.get(giver or "")
            for comp in side["components"]:
                if comp["type"] == "player" and receiver_id:
                    # trade blocks only carry surnames; resolve against this
                    # year's Trade movement rows headed to the receiving club
                    surname = normalize_name(comp["text"]).split()[-1]
                    for m, pid, to_club_id in trade_moves:
                        key = (t["slug"], pid)
                        if key not in linked and to_club_id == receiver_id and \
                                normalize_name(m["name"]).split()[-1] == surname:
                            conn.execute(
                                """INSERT INTO player_transaction (player_id, type, from_club_id,
                                       to_club_id, date, trade_period_year, source_url, notes)
                                   VALUES (?, 'trade', ?, ?, ?, ?, ?, ?)""",
                                (pid, giver_id, receiver_id, date, year, t["source_url"],
                                 f"{t['title']}; {note}"))
                            linked.add(key)
                            break
                elif comp["type"] in ("pick", "future_pick") and receiver_id and (
                        giver_id or comp.get("origin_club")):
                    # 3+-club trades have no single giver; for future picks the
                    # origin club stands in — ownership mapping only needs
                    # origin + receiver anyway
                    if not giver_id:
                        giver_id = club_ids.get(canonical_club(comp["origin_club"]) or "")
                        if not giver_id:
                            continue
                    final = re.match(r"#(\d+)", comp["resolved"] or "")
                    pick_row = None
                    if final:
                        pick_row = conn.execute(
                            """SELECT id FROM draft_pick WHERE year = ? AND draft_type = 'national'
                               AND pick_number = ?""", (year, int(final.group(1)))).fetchone()
                    if pick_row:
                        conn.execute("UPDATE draft_pick SET current_owner_club_id = ?, status = 'traded' WHERE id = ?",
                                     (receiver_id, pick_row["id"]))
                    if comp.get("future_year"):
                        # normalized so the draft-order API can map ownership:
                        # "2026 R2 (St Kilda)" = St Kilda's natural 2026 2nd-rounder
                        detail = f"{comp['future_year']} R{comp['future_round']} ({comp['origin_club']})"
                    else:
                        detail = comp["text"] + (f" -> {comp['resolved']}" if comp["resolved"] else "")
                    conn.execute(
                        """INSERT INTO draft_pick_trade_history (draft_pick_id, description,
                               from_club_id, to_club_id, date)
                           VALUES (?, ?, ?, ?, ?)""",
                        (pick_row["id"] if pick_row else None, detail, giver_id, receiver_id, date))

    # Trade movements the blocks didn't cover (e.g. 3-way trades) still get a row
    for m, pid, to_club_id in trade_moves:
        if not any(pid == k[1] for k in linked):
            conn.execute(
                """INSERT INTO player_transaction (player_id, type, to_club_id, date,
                                                   trade_period_year, source_url, notes)
                   VALUES (?, 'trade', ?, ?, ?, ?, ?)""",
                (pid, to_club_id, date, year, m["source_url"], note))

    n_picks = conn.execute("SELECT COUNT(*) c FROM draft_pick WHERE year = ?", (year,)).fetchone()["c"]
    print(f"  {year}: {len(movements)} movements, {len(trades)} trades, {n_picks} picks")


def replay_admin_entries(conn, club_ids: dict[str, int]) -> None:
    """Re-apply manual admin-tool entries (data/admin_entries.jsonl) after a
    rebuild — the scrape sources lag breaking news, so admin entries win.
    Lenient: a row that no longer applies (player gone, bad club) is skipped."""
    journal = Path(__file__).resolve().parent / "admin_entries.jsonl"
    if not journal.exists():
        return
    import json
    applied = 0
    for line in journal.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        action, p = entry["action"], entry["payload"]
        try:
            when = p.get("date") or entry["ts"][:10]
            # resolve the player by name (+ club-at-entry hint) — DB ids are
            # not stable across rebuilds
            pid = None
            if p.get("player_name"):
                norm = normalize_name(p["player_name"])
                cands = [r for r in conn.execute(
                    """SELECT p.id, p.first_name, p.last_name, c.abbreviation abbrev
                       FROM player p LEFT JOIN club c ON c.id = p.current_club_id""")
                    if normalize_name(f"{r['first_name']} {r['last_name']}") == norm]
                if len(cands) > 1 and p.get("player_club"):
                    cands = [r for r in cands if r["abbrev"] == p["player_club"]] or cands
                if len(cands) == 1:
                    pid = cands[0]["id"]
                else:
                    print(f"  ! admin replay: ambiguous/missing player {p['player_name']}")
                    continue
            elif p.get("player_id"):
                pid = p["player_id"]  # legacy entries only
            to_id = club_ids.get(next((k for k, v in CLUBS.items() if v["abbrev"] == p.get("to")), ""))
            if action in ("trade", "fa-sign") and pid and to_id:
                conn.execute(
                    """INSERT INTO player_transaction (player_id, type, from_club_id, to_club_id,
                           date, trade_period_year, source_url, notes)
                       VALUES (?, ?, (SELECT current_club_id FROM player WHERE id = ?), ?, ?, ?, ?, ?)""",
                    (pid, "trade" if action == "trade" else "sign_fa", pid, to_id, when,
                     int(when[:4]), p.get("source_url"), p.get("notes")))
                conn.execute("UPDATE player SET current_club_id = ?, status = 'listed' WHERE id = ?", (to_id, pid))
            if action in ("trade", "fa-sign", "re-sign") and pid:
                club = to_id if action != "re-sign" else conn.execute(
                    "SELECT current_club_id FROM player WHERE id = ?", (pid,)).fetchone()[0]
                if club:
                    conn.execute("UPDATE contract_status SET is_current = 0 WHERE player_id = ? AND is_current = 1", (pid,))
                    conn.execute(
                        """INSERT INTO contract_status (player_id, club_id, contracted_through_year, status,
                               source_note, source_url, last_confirmed_date, is_current)
                           VALUES (?, ?, ?, 'contracted', ?, ?, date('now'), 1)""",
                        (pid, club, p.get("through_year"), p.get("notes"), p.get("source_url")))
            elif action == "delist" and pid:
                conn.execute(
                    """INSERT INTO player_transaction (player_id, type, from_club_id, date,
                           trade_period_year, source_url, notes)
                       VALUES (?, ?, (SELECT current_club_id FROM player WHERE id = ?), ?, ?, ?, ?)""",
                    (pid, "retire" if p.get("retired") else "delist", pid, when, int(when[:4]),
                     p.get("source_url"), p.get("notes")))
                conn.execute("UPDATE player SET current_club_id = NULL, status = ? WHERE id = ?",
                             ("retired" if p.get("retired") else "unattached", pid))
                conn.execute("UPDATE contract_status SET is_current = 0 WHERE player_id = ? AND is_current = 1", (pid,))
            elif action == "pick-trade":
                f_id = club_ids.get(next((k for k, v in CLUBS.items() if v["abbrev"] == p.get("from")), ""))
                if f_id and to_id:
                    conn.execute(
                        """INSERT INTO draft_pick_trade_history (description, from_club_id, to_club_id, date)
                           VALUES (?, ?, ?, ?)""",
                        (p.get("description") or f"{p.get('year', '')} pick {p.get('pick_number', '?')}",
                         f_id, to_id, when))
            applied += 1
        except Exception as e:  # noqa: BLE001 — replay must never kill a rebuild
            print(f"  ! admin replay skipped ({action}): {e}")
    print(f"  admin entries replayed: {applied}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2015, help="first history year")
    ap.add_argument("--end", type=int, default=2026, help="last history year (also the current-list season)")
    args = ap.parse_args()

    conn = create_db()
    club_ids = load_clubs(conn)
    print("Loading current lists...")
    load_current_lists(conn, club_ids, args.end)
    print("Loading contract status...")
    load_contract_status(conn, club_ids, args.end)
    print("Loading contract end years (Footywire)...")
    load_contract_years(conn, club_ids, args.end)
    print("Loading history...")
    for year in range(args.start, args.end + 1):
        load_year_history(conn, club_ids, year)
    print("Replaying admin entries...")
    replay_admin_entries(conn, club_ids)
    conn.commit()

    for table in ("club", "player", "contract_status", "player_transaction", "draft_pick", "draft_pick_trade_history"):
        c = conn.execute(f"SELECT COUNT(*) c FROM {table}").fetchone()["c"]
        print(f"{table}: {c}")
    conn.close()


if __name__ == "__main__":
    main()
