/* ListTrac SPA — hash-routed views over the FastAPI read API. */
"use strict";

const view = document.getElementById("view");

const esc = s => String(s ?? "").replace(/[&<>"']/g,
  c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} — ${path}`);
  return res.json();
}

const STATUS = {
  contracted:      { cls: "ok",   label: "Contracted" },
  out_of_contract: { cls: "warn", label: "Out of contract" },
  restricted_fa:   { cls: "rfa",  label: "Restricted FA" },
  unrestricted_fa: { cls: "ufa",  label: "Unrestricted FA" },
};
const chip = s => {
  const m = STATUS[s] || { cls: "plain", label: s || "unknown" };
  return `<span class="chip ${m.cls}">${esc(m.label)}</span>`;
};
const URGENCY = { restricted_fa: 0, unrestricted_fa: 1, out_of_contract: 2, contracted: 3 };

const age = dob => {
  if (!dob) return "";
  const d = new Date(dob), now = new Date();
  let a = now.getFullYear() - d.getFullYear();
  if (now < new Date(now.getFullYear(), d.getMonth(), d.getDate())) a--;
  return a;
};
const DRAFT_LABEL = { national: "Nat", rookie: "Rookie", pre_season: "Pre-S", mid_season: "Mid-S" };
const draftedShort = p => p.draft_year
  ? `${p.draft_year} ${DRAFT_LABEL[p.draft_type] || p.draft_type}${p.pick_number ? " · #" + p.pick_number : ""}`
  : "—";
const playerLink = p => `<a href="#/player/${p.id}">${esc(p.first_name)} ${esc(p.last_name)}</a>`;

/* Sample rail content until the v1.5 news aggregator lands. Links out only. */
const SPOTLIGHTS = `
  <div class="card">
    <p class="eyebrow">Spotlights</p>
    <p class="sub">Contract &amp; trade coverage from around the league. <strong>Sample content</strong> — the aggregator ships with v1.5; headlines will always link out to the original source.</p>
    <div class="spot"><span class="src">AFL.com.au</span>
      <p><a href="https://www.afl.com.au/news/1484077/2026afl-free-agentslist" target="_blank" rel="noopener">2026 free agents revealed: the official list</a></p></div>
    <div class="spot"><span class="src">Zero Hanger</span>
      <p><a href="https://www.zerohanger.com/afl/players/off-contract-2026/" target="_blank" rel="noopener">The out-of-contract class of 2026</a></p></div>
    <div class="spot"><span class="src">Herald Sun <span class="lock">· subscriber 🔒</span></span>
      <p><a href="#" onclick="return false">Paywalled coverage appears here — linked, never reproduced</a></p></div>
  </div>`;

/* ---------- views ---------- */

const timeAgo = iso => {
  if (!iso) return "";
  const mins = Math.max(1, Math.round((Date.now() - new Date(iso)) / 60000));
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
};

async function landingView() {
  const [summary, order, newsItems, trend, clubList] = await Promise.all([
    api("/api/summary"),
    api("/api/draft-order").catch(() => null),
    api("/api/news").catch(() => []),
    api("/api/trending").catch(() => []),
    api("/clubs").catch(() => []),
  ]);
  const s = summary.contract_statuses;

  const rfas = trend.filter(t => t.kind === "rfa");
  view.innerHTML = `
    <div class="cols">
      <div>
        <div class="feature">
          <p class="eyebrow feature-eyebrow">The story of the season</p>
          <h2>Free agency class of 2026</h2>
          <p class="feature-sub">${(s.restricted_fa || 0) + (s.unrestricted_fa || 0)} free agents and
            ${s.out_of_contract || 0} more out of contract at season's end — the biggest movement
            pool ListTrac has tracked. Six are restricted:</p>
          <p class="rfa-row">${rfas.map(t =>
            `<a class="rfa-chip" href="#/player/${t.id}">${esc(t.first_name)} ${esc(t.last_name)} <span>${esc(t.abbrev)}</span></a>`).join("")}</p>
          <p class="feature-ctas">
            <a class="cta" href="#/free-agents">Free agent board</a>
            <a class="cta ghost" href="#/free-agents/out_of_contract">Full off-contract list</a>
          </p>
        </div>

        ${order ? `
        <div class="card">
          <h3>Projected 2026 draft order</h3>
          <p class="sub">Live — reverse ladder, ${order.as_of_round} games into the season,
            via ${esc(order.source)}. No academy, father-son or priority adjustments yet.</p>
          <div class="tablewrap"><table>
            <thead><tr><th class="num">Pick</th><th>Club</th><th class="num">W–L</th><th class="num">%</th></tr></thead>
            <tbody>${order.picks.slice(0, 8).map(p => `
              <tr><td class="num"><b>${p.pick}</b></td>
                <td><i class="dot" style="background:${esc(p.primary_color || "#888")}"></i>${esc(p.club)}</td>
                <td class="num">${p.wins}–${p.losses}</td><td class="num">${p.percentage}</td></tr>`).join("")}
            </tbody>
          </table></div>
          <p class="srcline"><a href="#/draft-order">Full order with pick outcome stats →</a> · <a href="#/mock-draft">run your own mock draft →</a></p>
        </div>` : ""}

        ${clubList.length ? `
        <div class="card">
          <h3>Clubs</h3>
          <div class="clubstrip" style="margin-top:10px">
            ${clubList.map(c => `
              <a href="#/club/${esc(c.abbreviation)}">
                <span class="badge" style="--club:${esc(c.primary_color || "#888")}">${esc(c.abbreviation)}</span>
                ${esc(c.name)}</a>`).join("")}
          </div>
        </div>` : ""}

        <div class="card">
          <h3>Upcoming deadlines</h3>
          <p class="sub">Indicative windows — confirmed dates land closer to season's end.</p>
          <div class="tablewrap"><table><tbody>
            <tr><td class="thin">Early October</td><td>Free agency window opens</td></tr>
            <tr><td class="thin">Mid October</td><td>Trade period</td></tr>
            <tr><td class="thin">Late November</td><td>National draft</td></tr>
            <tr><td class="thin">Early December</td><td>Rookie draft · pre-season supplemental signings</td></tr>
          </tbody></table></div>
        </div>
      </div>

      <aside class="rail">
        <div class="card">
          <p class="eyebrow">Movement news</p>
          <p class="sub">Live from around the league — every headline links to its source.</p>
          ${newsItems.length ? newsItems.slice(0, 12).map(n => `
            <div class="spot">
              <span class="src">${esc(n.source)} <span class="thin">· ${timeAgo(n.published)}</span></span>
              <p><a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a></p>
            </div>`).join("") : `<p class="thin">News feed unavailable right now.</p>`}
        </div>
        <div class="card">
          <p class="eyebrow">Trending players</p>
          <p class="sub">From the data — FA class, newest picks, latest trades.</p>
          ${trend.map((t, i) => `
            <div class="trendrow">
              <span class="tn">${i + 1}</span>
              <span class="badge" style="--club:${esc((clubList.find(c => c.abbreviation === t.abbrev) || {}).primary_color || "#888")};width:22px;height:22px;font-size:8.5px">${esc(t.abbrev)}</span>
              <a href="#/player/${t.id}">${esc(t.first_name)} ${esc(t.last_name)}</a>
              <span class="treason">${esc(t.reason)}</span>
            </div>`).join("")}
        </div>
      </aside>
    </div>`;
}

const intelTip = (intel, n) => {
  const s = intel && intel.picks[n];
  if (!s) return "";
  return `DVI ${s.dvi} pts · avg ${s.avg_games} games · AA ${s.aa_pct}% · Prem ${s.prem_pct}%`
    + (s.rs_pct != null ? ` · Rising Star ${s.rs_pct}%` : "");
};

async function draftOrderView() {
  const [order, intel] = await Promise.all([
    api("/api/draft-order"), api("/api/pick-intel").catch(() => null)]);
  const cell = (n, key, suffix = "") => {
    const s = intel && intel.picks[n];
    return s ? `${s[key] ?? "—"}${s[key] != null ? suffix : ""}` : "—";
  };
  view.innerHTML = `
    <div class="card">
      <h3>Projected 2026 national draft order</h3>
      <p class="sub">Reverse ladder ${order.as_of_round} games into the season, live from ${esc(order.source)} —
        the Tankathon method, plus what history says each slot is worth.</p>
      <div class="tablewrap"><table>
        <thead><tr><th class="num">Pick</th><th>Club</th><th class="num">W–L</th>
          <th class="num">DVI pts</th><th class="num">Avg games</th>
          <th class="num">AA %</th><th class="num">Prem %</th><th class="num">Rising Star %</th></tr></thead>
        <tbody>${order.picks.map(p => `
          <tr><td class="num"><b>${p.pick}</b></td>
            <td><i class="dot" style="background:${esc(p.primary_color || "#888")}"></i>
              ${p.abbrev ? `<a href="#/club/${esc(p.abbrev)}">${esc(p.club)}</a>` : esc(p.club)}</td>
            <td class="num">${p.wins}–${p.losses}</td>
            <td class="num">${cell(p.pick, "dvi")}</td>
            <td class="num">${cell(p.pick, "avg_games")}</td>
            <td class="num">${cell(p.pick, "aa_pct", "%")}</td>
            <td class="num">${cell(p.pick, "prem_pct", "%")}</td>
            <td class="num">${cell(p.pick, "rs_pct", "%")}</td></tr>`).join("")}
        </tbody>
      </table></div>
      <p class="srcline">${intel ? `Outcome stats: every national-draft selection at that pick,
        ${intel.cohort.from}–${intel.cohort.to} drafts only (recent draftees would skew careers-in-progress).
        Sources: Draftguru pick histories · Wikipedia Rising Star nominations · official DVI.`
        : "Outcome stats not built yet."} Ladder refreshes hourly.</p>
    </div>`;
}

/* ---------- interactive mock draft ---------- */

const MOCK_KEY = "mock_draft_2026";
const loadMock = () => { try { return (JSON.parse(localStorage.getItem(MOCK_KEY)) || []).filter(Boolean); } catch { return []; } };
const saveMock = events => localStorage.setItem(MOCK_KEY, JSON.stringify(events));

/* Official AFL Draft Value Index (54 picks, current revision — sourced from
   draftguru.com.au's pick value calculator; matches AFL-published values). */
const DVI = [3000, 2481, 2178, 1962, 1795, 1659, 1543, 1443, 1355, 1276, 1205, 1140,
  1080, 1024, 973, 924, 879, 836, 796, 757, 721, 686, 653, 621, 590, 561, 533, 505,
  479, 454, 429, 405, 382, 360, 338, 317, 297, 277, 257, 238, 220, 202, 184, 167,
  150, 134, 118, 102, 86, 71, 57, 42, 28, 14];
const dvi = n => (n >= 1 && n <= DVI.length) ? DVI[n - 1] : 0;

/* Map a prospect's tie string to the matching club. A dual tie
   ("Sydney Academy & North Melbourne F/S") resolves to the first listed —
   we model that as the player's nomination. Tasmania isn't in the 2026 draft. */
const TIE_CLUBS = [["Western Bulldogs", "WB"], ["West Coast", "WCE"], ["North Melbourne", "NM"],
  ["Carlton", "CAR"], ["Fremantle", "FRE"], ["Essendon", "ESS"], ["Richmond", "RIC"],
  ["Brisbane", "BRI"], ["Gold Coast", "GCS"], ["GWS", "GWS"], ["Sydney", "SYD"]];
const tieClub = tie => {
  if (!tie) return null;
  let best = null;
  for (const [name, ab] of TIE_CLUBS) {
    const i = tie.indexOf(name);
    if (i !== -1 && (best === null || i < best.i)) best = { i, ab };
  }
  return best && best.ab;
};

/* Ladder-based loading on bid cost (2026 rule change): top two pay a 20%
   premium, preliminary finalists 10%, bottom five get a 10% discount. */
const bidLoading = rank => rank <= 2 ? 1.2 : rank <= 4 ? 1.1 : rank >= 14 ? 0.9 : 1.0;

/* Replay the selection events into a board state. Assumptions (shown in UI):
   standard pick hands (each club holds its natural picks in rounds 1-4 —
   2026 pick trades aren't applied), clubs always match when affordable,
   max two picks per match, matched bids insert an extra selection. */
function simulateDraft(events, orderPicks, byName) {
  const rows = orderPicks.map((pk, i) => ({ kind: "order", club: pk, slot: i + 1, assigned: null, absorbed: null }));
  const hands = {}, rankOf = {};
  orderPicks.forEach((pk, i) => {
    hands[pk.abbrev] = [i + 1, i + 19, i + 37, i + 55].map(n => ({ n, spent: false }));
    rankOf[pk.abbrev] = pk.ladder_rank;
  });
  const ledger = [], drafted = new Set();

  const currentRow = () => rows.find(r => r.kind === "order" && !r.assigned && !r.absorbed);
  const displayNum = row => {
    let n = 0;
    for (const r of rows) { if (!r.absorbed) n++; if (r === row) return n; }
    return n;
  };

  for (const name of events) {
    const row = currentRow();
    if (!row) break;
    const p = byName[name];
    if (!p || drafted.has(name)) continue;

    const tied = tieClub(p.tie);
    if (tied && tied !== row.club.abbrev && hands[tied]) {
      const pickNo = displayNum(row);
      const cost = Math.round(dvi(Math.min(pickNo, 54)) * bidLoading(rankOf[tied]));
      const avail = hands[tied].filter(x => !x.spent);
      let best = null;
      const consider = combo => {
        const pts = combo.reduce((s, x) => s + dvi(x.n), 0);
        if (pts < cost) return;
        const cand = { combo, pts, waste: pts - cost, usesR1: combo.some(x => x.n <= 18) ? 1 : 0 };
        if (!best || cand.waste < best.waste || (cand.waste === best.waste && cand.usesR1 < best.usesR1)) best = cand;
      };
      avail.forEach(a => consider([a]));
      for (let i = 0; i < avail.length; i++)
        for (let j = i + 1; j < avail.length; j++) consider([avail[i], avail[j]]);

      if (best) {
        best.combo.forEach(x => { x.spent = true; });
        for (const x of best.combo) {
          if (x.n <= 18) {
            const r1 = rows.find(r => r.kind === "order" && r.club.abbrev === tied);
            if (r1 && !r1.assigned && !r1.absorbed) r1.absorbed = "pick used to match bid for " + name;
          }
        }
        rows.splice(rows.indexOf(row), 0, {
          kind: "matched", club: orderPicks.find(pk => pk.abbrev === tied),
          assigned: p, matchNote: "matched bid at pick " + pickNo,
        });
        drafted.add(name);
        ledger.push({ pick: pickNo, bidder: row.club.abbrev, club: tied, player: name,
                      cost, paid: best.combo.map(x => x.n), pts: best.pts });
        continue; // the bidding club stays on the clock
      }
      ledger.push({ pick: pickNo, bidder: row.club.abbrev, club: tied, player: name, cost, failed: true });
    }
    row.assigned = p;
    drafted.add(name);
    // the club's own R1 pick is now used — it can't also fund a later match
    const own = hands[row.club.abbrev].find(x => x.n === row.slot);
    if (own) own.spent = true;
  }
  return { rows, ledger, drafted, currentRow };
}

async function mockDraftView() {
  const [order, pool, intel] = await Promise.all([
    api("/api/draft-order"), api("/api/prospects"), api("/api/pick-intel").catch(() => null)]);
  const prospects = pool.prospects;
  const byName = Object.fromEntries(prospects.map(p => [p.name, p]));
  let events = loadMock();
  let filter = "";

  const tieBadge = p => p.tie ? `<span class="chip warn" title="Club-tied — a rival selection triggers a bid">${esc(p.tie)}</span>` : "";

  function render() {
    const sim = simulateDraft(events, order.picks, byName);
    const cur = sim.currentRow();
    const available = prospects.filter(p => !sim.drafted.has(p.name));
    const done = !cur;
    let shown = 0;

    view.innerHTML = `
      <div class="controls">
        <button class="cta" id="auto" ${done ? "disabled" : ""}>Auto pick</button>
        <button class="filterbtn" id="simbtn" ${done ? "disabled" : ""}>Sim to end</button>
        <button class="filterbtn" id="undo" ${events.length ? "" : "disabled"}>Undo</button>
        <button class="filterbtn" id="reset">Reset</button>
        <button class="filterbtn" id="copy">Copy board</button>
        <span class="thin" style="font-size:12px">Saves automatically in this browser.</span>
      </div>
      <div class="mockcols">
        <div>
          <div class="card">
            <h3>2026 mock draft — first round${done ? " · complete" : ""}</h3>
            <p class="sub">Bid matching is live: pick a club-tied player with a rival on the clock
              and the tied club matches if it can afford the points. Matched bids insert an extra
              selection, exactly like the real thing.</p>
            <div class="boardlist">
              ${sim.rows.map(r => {
                const isCur = r === cur;
                if (r.absorbed) return `<div class="pickrow absorbed">
                  <span class="picknum">·</span><i class="dot" style="background:${esc(r.club.primary_color || "#888")}"></i>
                  <span class="pickclub">${esc(r.club.abbrev)}</span>
                  <span class="thin" style="font-size:12px">${esc(r.absorbed)}</span></div>`;
                shown++;
                return `<div class="pickrow ${isCur ? "otc" : ""} ${r.kind === "matched" ? "matched" : ""}"
                    title="${esc(intelTip(intel, shown))}">
                  <span class="picknum">${shown}</span>
                  <i class="dot" style="background:${esc(r.club.primary_color || "#888")}"></i>
                  <span class="pickclub">${esc(r.club.abbrev)}</span>
                  ${r.assigned
                    ? `<span class="picked"><b>${esc(r.assigned.name)}</b>
                        <span class="thin">${esc(r.assigned.position || r.assigned.state_team)}</span>
                        ${r.kind === "matched" ? `<span class="chip rfa">Matched bid</span>` : ""}</span>`
                    : isCur ? `<span class="otc-label">On the clock</span>` : ""}
                </div>`;
              }).join("")}
            </div>
          </div>
          ${sim.ledger.length ? `
          <div class="card">
            <h3>Bid ledger</h3>
            <p class="sub">Costs use the official Draft Value Index with 2026 ladder loadings
              (top two +20%, prelim finalists +10%, bottom five −10%). Max two picks per match.</p>
            <div class="tablewrap"><table>
              <thead><tr><th class="num">Bid</th><th>Bidder</th><th>Player</th><th>Outcome</th></tr></thead>
              <tbody>${sim.ledger.map(l => `
                <tr><td class="num">${l.pick}</td><td class="thin">${esc(l.bidder)}</td>
                  <td><b>${esc(l.player)}</b></td>
                  <td>${l.failed
                    ? `<span class="chip warn">${esc(l.club)} couldn&#39;t match</span> <span class="thin">needed ${l.cost} pts</span>`
                    : `<span class="chip ok">${esc(l.club)} matched</span> <span class="thin">${l.cost} pts,
                       paid with pick${l.paid.length > 1 ? "s" : ""} ${l.paid.join(" + ")}${l.pts > l.cost ? `, ${l.pts - l.cost} pts forfeited` : ""}</span>`}
                  </td></tr>`).join("")}
              </tbody>
            </table></div>
            <p class="srcline">Model: standard pick hands (rounds 1–4, 2026 pick trades not applied),
              clubs match whenever affordable, dual-tied players nominate their first-listed club.
              Round-2 compensation picks and pick sliding beyond the bid aren&#39;t modelled yet.</p>
          </div>` : ""}
        </div>
        <div class="card">
          <h3>Prospect pool <span class="thin" style="font-weight:400">(${available.length} of ${prospects.length})</span></h3>
          <p class="sub">2026 U18 championships squads, ranked per Reading the Play&#39;s Top 50.
            Click a player to make the pick.</p>
          <input id="poolsearch" class="poolsearch" type="search" placeholder="Filter by name, position, state, club…" value="${esc(filter)}">
          <div class="poollist">
            ${available
              .filter(p => !filter || [p.name, p.position, p.state_team, p.junior_club, p.tie]
                .join(" ").toLowerCase().includes(filter.toLowerCase()))
              .slice(0, 60).map(p => `
              <button class="poolrow" data-name="${esc(p.name)}" ${done ? "disabled" : ""}>
                <span class="rankchip ${p.rank ? "" : "unranked"}">${p.rank ?? "–"}</span>
                <span class="poolinfo"><b>${esc(p.name)}</b>
                  <span class="thin">${[p.position, p.height_cm ? p.height_cm + "cm" : null, p.state_team, p.junior_club]
                    .filter(Boolean).map(esc).join(" · ")}</span></span>
                ${tieBadge(p)}
              </button>`).join("")}
          </div>
          <p class="srcline">Squads: <a href="${esc(pool.sources.squads)}" target="_blank" rel="noopener">Rookie Me Central ↗</a>
            · Rankings: <a href="${esc(pool.sources.rankings)}" target="_blank" rel="noopener">Reading the Play ↗</a>
            (${esc(pool.sources.rankings_note)})</p>
        </div>
      </div>`;

    const commit = name => { events.push(name); saveMock(events); render(); };
    view.querySelectorAll(".poolrow").forEach(b => b.addEventListener("click", () => commit(b.dataset.name)));
    view.querySelector("#auto").addEventListener("click", () => available.length && commit(available[0].name));
    view.querySelector("#simbtn").addEventListener("click", () => {
      let s = simulateDraft(events, order.picks, byName);
      while (s.currentRow()) {
        const next = prospects.find(p => !s.drafted.has(p.name));
        if (!next) break;
        events.push(next.name);
        s = simulateDraft(events, order.picks, byName);
      }
      saveMock(events); render();
    });
    view.querySelector("#undo").addEventListener("click", () => { events.pop(); saveMock(events); render(); });
    view.querySelector("#reset").addEventListener("click", () => { events = []; saveMock(events); render(); });
    view.querySelector("#copy").addEventListener("click", async () => {
      const s = simulateDraft(events, order.picks, byName);
      let n = 0;
      const lines = s.rows.filter(r => !r.absorbed).map(r =>
        `${++n}. ${r.club.club}: ${r.assigned ? r.assigned.name : "—"}${r.kind === "matched" ? " (matched bid)" : ""}`);
      try { await navigator.clipboard.writeText(`ListTrac 2026 mock draft\n${lines.join("\n")}`); } catch {}
    });
    const search = view.querySelector("#poolsearch");
    search.addEventListener("input", () => {
      filter = search.value;
      const pos = search.selectionStart;
      render();
      const s2 = view.querySelector("#poolsearch");
      s2.focus(); s2.setSelectionRange(pos, pos);
    });
  }
  render();
}

async function clubsView() {
  const [clubs, summary] = await Promise.all([api("/clubs"), api("/api/summary")]);
  const s = summary.contract_statuses, c = summary.counts;
  view.innerHTML = `
    <div class="tiles">
      <div class="tile"><p class="eyebrow">Players tracked</p><b>${c.player.toLocaleString()}</b><span>since 1986</span></div>
      <div class="tile g"><p class="eyebrow">Draft picks</p><b>${c.draft_pick.toLocaleString()}</b><span>${summary.draft_years.min}–${summary.draft_years.max}</span></div>
      <div class="tile w"><p class="eyebrow">Off contract 2026</p><b>${(s.out_of_contract || 0) + (s.restricted_fa || 0) + (s.unrestricted_fa || 0)}</b><span>incl. free agents</span></div>
      <div class="tile r"><p class="eyebrow">Free agents</p><b>${(s.restricted_fa || 0) + (s.unrestricted_fa || 0)}</b><span>${s.restricted_fa || 0} restricted · ${s.unrestricted_fa || 0} unrestricted</span></div>
    </div>
    <div class="clubgrid">
      ${clubs.map(cl => `
        <a class="clubcard" href="#/club/${esc(cl.abbreviation)}" style="--club:${esc(cl.primary_color || "#888")}">
          <b>${esc(cl.name)}</b>
          <span>${cl.listed_players ? cl.listed_players + " listed · 2026" : "list forms for 2028 entry"}</span>
        </a>`).join("")}
    </div>`;
}

async function clubView(abbrev) {
  const list = await api(`/clubs/${encodeURIComponent(abbrev)}/list`);
  const first = list[0];
  const n = k => list.filter(p => p.contract_status === k).length;
  const sorted = [...list].sort((a, b) =>
    (URGENCY[a.contract_status] ?? 9) - (URGENCY[b.contract_status] ?? 9) ||
    (a.jumper_number ?? 99) - (b.jumper_number ?? 99));
  view.innerHTML = `
    <div class="tiles">
      <div class="tile" style="border-left-color:${esc(first.club_primary || "var(--accent)")}"><p class="eyebrow">List size</p><b>${list.length}</b><span>players · 2026</span></div>
      <div class="tile g"><p class="eyebrow">Contracted past '26</p><b>${n("contracted")}</b><span>players</span></div>
      <div class="tile w"><p class="eyebrow">Off contract '26</p><b>${list.length - n("contracted")}</b><span>incl. free agents</span></div>
      <div class="tile r"><p class="eyebrow">Free agents</p><b>${n("restricted_fa") + n("unrestricted_fa")}</b><span>${n("restricted_fa")} restricted · ${n("unrestricted_fa")} unrestricted</span></div>
    </div>
    <div class="card">
      <h3>${esc(first.club)} — 2026 list</h3>
      <p class="sub">Sorted by contract urgency.</p>
      <div class="tablewrap"><table>
        <thead><tr><th class="num">#</th><th>Player</th><th class="num">Age</th><th class="num">Ht</th><th>Drafted</th><th>Contract status</th><th class="num">Through</th></tr></thead>
        <tbody>${sorted.map(p => `
          <tr>
            <td class="num thin">${p.jumper_number ?? ""}</td>
            <td>${playerLink(p)}</td>
            <td class="num">${age(p.dob)}</td>
            <td class="num">${p.height_cm ?? ""}</td>
            <td class="thin">${esc(draftedShort(p))}</td>
            <td>${chip(p.contract_status)}</td>
            <td class="num ${p.contracted_through_year ? "" : "thin"}">${p.contracted_through_year ?? "—"}</td>
          </tr>`).join("")}
        </tbody>
      </table></div>
      <p class="srcline">Lists: Draftguru · off-contract: Zero Hanger · FA status: AFL.com.au — every row carries its source URL in the API.</p>
    </div>`;
}

function timelineHTML(p) {
  const current = p.contract_status.find(cs => cs.is_current) || {};
  const startYear = p.drafted ? p.drafted.year + 1 : 2022;
  const endYear = Math.max((current.contracted_through_year || 2026) + 1, 2027);
  const from = Math.max(startYear, endYear - 11);
  const statusCls = { restricted_fa: "rfa", unrestricted_fa: "ufa", out_of_contract: "warn", contracted: "ok" }[current.status] || "ok";
  let cells = "";
  for (let y = from; y <= endYear; y++) {
    let cls;
    if (y === 2026) cls = statusCls;
    else if (y < 2026) cls = "faded";
    else cls = current.status === "contracted" && current.contracted_through_year >= y ? "ok" : "tbd";
    cells += `<div class="yr"><div class="bar ${cls}"></div><div class="lab">'${String(y).slice(2)}</div></div>`;
  }
  return `<div class="timeline" aria-label="Contract status timeline">${cells}</div>
    <div class="legend">
      <span><i style="background:var(--ok);opacity:.75"></i>Contracted</span>
      <span><i style="background:var(--ok);opacity:.28"></i>On list (status not tracked pre-2026)</span>
      <span><i style="background:var(--${statusCls === "ok" ? "rfa" : statusCls})"></i>${esc((STATUS[current.status] || {}).label || "")} year</span>
      <span><i style="background:var(--line)"></i>Unresolved</span>
    </div>`;
}

