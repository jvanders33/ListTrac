# ListTrac

AFL player movement, list, contract-status, and draft tracker — Spotrac/Tankathon for Australian sport.

## Scope (v1 — AFL)
- List tracker (current club lists)
- Trade & movement tracker
- Draft tracker (order, points, pick trade history)
- Contract status board (status only — no salary figures; AFL doesn't disclose these)

## Structure
- `scraper/` — data ingestion (AFL Tables, Footywire, Squiggle API)
- `data/` — schema + normalized data store
- `admin/` — manual entry tool for trades/contract status (no clean public source exists)
- `web/` — frontend

## Data sources
- AFL Tables (afltables.com) — historical player/club data
- Footywire — current squads, stats
- Squiggle API (squiggle.com.au) — ladder/standings, proper public API
- Manual/reporter-sourced — trades, draft picks, contract status

## Non-goals (v1)
- Contract dollar values (no public source, don't fabricate)
- NRL/NBL support (planned expansion, not v1)
