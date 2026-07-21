"""
ListTrac admin — trade-period manual entry. LOCAL ONLY, never deployed.

    uvicorn admin.app:app --port 8011        (from repo root)

No clean scrape source exists for moves as they break (Draftguru updates
after the fact), so October runs through this tool: record the move against
the local data/listtrac.db, then hit Publish — it commits the DB snapshot
and pushes, and Vercel redeploys the live site with the news.

Actions write both the movement record (player_transaction /
draft_pick_trade_history) and the state it implies (player.current_club_id,
a fresh current contract_status row). Every action takes a source URL/note —
same provenance rule as the scrapers.
"""
import subprocess
import sqlite3
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "listtrac.db"
JOURNAL = ROOT / "data" / "admin_entries.jsonl"

app = FastAPI(title="ListTrac admin (local)")


def journal(action: str, payload: dict) -> None:
    """Every admin action is journalled so data/load.py can replay it after a
    rebuild — otherwise the weekly re-scrape would revert manual entries the
    sources haven't caught up on yet. Player identity is stored as name+club,
    NOT id: a rebuild reassigns database ids."""
    import json
    from datetime import datetime
    data = dict(payload)
    if data.get("player_id"):
        with db() as conn:
            r = conn.execute(
                """SELECT p.first_name || ' ' || p.last_name AS name, c.abbreviation abbrev
                   FROM player p LEFT JOIN club c ON c.id = p.current_club_id
                   WHERE p.id = ?""", (data["player_id"],)).fetchone()
            if r:
                data["player_name"], data["player_club"] = r["name"], r["abbrev"]
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"),
                            "action": action, "payload": data}) + "\n")


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def club_id(conn, abbrev: str) -> int:
    row = conn.execute("SELECT id FROM club WHERE abbreviation = ? COLLATE NOCASE", (abbrev,)).fetchone()
    if not row:
        raise HTTPException(400, f"unknown club '{abbrev}'")
    return row["id"]


def set_contract_status(conn, player_id: int, new_club_id: int | None, status: str,
                        through_year: int | None, source_url: str | None, note: str | None):
    conn.execute("UPDATE contract_status SET is_current = 0 WHERE player_id = ? AND is_current = 1", (player_id,))
    if new_club_id is not None:
        conn.execute(
            """INSERT INTO contract_status (player_id, club_id, contracted_through_year, status,
                                            source_note, source_url, last_confirmed_date, is_current)
               VALUES (?, ?, ?, ?, ?, ?, date('now'), 1)""",
            (player_id, new_club_id, through_year, status, note, source_url))


