"""
ListTrac read API — FastAPI over data/listtrac.db.

    uvicorn api.app:app --reload        (from repo root; build the DB first
                                         with python data/load.py)

Read-only by design: the DB is rebuilt by the loader, and trade-period manual
entry will get its own admin tool. No dollar figures anywhere — contract
status only, per project scope.
"""
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "listtrac.db"

app = FastAPI(title="ListTrac API", version="0.1.0",
              description="AFL player movement, lists, contract status, and draft history. No salary data.")


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def rows(query: str, params: tuple = ()) -> list[dict]:
    with db() as conn:
        return [dict(r) for r in conn.execute(query, params)]


PLAYER_COLS = """p.id, p.first_name, p.last_name, p.dob, p.height_cm, p.jumper_number,
                 p.status player_status, c.name club, c.abbreviation club_abbrev"""


@app.get("/clubs")
def clubs():
    return rows("""SELECT c.id, c.name, c.abbreviation,
                          COUNT(p.id) listed_players
                   FROM club c LEFT JOIN player p
                        ON p.current_club_id = c.id AND p.status = 'listed'
                   GROUP BY c.id ORDER BY c.name""")


@app.get("/clubs/{abbrev}/list")
def club_list(abbrev: str):
    result = rows(f"""SELECT {PLAYER_COLS}, cs.status contract_status, cs.contracted_through_year
                      FROM player p
                      JOIN club c ON c.id = p.current_club_id
                      LEFT JOIN contract_status cs ON cs.player_id = p.id AND cs.is_current = 1
                      WHERE c.abbreviation = ? COLLATE NOCASE
                      ORDER BY p.jumper_number""", (abbrev,))
    if not result:
        raise HTTPException(404, f"no listed players for club '{abbrev}'")
    return result


@app.get("/players")
def search_players(q: str):
    like = f"%{q}%"
    return rows(f"""SELECT {PLAYER_COLS}
                    FROM player p LEFT JOIN club c ON c.id = p.current_club_id
                    WHERE p.first_name || ' ' || p.last_name LIKE ? COLLATE NOCASE
                    ORDER BY p.last_name LIMIT 25""", (like,))


@app.get("/players/{player_id}")
def player(player_id: int):
    found = rows(f"""SELECT {PLAYER_COLS}, p.draftguru_id
                     FROM player p LEFT JOIN club c ON c.id = p.current_club_id
                     WHERE p.id = ?""", (player_id,))
    if not found:
        raise HTTPException(404, "player not found")
    profile = found[0]

    profile["contract_status"] = rows(
        """SELECT cs.status, cs.contracted_through_year, c.name club,
                  cs.source_note, cs.source_url, cs.last_confirmed_date, cs.is_current
           FROM contract_status cs JOIN club c ON c.id = cs.club_id
           WHERE cs.player_id = ? ORDER BY cs.is_current DESC""", (player_id,))
    profile["transactions"] = rows(
        """SELECT pt.type, cf.name from_club, ct.name to_club, pt.date,
                  pt.trade_period_year, pt.notes, pt.source_url
           FROM player_transaction pt
           LEFT JOIN club cf ON cf.id = pt.from_club_id
           LEFT JOIN club ct ON ct.id = pt.to_club_id
           WHERE pt.player_id = ? ORDER BY pt.date""", (player_id,))
    profile["drafted"] = next(iter(rows(
        """SELECT dp.year, dp.draft_type, dp.pick_number, c.name club
           FROM draft_pick dp JOIN club c ON c.id = dp.original_club_id
           WHERE dp.player_selected_id = ?""", (player_id,))), None)
    return profile


@app.get("/drafts/{year}")
def draft(year: int, draft_type: str = "national"):
    result = rows("""SELECT dp.pick_number, dp.draft_type, dp.status,
                            c.name club, co.name original_club,
                            p.id player_id, p.first_name, p.last_name
                     FROM draft_pick dp
                     JOIN club c ON c.id = dp.current_owner_club_id
                     JOIN club co ON co.id = dp.original_club_id
                     LEFT JOIN player p ON p.id = dp.player_selected_id
                     WHERE dp.year = ? AND dp.draft_type = ?
                     ORDER BY dp.pick_number""", (year, draft_type))
    if not result:
        raise HTTPException(404, f"no {draft_type} draft data for {year}")
    return result


@app.get("/trades/{year}")
def trades(year: int):
    player_moves = rows(
        """SELECT pt.player_id, p.first_name, p.last_name, cf.name from_club,
                  ct.name to_club, pt.notes, pt.source_url
           FROM player_transaction pt
           JOIN player p ON p.id = pt.player_id
           LEFT JOIN club cf ON cf.id = pt.from_club_id
           LEFT JOIN club ct ON ct.id = pt.to_club_id
           WHERE pt.type = 'trade' AND pt.trade_period_year = ?""", (year,))
    pick_moves = rows(
        """SELECT h.description, cf.name from_club, ct.name to_club,
                  dp.pick_number resolved_pick, dp.year draft_year
           FROM draft_pick_trade_history h
           JOIN club cf ON cf.id = h.from_club_id
           JOIN club ct ON ct.id = h.to_club_id
           LEFT JOIN draft_pick dp ON dp.id = h.draft_pick_id
           WHERE h.date LIKE ?""", (f"{year}-%",))
    if not player_moves and not pick_moves:
        raise HTTPException(404, f"no trade data for {year}")
    return {"year": year, "players": player_moves, "picks": pick_moves}


@app.get("/contract-status")
def contract_status(status: str | None = None, club: str | None = None):
    query = f"""SELECT {PLAYER_COLS}, cs.status contract_status,
                       cs.contracted_through_year, cs.source_url
                FROM contract_status cs
                JOIN player p ON p.id = cs.player_id
                JOIN club c ON c.id = cs.club_id
                WHERE cs.is_current = 1"""
    params: list = []
    if status:
        query += " AND cs.status = ?"
        params.append(status)
    if club:
        query += " AND c.abbreviation = ? COLLATE NOCASE"
        params.append(club)
    return rows(query + " ORDER BY c.name, p.last_name", tuple(params))