async function playerView(id) {
  const p = await api(`/players/${id}`);
  const current = p.contract_status.find(cs => cs.is_current);
  const heroA = p.club_primary || "#333", heroTrim = p.club_secondary || "#ddd";
  const isFA = current && (current.status === "restricted_fa" || current.status === "unrestricted_fa");

  const txRows = [];
  if (p.drafted) txRows.push(`
    <tr><td class="thin">Nov ${p.drafted.year}</td><td><span class="chip ok">Drafted</span></td>
      <td>${p.drafted.year} ${esc(p.drafted.draft_type)} draft${p.drafted.pick_number ? ", pick " + p.drafted.pick_number : ""} — ${esc(p.drafted.club)}</td>
      <td><a href="https://www.draftguru.com.au/years/${p.drafted.year}" target="_blank" rel="noopener">Draftguru ↗</a></td></tr>`);
  for (const t of p.transactions) {
    const label = { trade: "Trade", sign_fa: "FA signing", sign_rookie: "Rookie signing", delist: "Delisted", retire: "Retired", rookie_elevate: "Elevated" }[t.type] || t.type;
    const cls = t.type === "trade" ? "warn" : "plain";
    txRows.push(`
      <tr><td class="thin">${esc((t.date || "").slice(0, 4))}</td><td><span class="chip ${cls}">${esc(label)}</span></td>
        <td>${t.from_club ? esc(t.from_club) + " → " : ""}${esc(t.to_club || "")}${t.notes ? ` <span class="thin">· ${esc(t.notes.replace("; date approximate (year-level from Draftguru)", ""))}</span>` : ""}</td>
        <td>${t.source_url ? `<a href="${esc(t.source_url)}" target="_blank" rel="noopener">source ↗</a>` : ""}</td></tr>`);
  }
  if (current && isFA) txRows.push(`
    <tr><td class="thin">Jul 2026</td><td>${chip(current.status)}</td>
      <td>Named ${esc(STATUS[current.status].label.toLowerCase())} for end of ${current.contracted_through_year}</td>
      <td>${current.source_url ? `<a href="${esc(current.source_url)}" target="_blank" rel="noopener">AFL.com.au ↗</a>` : ""}</td></tr>`);

  let sameBoat = "";
  if (isFA) {
    const peers = (await api(`/contract-status?status=${current.status}`)).filter(x => x.id !== p.id).slice(0, 8);
    if (peers.length) sameBoat = `
      <div class="card"><p class="eyebrow">Same boat</p>
        <p class="sub">Other ${esc(STATUS[current.status].label.toLowerCase())}s of 2026.</p>
        <div class="tablewrap"><table><tbody>
          ${peers.map(x => `<tr><td>${playerLink(x)}</td><td class="thin">${esc(x.club)}</td></tr>`).join("")}
        </tbody></table></div></div>`;
  }

  view.innerHTML = `
    <div class="hero" style="--hero-a:${esc(heroA)};--hero-b:${esc(heroA)}CC;--hero-trim:${esc(heroTrim)}">
      <div class="hero-inner">
        <p class="club-line">${p.club ? `<a href="#/club/${esc(p.club_abbrev)}">${esc(p.club)}</a>` : "Unattached"}</p>
        <h2>${esc(p.first_name)} ${esc(p.last_name)}</h2>
        ${current ? `<p class="statusline">${chip(current.status)}</p>` : ""}
        <dl class="hero-facts">
          ${p.dob ? `<div><dt>Age</dt><dd>${age(p.dob)} (${esc(p.dob)})</dd></div>` : ""}
          ${p.height_cm ? `<div><dt>Height</dt><dd>${p.height_cm} cm</dd></div>` : ""}
          ${p.jumper_number ? `<div><dt>Guernsey</dt><dd>#${p.jumper_number}</dd></div>` : ""}
          ${p.drafted ? `<div><dt>Drafted</dt><dd>${p.drafted.year} ${esc(p.drafted.draft_type)}${p.drafted.pick_number ? " · Pick " + p.drafted.pick_number : ""}</dd></div>
          <div><dt>Drafted by</dt><dd>${esc(p.drafted.club)}</dd></div>` : ""}
        </dl>
      </div>
    </div>
    <div class="cols">
      <div>
        ${current ? `<div class="card">
          <h3>Contract status</h3>
          <p class="sub">Status by season — ListTrac tracks status, never dollars.</p>
          ${timelineHTML(p)}
          ${current.source_url ? `<p class="srcline">Status per <a href="${esc(current.source_url)}" target="_blank" rel="noopener">source ↗</a> · confirmed ${esc(current.last_confirmed_date || "")}</p>` : `<p class="srcline">${esc(current.source_note || "")}</p>`}
        </div>` : ""}
        <div class="card">
          <h3>Transactions</h3>
          <p class="sub">Every list move on record, provenance attached. Historical dates are trade-period-year approximations.</p>
          <div class="tablewrap"><table>
            <thead><tr><th>When</th><th>Type</th><th>Detail</th><th>Source</th></tr></thead>
            <tbody>${txRows.join("") || `<tr><td colspan="4" class="thin">No recorded movements — original-list player.</td></tr>`}</tbody>
          </table></div>
        </div>
      </div>
      <aside class="rail">${SPOTLIGHTS}${sameBoat}</aside>
    </div>`;
}

async function draftView(year, draftType = "national") {
  let picks = [], picksErr = "";
  const intel = await api("/api/pick-intel").catch(() => null);
  try { picks = await api(`/drafts/${year}?draft_type=${encodeURIComponent(draftType)}`); }
  catch { picksErr = `No ${draftType.replace("_", "-")} draft recorded for ${year}.`; }
  let trades = { players: [], picks: [] };
  try { trades = await api(`/trades/${year}`); } catch { /* none that year */ }

  const years = [];
  for (let y = 2026; y >= 1986; y--) years.push(y);
  view.innerHTML = `
    <div class="controls">
      <label class="eyebrow" style="margin:0" for="dyear">Year</label>
      <select id="dyear">${years.map(y => `<option ${y === +year ? "selected" : ""}>${y}</option>`).join("")}</select>
      <label class="eyebrow" style="margin:0" for="dtype">Draft</label>
      <select id="dtype">
        ${["national", "rookie", "pre_season", "mid_season"].map(t =>
          `<option value="${t}" ${t === draftType ? "selected" : ""}>${t.replace("_", "-")}</option>`).join("")}
      </select>
    </div>
    <div class="card">
      <h3>${esc(year)} ${esc(draftType.replace("_", "-"))} draft</h3>
      <p class="sub">Pick, club on the night, and the player taken.</p>
      ${picksErr ? `<p class="thin">${esc(picksErr)}</p>` : `
      <div class="tablewrap"><table>
        <thead><tr><th class="num">Pick</th><th class="num">DVI</th><th>Club</th><th>Player</th><th>How the pick arrived</th></tr></thead>
        <tbody>${picks.map(pk => `
          <tr title="${esc(intelTip(intel, pk.pick_number))}">
            <td class="num">${pk.pick_number ?? "—"}</td>
            <td class="num thin">${intel && intel.picks[pk.pick_number] ? intel.picks[pk.pick_number].dvi : "—"}</td>
            <td>${esc(pk.club)}</td>
            <td>${pk.player_id ? `<a href="#/player/${pk.player_id}">${esc(pk.first_name)} ${esc(pk.last_name)}</a>` : "<span class='thin'>passed</span>"}</td>
            <td>${pk.status === "traded"
              ? `<span class="chip warn">via trade</span> <span class="thin">${esc(pk.trade_detail || "chain unresolved")}</span>`
              : "<span class='thin'>own selection</span>"}</td></tr>`).join("")}
        </tbody>
      </table></div>
      <p class="srcline">Hover a row for the pick's historical outcome profile (avg games, AA%, premiership%,
        Rising Star%). Trade chains from Draftguru; <a href="#/trades/${esc(year)}">full trade period →</a></p>`}
    </div>
    ${trades.players.length || trades.picks.length ? `
    <div class="card">
      <h3>Trades — ${esc(year)} trade period</h3>
      <p class="sub">${trades.players.length} player moves · ${trades.picks.length} pick moves. Pick rows show what each traded pick became.</p>
      ${trades.players.length ? `
      <div class="tablewrap"><table>
        <thead><tr><th>Player</th><th>From</th><th>To</th><th>Deal</th></tr></thead>
        <tbody>${trades.players.map(t => `
          <tr><td><a href="#/player/${t.player_id}">${esc(t.first_name)} ${esc(t.last_name)}</a></td>
            <td class="thin">${esc(t.from_club || "—")}</td><td>${esc(t.to_club || "")}</td>
            <td>${t.source_url ? `<a href="${esc(t.source_url)}" target="_blank" rel="noopener">detail ↗</a>` : ""}</td></tr>`).join("")}
        </tbody>
      </table></div>` : ""}
      ${trades.picks.length ? `
      <div class="tablewrap" style="margin-top:18px"><table>
        <thead><tr><th>Pick traded</th><th>From</th><th>To</th><th class="num">Became</th></tr></thead>
        <tbody>${trades.picks.map(t => `
          <tr><td>${esc(t.description || "")}</td><td class="thin">${esc(t.from_club)}</td><td>${esc(t.to_club)}</td>
            <td class="num ${t.resolved_pick ? "" : "thin"}">${t.resolved_pick ? "#" + t.resolved_pick : "—"}</td></tr>`).join("")}
        </tbody>
      </table></div>` : ""}
      <p class="srcline">Draftguru provenance on every row · dates approximate to the trade period.</p>
    </div>` : ""}`;

  document.getElementById("dyear").addEventListener("change", e => location.hash = `#/draft/${e.target.value}/${document.getElementById("dtype").value}`);
  document.getElementById("dtype").addEventListener("change", e => location.hash = `#/draft/${document.getElementById("dyear").value}/${e.target.value}`);
}