def add_transaction(conn, player_id: int, tx_type: str, from_id: int | None, to_id: int | None,
                    when: str, source_url: str | None, notes: str | None):
    conn.execute(
        """INSERT INTO player_transaction (player_id, type, from_club_id, to_club_id, date,
                                           trade_period_year, source_url, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (player_id, tx_type, from_id, to_id, when, int(when[:4]), source_url, notes))


@app.get("/api/search")
def search(q: str):
    with db() as conn:
        return [dict(r) for r in conn.execute(
            """SELECT p.id, p.first_name, p.last_name, c.name club, c.abbreviation abbrev,
                      cs.status, cs.contracted_through_year
               FROM player p
               LEFT JOIN club c ON c.id = p.current_club_id
               LEFT JOIN contract_status cs ON cs.player_id = p.id AND cs.is_current = 1
               WHERE p.first_name || ' ' || p.last_name LIKE ? COLLATE NOCASE
               ORDER BY p.current_club_id IS NULL, p.last_name LIMIT 15""", (f"%{q}%",))]


@app.get("/api/clubs")
def clubs():
    with db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT abbreviation, name FROM club ORDER BY name")]


@app.post("/api/trade")
def trade(payload: dict):
    journal("trade", payload)
    when = payload.get("date") or date.today().isoformat()
    with db() as conn:
        to_id = club_id(conn, payload["to"])
        p = conn.execute("SELECT current_club_id FROM player WHERE id = ?", (payload["player_id"],)).fetchone()
        if not p:
            raise HTTPException(400, "unknown player")
        add_transaction(conn, payload["player_id"], "trade", p["current_club_id"], to_id,
                        when, payload.get("source_url"), payload.get("notes"))
        conn.execute("UPDATE player SET current_club_id = ?, status = 'listed' WHERE id = ?",
                     (to_id, payload["player_id"]))
        set_contract_status(conn, payload["player_id"], to_id, "contracted",
                            payload.get("through_year"), payload.get("source_url"),
                            payload.get("notes") or "traded")
        conn.commit()
    return {"ok": True}


@app.post("/api/fa-sign")
def fa_sign(payload: dict):
    journal("fa-sign", payload)
    when = payload.get("date") or date.today().isoformat()
    with db() as conn:
        to_id = club_id(conn, payload["to"])
        p = conn.execute("SELECT current_club_id FROM player WHERE id = ?", (payload["player_id"],)).fetchone()
        add_transaction(conn, payload["player_id"], "sign_fa", p["current_club_id"] if p else None,
                        to_id, when, payload.get("source_url"), payload.get("notes"))
        conn.execute("UPDATE player SET current_club_id = ?, status = 'listed' WHERE id = ?",
                     (to_id, payload["player_id"]))
        set_contract_status(conn, payload["player_id"], to_id, "contracted",
                            payload.get("through_year"), payload.get("source_url"),
                            payload.get("notes") or "free agency signing")
        conn.commit()
    return {"ok": True}


@app.post("/api/re-sign")
def re_sign(payload: dict):
    journal("re-sign", payload)
    """Contract extension at the current club — e.g. an FA taken off the market."""
    with db() as conn:
        p = conn.execute("SELECT current_club_id FROM player WHERE id = ?", (payload["player_id"],)).fetchone()
        if not p or p["current_club_id"] is None:
            raise HTTPException(400, "player has no current club")
        set_contract_status(conn, payload["player_id"], p["current_club_id"], "contracted",
                            payload.get("through_year"), payload.get("source_url"),
                            payload.get("notes") or "re-signed")
        conn.commit()
    return {"ok": True}


@app.post("/api/delist")
def delist(payload: dict):
    journal("delist", payload)
    when = payload.get("date") or date.today().isoformat()
    tx = "retire" if payload.get("retired") else "delist"
    with db() as conn:
        p = conn.execute("SELECT current_club_id FROM player WHERE id = ?", (payload["player_id"],)).fetchone()
        add_transaction(conn, payload["player_id"], tx, p["current_club_id"] if p else None, None,
                        when, payload.get("source_url"), payload.get("notes"))
        conn.execute("UPDATE player SET current_club_id = NULL, status = ? WHERE id = ?",
                     ("retired" if tx == "retire" else "unattached", payload["player_id"]))
        conn.execute("UPDATE contract_status SET is_current = 0 WHERE player_id = ? AND is_current = 1",
                     (payload["player_id"],))
        conn.commit()
    return {"ok": True}


@app.post("/api/pick-trade")
def pick_trade(payload: dict):
    journal("pick-trade", payload)
    when = payload.get("date") or date.today().isoformat()
    with db() as conn:
        f_id, t_id = club_id(conn, payload["from"]), club_id(conn, payload["to"])
        pick_row = None
        if payload.get("year") and payload.get("pick_number"):
            pick_row = conn.execute(
                """SELECT id FROM draft_pick WHERE year = ? AND draft_type = 'national' AND pick_number = ?""",
                (payload["year"], payload["pick_number"])).fetchone()
            if pick_row:
                conn.execute("UPDATE draft_pick SET current_owner_club_id = ?, status = 'traded' WHERE id = ?",
                             (t_id, pick_row["id"]))
        conn.execute(
            """INSERT INTO draft_pick_trade_history (draft_pick_id, description, from_club_id, to_club_id, date)
               VALUES (?, ?, ?, ?, ?)""",
            (pick_row["id"] if pick_row else None,
             payload.get("description") or f"{payload.get('year', '')} pick {payload.get('pick_number', '?')}",
             f_id, t_id, when))
        conn.commit()
    return {"ok": True}


@app.post("/api/publish")
def publish():
    """Commit the DB snapshot and push — Vercel redeploys with the update."""
    git = ["git", "-C", str(ROOT)]
    try:
        subprocess.run(git + ["add", "-f", "data/listtrac.db", "data/admin_entries.jsonl"], check=True, capture_output=True)
        diff = subprocess.run(git + ["diff", "--cached", "--quiet"], capture_output=True)
        if diff.returncode == 0:
            return {"ok": True, "message": "No data changes to publish."}
        subprocess.run(git + ["commit", "-m", f"Admin data entry ({date.today().isoformat()})"],
                       check=True, capture_output=True)
        subprocess.run(git + ["push"], check=True, capture_output=True)
        return {"ok": True, "message": "Pushed — live site redeploys in ~1 minute."}
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, (e.stderr or b"").decode()[:500])


PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ListTrac admin — trade period entry</title>
<style>
:root { --ground:#F2F4F3; --card:#fff; --ink:#182129; --ink2:#55636D; --line:#D4DAD7;
  --accent:#BF4226; --ok:#1E6B4F; --warn:#A8730F; }
@media (prefers-color-scheme: dark) { :root { --ground:#10171C; --card:#182129; --ink:#E6EBE9;
  --ink2:#93A1A8; --line:#2C3942; --accent:#D8603F; --ok:#5BBD94; --warn:#D9A84E; } }
* { box-sizing:border-box; } body { background:var(--ground); color:var(--ink);
  font-family:system-ui,sans-serif; margin:0; padding:20px; line-height:1.45; }
.wrap { max-width:860px; margin:0 auto; }
h1 { font-size:22px; font-weight:800; letter-spacing:-0.02em; }
h1 em { font-style:normal; color:var(--accent); }
.card { background:var(--card); border:1px solid var(--line); border-radius:6px; padding:16px 18px; margin-top:16px; }
.card h2 { font-size:14px; margin:0 0 10px; text-transform:uppercase; letter-spacing:0.08em; }
label { display:block; font-size:12px; color:var(--ink2); margin:8px 0 3px; }
input, select { font:inherit; font-size:13.5px; color:var(--ink); background:var(--ground);
  border:1px solid var(--line); border-radius:5px; padding:7px 10px; width:100%; }
.row { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:10px; }
button { font:inherit; font-size:13px; font-weight:700; color:#fff; background:var(--accent);
  border:none; border-radius:5px; padding:9px 16px; margin-top:12px; cursor:pointer; }
button.ghost { background:none; color:var(--ink); border:1px solid var(--line); }
.hit { padding:6px 9px; border-bottom:1px solid var(--line); cursor:pointer; font-size:13.5px; }
.hit:hover { background:var(--ground); }
.hit .thin, .thin { color:var(--ink2); font-size:12px; }
#player-box { border:1px solid var(--line); border-radius:5px; max-height:220px; overflow-y:auto; margin-top:4px; }
#selected { font-weight:700; margin-top:6px; }
#msg { margin-top:10px; font-size:13px; font-weight:600; }
#msg.ok { color:var(--ok); } #msg.err { color:var(--warn); }
.note { font-size:12px; color:var(--ink2); }
</style></head><body><div class="wrap">
<h1>List<em>Trac</em> admin <span class="thin" style="font-weight:400;font-size:13px">local only — publish pushes the DB snapshot live</span></h1>

<div class="card">
  <h2>1 · Find player</h2>
  <input id="q" placeholder="Type a name…">
  <div id="player-box"></div>
  <p id="selected" class="thin">No player selected.</p>
</div>

<div class="card">
  <h2>2 · Action</h2>
  <div class="row">
    <div><label>Action</label>
      <select id="action">
        <option value="re-sign">Re-sign / extension</option>
        <option value="trade">Trade</option>
        <option value="fa-sign">Free agency signing</option>
        <option value="delist">Delist</option>
        <option value="retire">Retirement</option>
        <option value="pick-trade">Pick trade (no player)</option>
      </select></div>
    <div><label>To club (trade / FA)</label><select id="to"></select></div>
    <div><label>Contracted through</label><input id="through" type="number" placeholder="2030"></div>
    <div><label>Date</label><input id="date" type="date"></div>
  </div>
  <div class="row">
    <div><label>Pick year (pick trade)</label><input id="pyear" type="number" placeholder="2026"></div>
    <div><label>Pick number</label><input id="pnum" type="number" placeholder="7"></div>
    <div><label>From club (pick trade)</label><select id="from"></select></div>
  </div>
  <label>Source URL</label><input id="source" placeholder="https://…">
  <label>Notes</label><input id="notes" placeholder="e.g. 6-year deal, per Callum Twomey">
  <button id="go">Record it</button>
  <p id="msg"></p>
</div>

<div class="card">
  <h2>3 · Publish</h2>
  <p class="note">Commits data/listtrac.db and pushes — the live site redeploys in about a minute.</p>
  <button id="publish" class="ghost">Publish to live site</button>
  <p id="pubmsg"></p>
</div>

<script>
let selected = null;
const $ = id => document.getElementById(id);
const api = (p, opts) => fetch(p, opts).then(async r => { if (!r.ok) throw new Error((await r.json()).detail || r.status); return r.json(); });

api("/api/clubs").then(cs => ["to","from"].forEach(id =>
  $(id).innerHTML = cs.map(c => `<option value="${c.abbreviation}">${c.name}</option>`).join("")));

$("q").addEventListener("input", async () => {
  const q = $("q").value.trim();
  if (q.length < 2) { $("player-box").innerHTML = ""; return; }
  const hits = await api("/api/search?q=" + encodeURIComponent(q));
  $("player-box").innerHTML = hits.map(h => `
    <div class="hit" data-id="${h.id}" data-name="${h.first_name} ${h.last_name}">
      <b>${h.first_name} ${h.last_name}</b>
      <span class="thin">${h.club || "unattached"} · ${h.status || "no status"}${h.contracted_through_year ? " through " + h.contracted_through_year : ""}</span>
    </div>`).join("");
  document.querySelectorAll(".hit").forEach(el => el.addEventListener("click", () => {
    selected = { id: Number(el.dataset.id), name: el.dataset.name };
    $("selected").textContent = "Selected: " + selected.name;
    $("selected").classList.remove("thin");
  }));
});

$("go").addEventListener("click", async () => {
  const action = $("action").value;
  const msg = $("msg"); msg.className = ""; msg.textContent = "…";
  try {
    const base = { source_url: $("source").value || null, notes: $("notes").value || null,
                   date: $("date").value || null };
    if (action === "pick-trade") {
      await api("/api/pick-trade", { method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ ...base, year: Number($("pyear").value) || null,
          pick_number: Number($("pnum").value) || null, from: $("from").value, to: $("to").value }) });
    } else {
      if (!selected) throw new Error("select a player first");
      const payload = { ...base, player_id: selected.id,
        through_year: Number($("through").value) || null, to: $("to").value,
        retired: action === "retire" };
      const path = action === "retire" ? "delist" : action;
      await api("/api/" + path, { method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload) });
    }
    msg.className = "ok"; msg.textContent = "Recorded. Publish when you're done entering.";
  } catch (e) { msg.className = "err"; msg.textContent = e.message; }
});

$("publish").addEventListener("click", async () => {
  const m = $("pubmsg"); m.textContent = "Publishing…";
  try { const r = await api("/api/publish", { method: "POST" }); m.textContent = r.message; }
  catch (e) { m.textContent = "Failed: " + e.message; }
});
</script>
</div></body></html>"""


@app.get("/", response_class=HTMLResponse)
def page():
    return PAGE
