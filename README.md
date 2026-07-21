# ListTrac

AFL player movement, list, contract-status, and draft tracker — Spotrac/Tankathon for Australian sport.

## Scope (v1 — AFL)
- List tracker (current club lists)
- Trade & movement tracker
- Draft tracker (order, points, pick trade history)
- Contract status board (status only — no salary figures; AFL doesn't disclose these)

## Structure
- `scraper/` — data ingestion (AFL Tables, Draftguru, Zerohanger, AFL.com.au, Squiggle API)
- `data/` — schema.sql + load.py (builds listtrac.db from the scrapers via identity.py)
- `api/` — FastAPI read API over the SQLite DB (`uvicorn api.app:app` serves API + frontend)
- `admin/` — manual entry tool for trades/contract status (no clean public source exists)
- `web/` — frontend (vanilla SPA, no build step; served by FastAPI everywhere).
  Must NOT be renamed `public/` — Vercel strips that folder from function bundles.

## Deploy (Vercel)
Everything routes through the Python function (`api/index.py`): vercel.json
bundles the whole repo into it (`includeFiles: "**"`) and FastAPI serves both
the API and `web/` static files. `data/listtrac.db` is a **committed
read-only snapshot** that ships with each deploy. To refresh the data:
`python data/load.py`, commit the new DB, push — Vercel redeploys.
Scraper-only deps live in `scraper/requirements.txt` so the function stays lean.

## News spotlights (web layer)
Aggregate existing contract/trade/free-agency coverage, Spotrac-spotlights
style: headline + source + link out only. Paywalled/firewalled pieces get
linked like everything else — never reproduced or summarized around the
paywall.

## Data sources
- AFL Tables (afltables.com) — historical player/club data
- Footywire — current squads, stats
- Draftguru (draftguru.com.au) — historical drafts, trades, lists by year
- Zerohanger + AFL.com.au — contract status / free agent lists
- Squiggle API (squiggle.com.au) — ladder/standings, proper public API
- Manual/reporter-sourced — trades, draft picks, contract status

## Roadmap: v1.5 — fantasy context layer
Fantasy-as-context, not fantasy-tools. FanFooty owns live scoring, planners,
projections, and editorial player news — don't compete there. ListTrac's wedge
is fantasy data alongside the structural layer nobody else has: contract
status, FA class, trade history, draft pedigree on the same player page.

- `fantasy_score` table: player_id, year, round, sc_points, af_points,
  af_price, breakeven
- FootyWire scraper for SC/AF points per round (fitzRoy has a reference
  implementation; doubles as the footywire_id reconciliation source)
- AFL Fantasy JSON feed for prices/ownership
- Generated "player notes" view merging scoring trends with movement/contract
  flags — e.g. "off-contract 2026, restricted FA, SC average up 18 on last
  year". Data-driven blurbs only; no editorial, no live scores.
- FanFooty is a competitor reference, not a data source (proprietary feed)

## Non-goals (v1)
- Contract dollar values (no public source, don't fabricate)
- NRL/NBL support (planned expansion, not v1)
- Live fantasy scoring, team planners, projections (FanFooty's turf — see v1.5)