async function tradesView(year) {
  let trades = { players: [], picks: [] };
  let empty = "";
  try { trades = await api(`/trades/${year}`); } catch { empty = `No trade data recorded for ${year}.`; }
  const years = [];
  for (let y = 2025; y >= 1986; y--) years.push(y);
  view.innerHTML = `
    <div class="controls">
      <label class="eyebrow" style="margin:0" for="tyear">Trade period</label>
      <select id="tyear">${years.map(y => `<option ${y === +year ? "selected" : ""}>${y}</option>`).join("")}</select>
      <span class="thin" style="font-size:12px">Interactive trade machine is next on the roadmap.</span>
    </div>
    ${empty ? `<div class="card"><p class="thin">${esc(empty)}</p></div>` : `
    <div class="card">
      <h3>${esc(year)} trade period — player moves</h3>
      <p class="sub">${trades.players.length} players changed clubs. Dates are trade-period approximations.</p>
      <div class="tablewrap"><table>
        <thead><tr><th>Player</th><th>From</th><th>To</th><th>Deal</th></tr></thead>
        <tbody>${trades.players.map(t => `
          <tr><td><a href="#/player/${t.player_id}">${esc(t.first_name)} ${esc(t.last_name)}</a></td>
            <td class="thin">${esc(t.from_club || "—")}</td><td>${esc(t.to_club || "")}</td>
            <td>${t.source_url ? `<a href="${esc(t.source_url)}" target="_blank" rel="noopener">detail ↗</a>` : ""}</td></tr>`).join("")}
        </tbody>
      </table></div>
    </div>
    <div class="card">
      <h3>Pick moves</h3>
      <p class="sub">${trades.picks.length} picks changed hands — "became" shows the selection each pick resolved to.</p>
      <div class="tablewrap"><table>
        <thead><tr><th>Pick traded</th><th>From</th><th>To</th><th class="num">Became</th></tr></thead>
        <tbody>${trades.picks.map(t => `
          <tr><td>${esc(t.description || "")}</td><td class="thin">${esc(t.from_club)}</td><td>${esc(t.to_club)}</td>
            <td class="num ${t.resolved_pick ? "" : "thin"}">${t.resolved_pick ? "#" + t.resolved_pick : "—"}</td></tr>`).join("")}
        </tbody>
      </table></div>
      <p class="srcline">Draftguru provenance on every row · <a href="#/draft/${esc(year)}">see the resulting draft board →</a></p>
    </div>`}`;
  document.getElementById("tyear").addEventListener("change", e => location.hash = `#/trades/${e.target.value}`);
}

async function faView(filter = "all") {
  const statuses = filter === "all" ? ["restricted_fa", "unrestricted_fa"] : [filter];
  const lists = await Promise.all(statuses.map(s => api(`/contract-status?status=${s}`)));
  const players = lists.flat();
  const buttons = [["all", "All free agents"], ["restricted_fa", "Restricted"], ["unrestricted_fa", "Unrestricted"], ["out_of_contract", "Out of contract"]];
  view.innerHTML = `
    <div class="controls">
      ${buttons.map(([k, label]) =>
        `<button class="filterbtn ${k === filter ? "active" : ""}" data-f="${k}">${label}</button>`).join("")}
    </div>
    <div class="card">
      <h3>${esc(buttons.find(b => b[0] === filter)[1])} — end of 2026</h3>
      <p class="sub">${players.length} players. FA status per the official AFL list; off-contract per Zero Hanger.</p>
      <div class="tablewrap"><table>
        <thead><tr><th>Player</th><th>Club</th><th class="num">Age</th><th>Status</th><th>Source</th></tr></thead>
        <tbody>${players.map(x => `
          <tr><td>${playerLink(x)}</td><td class="thin">${esc(x.club)}</td>
            <td class="num">${age(x.dob)}</td><td>${chip(x.contract_status)}</td>
            <td>${x.source_url ? `<a href="${esc(x.source_url)}" target="_blank" rel="noopener">↗</a>` : ""}</td></tr>`).join("")}
        </tbody>
      </table></div>
    </div>`;
  view.querySelectorAll(".filterbtn").forEach(b =>
    b.addEventListener("click", () => location.hash = `#/free-agents/${b.dataset.f}`));
}

async function searchView(q) {
  const [players, allClubs] = await Promise.all([
    api(`/players?q=${encodeURIComponent(q)}`), api("/clubs").catch(() => [])]);
  const ql = q.toLowerCase();
  const clubHits = allClubs.filter(c =>
    c.name.toLowerCase().includes(ql) || c.abbreviation.toLowerCase() === ql);
  view.innerHTML = `
    ${clubHits.length ? `
    <div class="card">
      <h3>Clubs</h3>
      <div class="clubstrip" style="margin-top:10px">
        ${clubHits.map(c => `
          <a href="#/club/${esc(c.abbreviation)}">
            <span class="badge" style="--club:${esc(c.primary_color || "#888")}">${esc(c.abbreviation)}</span>
            ${esc(c.name)}</a>`).join("")}
      </div>
    </div>` : ""}
    <div class="card">
      <h3>Search: “${esc(q)}”</h3>
      <p class="sub">${players.length} match${players.length === 1 ? "" : "es"} (first 25 shown).</p>
      <div class="tablewrap"><table>
        <thead><tr><th>Player</th><th>Club</th><th class="num">Age</th><th>Status</th></tr></thead>
        <tbody>${players.map(x => `
          <tr><td>${playerLink(x)}</td><td class="thin">${esc(x.club || "—")}</td>
            <td class="num">${age(x.dob)}</td><td><span class="chip plain">${esc(x.player_status)}</span></td></tr>`).join("")}
        </tbody>
      </table></div>
    </div>`;
}

/* ---------- router ---------- */

const routes = [
  [/^#?\/?$/,                       () => landingView()],
  [/^#\/clubs$/,                    () => clubsView()],
  [/^#\/draft-order$/,              () => draftOrderView()],
  [/^#\/mock-draft$/,               () => mockDraftView()],
  [/^#\/trades\/(\d{4})$/,          m => tradesView(m[1])],
  [/^#\/club\/([A-Za-z]+)$/,        m => clubView(m[1])],
  [/^#\/player\/(\d+)$/,            m => playerView(m[1])],
  [/^#\/draft\/(\d{4})(?:\/(\w+))?$/, m => draftView(m[1], m[2] || "national")],
  [/^#\/free-agents(?:\/(\w+))?$/,  m => faView(m[1] || "all")],
  [/^#\/search\/(.+)$/,             m => searchView(decodeURIComponent(m[1]))],
];

async function route() {
  const hash = location.hash || "#/";
  document.querySelectorAll("#nav a").forEach(a =>
    a.classList.toggle("active", hash === a.getAttribute("href") ||
      (a.getAttribute("href") !== "#/" && hash.startsWith(a.getAttribute("href").split("/").slice(0, 2).join("/")))));
  for (const [re, fn] of routes) {
    const m = hash.match(re);
    if (m) {
      view.innerHTML = `<p class="loading">Loading…</p>`;
      try { await fn(m); } catch (e) { view.innerHTML = `<p class="error">Couldn't load this page — ${esc(e.message)}</p>`; }
      window.scrollTo(0, 0);
      return;
    }
  }
  view.innerHTML = `<p class="error">Page not found.</p>`;
}

document.getElementById("search-form").addEventListener("submit", e => {
  e.preventDefault();
  const q = document.getElementById("search-input").value.trim();
  if (q) location.hash = `#/search/${encodeURIComponent(q)}`;
});
window.addEventListener("hashchange", route);
route();
