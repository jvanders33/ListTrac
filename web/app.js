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

/* Player-movement insiders on X. Set INSIDER_LIST_URL to an X List URL
   (e.g. https://twitter.com/i/lists/123...) to embed the whole list; the
   handle links below always render regardless of whether X allows the
   embedded timeline for logged-out viewers. */
const INSIDER_LIST_URL = "https://twitter.com/CalTwomey";
const INSIDERS = [
  ["CalTwomey", "Callum Twomey — AFL.com.au"],
  ["MitchCleary", "Mitch Cleary — AFL.com.au"],
  ["barrettdamian", "Damian Barrett — AFL.com.au"],
  ["sammcclure", "Sam McClure — The Age"],
  ["tommorris32", "Tom Morris"],
  ["RalphyHeraldSun", "Jon Ralph — Herald Sun"],
];

function loadXWidgets() {
  if (window.twttr) { window.twttr.widgets && window.twttr.widgets.load(view); return; }
  const s = document.createElement("script");
  s.src = "https://platform.twitter.com/widgets.js";
  s.async = true;
  document.head.appendChild(s);
}

/* Hand-picked must-reads pinned to the top of the movement news rail.
   Swap entries as better editions drop (Twomey's guide is ~monthly). */
const FEATURED_NEWS = [{
  title: "Cal Twomey's Phantom Form Guide: the July top-25 draft prospect rankings",
  source: "AFL.com.au",
  url: "https://www.afl.com.au/news/1565947/cal-twomeys-phantom-form-guide-top-draft-prospects-july-ranking",
}];

/* Player-page rail: key movement reading. */
const SPOTLIGHTS = `
  <div class="card">
    <p class="eyebrow">Spotlights</p>
    <div class="spot"><span class="src">AFL.com.au</span>
      <p><a href="https://www.afl.com.au/news/1484077/2026afl-free-agentslist" target="_blank" rel="noopener">2026 free agents revealed: the official list</a></p></div>
    <div class="spot"><span class="src">Zero Hanger</span>
      <p><a href="https://www.zerohanger.com/afl/players/off-contract-2026/" target="_blank" rel="noopener">The out-of-contract class of 2026</a></p></div>
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
  const [summary, order, newsItems, trend, clubList, adminUpdates] = await Promise.all([
    api("/api/summary"),
    api("/api/draft-order").catch(() => null),
    api("/api/news").catch(() => []),
    api("/api/trending").catch(() => []),
    api("/clubs").catch(() => []),
    api("/api/updates").catch(() => []),
  ]);
  const s = summary.contract_statuses;
  const rfas = trend.filter(t => t.kind === "rfa");

  // Top stories: first-party updates and aggregated headlines compete on
  // recency alone — news moves fast. The freshest three rotate in the hero.
  const stories = [];
  adminUpdates.filter(u => u.player_name && (Date.now() - new Date(u.ts)) < 7 * 86400e3)
    .forEach(u => {
      const dest = u.action === "trade" || u.action === "fa-sign" ? ` to ${u.to}` : "";
      const through = u.through_year ? ` through ${u.through_year}` : "";
      stories.push({
        ts: +new Date(u.ts),
        eyebrow: `ListTrac update · ${timeAgo(u.ts)}`,
        title: `${u.player_name} ${u.verb}${dest}${through}`,
        sub: u.notes || "",
        ctas: `<a class="cta" href="#/search/${encodeURIComponent(u.player_name)}">Player page</a>
               ${u.source_url ? `<a class="cta ghost" href="${esc(u.source_url)}" target="_blank" rel="noopener">Source ↗</a>` : ""}`,
      });
    });
  newsItems.slice(0, 6).forEach(n => stories.push({
    ts: +new Date(n.published || 0),
    eyebrow: `${esc(n.source)} · ${timeAgo(n.published)}`,
    title: n.title,
    sub: "",
    ctas: `<a class="cta" href="${esc(n.url)}" target="_blank" rel="noopener">Read at ${esc(n.source)} ↗</a>
           <a class="cta ghost" href="#/free-agents">Free agent board</a>`,
  }));
  stories.sort((a, b) => b.ts - a.ts);
  const leads = stories.slice(0, 3);

  view.innerHTML = `
    <div class="cols">
      <div>
        ${leads.length ? `
        <div class="feature" id="hero-rotor">
          ${leads.map((s, i) => `
          <div class="hero-slide ${i === 0 ? "on" : ""}" data-i="${i}">
            <p class="eyebrow feature-eyebrow">${s.eyebrow}</p>
            <h2>${esc(s.title)}</h2>
            ${s.sub ? `<p class="feature-sub">${esc(s.sub)}</p>` : ""}
            <p class="feature-ctas">${s.ctas}</p>
          </div>`).join("")}
          ${leads.length > 1 ? `<div class="hero-dots">
            ${leads.map((_, i) => `<button data-i="${i}" class="${i === 0 ? "on" : ""}" aria-label="Story ${i + 1}"></button>`).join("")}
          </div>` : ""}
        </div>` : ""}

        <div class="card">
          <h3>Free agency class of 2026</h3>
          <p class="sub">${(s.restricted_fa || 0) + (s.unrestricted_fa || 0)} free agents and
            ${s.out_of_contract || 0} more out of contract at season's end. ${rfas.length} are restricted:</p>
          <p class="rfa-row">${rfas.map(t =>
            `<a class="rfa-chip light" href="#/player/${t.id}">${esc(t.first_name)} ${esc(t.last_name)} <span>${esc(t.abbrev)}</span></a>`).join("")}</p>
          <p class="feature-ctas" style="margin-top:14px">
            <a class="cta" href="#/free-agents">Free agent board</a>
            <a class="cta quiet" href="#/free-agents/out_of_contract">Full off-contract list</a>
          </p>
        </div>

        ${order ? `
        <div class="card">
          <h3>Projected 2026 draft order</h3>
          <p class="sub">Live — reverse ladder, ${order.as_of_round} games in, with
            ${order.traded_slots || 0} already-traded 2026 picks applied. No bid-compensation
            or priority adjustments yet.</p>
          <div class="tablewrap"><table>
            <thead><tr><th class="num">Pick</th><th>Club</th><th class="num">W–L</th><th class="num">%</th></tr></thead>
            <tbody>${order.picks.slice(0, 8).map(p => `
              <tr><td class="num"><b>${p.pick}</b></td>
                <td><i class="dot" style="background:${esc(p.primary_color || "#888")}"></i>${esc(p.club)}
                  ${p.via ? `<span class="chip warn">via ${esc(p.via)}</span>` : ""}</td>
                <td class="num">${p.wins}–${p.losses}</td><td class="num">${p.percentage}</td></tr>`).join("")}
            </tbody>
          </table></div>
          <p class="srcline"><a href="#/draft">Full order with pick outcome stats →</a> · <a href="#/draft/mock">run your own mock draft →</a></p>
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
          ${FEATURED_NEWS.filter(f => !newsItems.some(n => n.url === f.url)).map(f => `
            <div class="spot">
              <span class="src">${esc(f.source)} <span class="chip rfa" style="font-size:9px">Featured</span></span>
              <p><a href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.title)}</a></p>
            </div>`).join("")}
          ${newsItems.length ? newsItems.slice(0, 12).map(n => `
            <div class="spot">
              <span class="src">${esc(n.source)} <span class="thin">· ${timeAgo(n.published)}</span></span>
              <p><a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a></p>
            </div>`).join("") : `<p class="thin">News feed unavailable right now.</p>`}
        </div>
        <div class="card">
          <p class="eyebrow">Insider feed</p>
          <a class="twitter-timeline" data-height="380" data-dnt="true" data-tweet-limit="5"
             href="${esc(INSIDER_LIST_URL)}">Posts from AFL insiders</a>
          <div class="insiders">
            ${INSIDERS.map(([h, label]) => `
              <a href="https://twitter.com/${esc(h)}" target="_blank" rel="noopener">@${esc(h)}
                <span class="thin">· ${esc(label)}</span></a>`).join("")}
          </div>
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
  loadXWidgets();

  // hero rotation — one timer, dies with the element
  const rotor = document.getElementById("hero-rotor");
  if (rotor && leads.length > 1) {
    let cur = 0;
    const show = i => {
      cur = i;
      rotor.querySelectorAll(".hero-slide").forEach(s => s.classList.toggle("on", +s.dataset.i === i));
      rotor.querySelectorAll(".hero-dots button").forEach(b => b.classList.toggle("on", +b.dataset.i === i));
    };
    if (heroTimer) clearInterval(heroTimer);
    heroTimer = setInterval(() => {
      if (!document.contains(rotor)) { clearInterval(heroTimer); return; }
      show((cur + 1) % leads.length);
    }, 7000);
    rotor.querySelectorAll(".hero-dots button").forEach(b =>
      b.addEventListener("click", () => show(+b.dataset.i)));
  }
}
let heroTimer = null;

/* Inline SVG sparkline of a rating timeline — higher is better, so the y-axis
   is rating value; endpoint emphasised. */
function sparkline(seasons) {
  if (seasons.length < 2) return "";
  const w = 320, h = 56, pad = 4;
  const vals = seasons.map(s => s.rating);
  const lo = Math.min(...vals), hi = Math.max(...vals), span = hi - lo || 1;
  const x = i => pad + i * (w - 2 * pad) / (seasons.length - 1);
  const y = v => pad + (h - 2 * pad) * (1 - (v - lo) / span);
  const pts = seasons.map((s, i) => `${x(i).toFixed(1)},${y(s.rating).toFixed(1)}`).join(" ");
  const last = seasons[seasons.length - 1];
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none" aria-hidden="true">
    <polyline fill="none" stroke="var(--accent)" stroke-width="2" points="${pts}"/>
    <circle cx="${x(seasons.length - 1).toFixed(1)}" cy="${y(last.rating).toFixed(1)}" r="3.5" fill="var(--accent)"/>
  </svg>`;
}

const intelTip = (intel, n) => {
  const s = intel && intel.picks[n];
  if (!s) return "";
  return `DVI ${s.dvi} pts · avg ${s.avg_games} games · AA ${s.aa_pct}% · Prem ${s.prem_pct}%`
    + (s.rs_pct != null ? ` · Rising Star ${s.rs_pct}%` : "");
};

async function draftOrderView(chrome = "") {
  const [order, intel] = await Promise.all([
    api("/api/draft-order"), api("/api/pick-intel").catch(() => null)]);
  const cell = (n, key, suffix = "") => {
    const s = intel && intel.picks[n];
    return s ? `${s[key] ?? "—"}${s[key] != null ? suffix : ""}` : "—";
  };
  const rowHTML = p => `
    <tr><td class="num"><b>${p.pick}</b></td>
      <td><i class="dot" style="background:${esc(p.primary_color || "#888")}"></i>
        ${p.abbrev ? `<a href="#/club/${esc(p.abbrev)}">${esc(p.club)}</a>` : esc(p.club)}
        ${p.via ? `<span class="chip warn" title="Natural slot belongs to ${esc(p.via)} — traded">via ${esc(p.via)}</span>` : ""}</td>
      <td class="num">${p.round === 1 ? `${p.wins}–${p.losses}` : ""}</td>
      <td class="num">${p.dvi || "—"}</td>
      <td class="num">${cell(p.pick, "avg_games")}</td>
      <td class="num">${cell(p.pick, "aa_pct", "%")}</td>
      <td class="num">${cell(p.pick, "prem_pct", "%")}</td>
      <td class="num">${cell(p.pick, "rs_pct", "%")}</td></tr>`;
  view.innerHTML = `${chrome}
    <div class="card">
      <h3>Projected 2026 national draft order — all rounds</h3>
      <p class="sub">Live reverse ladder, ${order.as_of_round} games in, with all
        ${order.traded_slots} already-traded 2026 picks applied ("via" = the club whose natural
        slot it is). Outcome stats show what history says each slot is worth.</p>
      <div class="tablewrap"><table>
        <thead><tr><th class="num">Pick</th><th>Owner</th><th class="num">W–L</th>
          <th class="num">DVI pts</th><th class="num">Avg games</th>
          <th class="num">AA %</th><th class="num">Prem %</th><th class="num">Rising Star %</th></tr></thead>
        <tbody>${(order.rounds || [{ round: 1, picks: order.picks }]).map(r => `
          <tr><td colspan="8" style="background:var(--card-2);font-weight:800;font-size:11px;
            letter-spacing:0.1em;text-transform:uppercase;padding:6px 12px">Round ${r.round}</td></tr>
          ${r.picks.map(rowHTML).join("")}`).join("")}
        </tbody>
      </table></div>
      ${intel ? `
      <div class="statlegend">
        <p class="eyebrow">Reading this table</p>
        <dl>
          <div><dt>via</dt><dd>the pick changed hands — shown against the club that now owns it, named for the club whose ladder position sets the slot</dd></div>
          <div><dt>DVI pts</dt><dd>the pick's value on the AFL's official Draft Value Index — the points currency used to match academy and father-son bids</dd></div>
          <div><dt>Avg games</dt><dd>average career games played by every player ever taken at that pick</dd></div>
          <div><dt>AA %</dt><dd>share of players taken at that pick who made an All-Australian team</dd></div>
          <div><dt>Prem %</dt><dd>share who played in a premiership</dd></div>
          <div><dt>Rising Star %</dt><dd>share who earned a Rising Star nomination in their early seasons</dd></div>
        </dl>
        <p class="thin" style="font-size:11.5px;margin:8px 0 0">Outcome stats cover the
          ${intel.cohort.from}–${intel.cohort.to} drafts — more recent draftees are still mid-career
          and would drag the numbers down.</p>
      </div>` : ""}
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
function simulateDraft(events, orderPicks, byName, rounds) {
  const rows = orderPicks.map((pk, i) => ({ kind: "order", club: pk, slot: i + 1, assigned: null, absorbed: null }));
  const hands = {}, rankOf = {};
  if (rounds) {
    // real ownership: each club's hand is the picks it actually holds
    rounds.forEach(r => r.picks.forEach(p => {
      (hands[p.abbrev] = hands[p.abbrev] || []).push({ n: p.pick, spent: false });
    }));
    // bid loadings key off the matching club's own ladder finish
    orderPicks.forEach(pk => { rankOf[pk.via || pk.abbrev] = pk.ladder_rank; });
    orderPicks.forEach(pk => { if (!(pk.abbrev in hands)) hands[pk.abbrev] = []; });
  } else {
    orderPicks.forEach((pk, i) => {
      hands[pk.abbrev] = [i + 1, i + 19, i + 37, i + 55].map(n => ({ n, spent: false }));
      rankOf[pk.abbrev] = pk.ladder_rank;
    });
  }
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
            const r1 = rows.find(r => r.kind === "order" && r.slot === x.n);
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
    // the pick just used can't also fund a later match
    const own = (hands[row.club.abbrev] || []).find(x => x.n === row.slot);
    if (own) own.spent = true;
  }
  return { rows, ledger, drafted, currentRow };
}

async function mockDraftView(chrome = "") {
  const [order, pool, intel] = await Promise.all([
    api("/api/draft-order"), api("/api/prospects"), api("/api/pick-intel").catch(() => null)]);
  const prospects = pool.prospects;
  const byName = Object.fromEntries(prospects.map(p => [p.name, p]));
  let events = loadMock();
  let filter = "";

  const tieBadge = p => p.tie ? `<span class="chip warn" title="Club-tied — a rival selection triggers a bid">${esc(p.tie)}</span>` : "";

  function render() {
    const sim = simulateDraft(events, order.picks, byName, order.rounds);
    const cur = sim.currentRow();
    const available = prospects.filter(p => !sim.drafted.has(p.name));
    const done = !cur;
    let shown = 0;

    view.innerHTML = `${chrome}
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
            <p class="sub">Pick a club-tied player with a rival on the clock and the tied club
              matches if it can afford the points — matched bids insert an extra selection.</p>
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
                  ${r.club.via ? `<span class="thin" style="font-size:10px">via ${esc(r.club.via)}</span>` : ""}
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
          </div>` : ""}
        </div>
        <div class="card">
          <h3>Prospect pool <span class="thin" style="font-weight:400">(${available.length} of ${prospects.length})</span></h3>
          <p class="sub">The 2026 U18 championships pool in ranked order — click a player to make the pick.</p>
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
        </div>
      </div>`;

    const commit = name => { events.push(name); saveMock(events); render(); };
    view.querySelectorAll(".poolrow").forEach(b => b.addEventListener("click", () => commit(b.dataset.name)));
    view.querySelector("#auto").addEventListener("click", () => available.length && commit(available[0].name));
    view.querySelector("#simbtn").addEventListener("click", () => {
      let s = simulateDraft(events, order.picks, byName, order.rounds);
      while (s.currentRow()) {
        const next = prospects.find(p => !s.drafted.has(p.name));
        if (!next) break;
        events.push(next.name);
        s = simulateDraft(events, order.picks, byName, order.rounds);
      }
      saveMock(events); render();
    });
    view.querySelector("#undo").addEventListener("click", () => { events.pop(); saveMock(events); render(); });
    view.querySelector("#reset").addEventListener("click", () => { events = []; saveMock(events); render(); });
    view.querySelector("#copy").addEventListener("click", async () => {
      const s = simulateDraft(events, order.picks, byName, order.rounds);
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

/* ---------- trade machine ---------- */

const TM_KEY = "trade_machine_v1";
const tmLoad = () => { try { return JSON.parse(localStorage.getItem(TM_KEY)) || null; } catch { return null; } };
const tmSave = s => localStorage.setItem(TM_KEY, JSON.stringify(s));

/* A club's tradeable 2026 picks: projected R1 slot from the live order plus
   standard R2-R4 slots, valued by DVI. Future picks carry no points yet. */
function tmPicks(abbrev, order) {
  // the picks a club ACTUALLY holds — natural slots minus traded away,
  // plus anything acquired (marked "via")
  const picks = [];
  (order.rounds || [{ round: 1, picks: order.picks }]).forEach(r => r.picks.forEach(p => {
    if (p.abbrev === abbrev) picks.push({
      id: `2026-${p.pick}`,
      label: `2026 pick ${p.pick} (R${r.round}${p.via ? ", via " + p.via : ""})`,
      dvi: p.dvi ?? dvi(p.pick),
    });
  }));
  for (const year of [2027, 2028]) {
    for (const round of [1, 2, 3, 4]) {
      picks.push({ id: `${year}-R${round}`, label: `${year} round ${round} (future)`, dvi: null });
    }
  }
  return picks;
}

async function tradeMachineView(chrome = "") {
  const [clubList, order] = await Promise.all([api("/clubs"), api("/api/draft-order")]);
  const clubs = clubList.filter(c => c.listed_players > 0);
  let state = tmLoad() || {
    a: { club: clubs[0].abbreviation, players: [], picks: [] },
    b: { club: clubs[1].abbreviation, players: [], picks: [] },
  };
  const rosters = {};  // abbrev -> list rows

  async function roster(abbrev) {
    if (!rosters[abbrev]) {
      const list = await api(`/clubs/${abbrev}/list`);
      rosters[abbrev] = list.sort((a, b) =>
        `${a.last_name} ${a.first_name}`.localeCompare(`${b.last_name} ${b.first_name}`));
    }
    return rosters[abbrev];
  }

  const statusWarn = p => {
    if (!p.contract_status || p.contract_status === "contracted") return null;
    const label = (STATUS[p.contract_status] || {}).label || p.contract_status;
    return `${p.first_name} ${p.last_name} is ${label.toLowerCase()} — uncontracted players can't be traded without re-signing first`;
  };

  async function render() {
    const [ra, rb] = await Promise.all([roster(state.a.club), roster(state.b.club)]);
    const sides = [
      { key: "a", other: "b", list: ra },
      { key: "b", other: "a", list: rb },
    ];
    // prune selections that no longer exist (club changed)
    for (const s of sides) {
      const st = state[s.key];
      const ids = new Set(s.list.map(p => p.id));
      st.players = st.players.filter(id => ids.has(id));
      const pickIds = new Set(tmPicks(st.club, order).map(p => p.id));
      st.picks = st.picks.filter(id => pickIds.has(id));
    }
    tmSave(state);

    const sideData = sides.map(s => {
      const st = state[s.key];
      const info = clubs.find(c => c.abbreviation === st.club) || {};
      const chosen = s.list.filter(p => st.players.includes(p.id));
      const picks = tmPicks(st.club, order).filter(p => st.picks.includes(p.id));
      const points = picks.reduce((t, p) => t + (p.dvi || 0), 0);
      const warnings = chosen.map(statusWarn).filter(Boolean);
      return { ...s, st, info, chosen, picks, points, warnings };
    });

    const [A, B] = sideData;
    const diff = A.points - B.points;
    const anyAssets = A.chosen.length + A.picks.length + B.chosen.length + B.picks.length > 0;
    const verdict = !anyAssets ? "" :
      Math.abs(diff) <= 300 ? "Pick points are roughly balanced."
      : `${(diff > 0 ? A : B).info.name} sends ${Math.abs(diff)} more DVI points — the player side of the deal has to justify it.`;

    const sideHTML = s => `
      <div class="card tm-side">
        <div class="tm-head">
          <span class="badge" style="--club:${esc(s.info.primary_color || "#888")}">${esc(s.st.club)}</span>
          <select data-side="${s.key}" class="tm-club">
            ${clubs.map(c => `<option value="${esc(c.abbreviation)}" ${c.abbreviation === s.st.club ? "selected" : ""}>${esc(c.name)}</option>`).join("")}
          </select>
        </div>
        <p class="eyebrow" style="margin-top:12px">Players out</p>
        <div class="tm-assets">
          ${s.list.map(p => `
            <label class="tm-asset ${s.st.players.includes(p.id) ? "on" : ""}">
              <input type="checkbox" data-side="${s.key}" data-kind="players" data-id="${p.id}"
                ${s.st.players.includes(p.id) ? "checked" : ""}>
              <span><b>${esc(p.first_name)} ${esc(p.last_name)}</b>
                <span class="thin">${age(p.dob)}yo${p.contract_status && p.contract_status !== "contracted" ? " · " : ""}</span>
                ${p.contract_status && p.contract_status !== "contracted" ? chip(p.contract_status) : ""}</span>
            </label>`).join("")}
        </div>
        <p class="eyebrow" style="margin-top:12px">Picks out</p>
        <div class="tm-assets">
          ${tmPicks(s.st.club, order).map(p => `
            <label class="tm-asset ${s.st.picks.includes(p.id) ? "on" : ""}">
              <input type="checkbox" data-side="${s.key}" data-kind="picks" data-id="${esc(p.id)}"
                ${s.st.picks.includes(p.id) ? "checked" : ""}>
              <span><b>${esc(p.label)}</b> <span class="thin">${p.dvi != null ? p.dvi + " pts" : "value TBD"}</span></span>
            </label>`).join("")}
        </div>
      </div>`;

    view.innerHTML = `${chrome}
      <div class="controls">
        <button class="filterbtn" id="tm-reset">Reset</button>
        <button class="filterbtn" id="tm-copy">Copy trade</button>
      </div>
      <div class="tmcols">
        ${sideHTML(A)}
        ${sideHTML(B)}
      </div>
      <div class="card">
        <h3>The deal</h3>
        ${anyAssets ? `
        <div class="tablewrap"><table>
          <thead><tr><th></th><th>${esc(A.info.name)} receives</th><th>${esc(B.info.name)} receives</th></tr></thead>
          <tbody>
            <tr><td class="thin">Players</td>
              <td>${B.chosen.map(p => `${esc(p.first_name)} ${esc(p.last_name)}`).join(", ") || "—"}</td>
              <td>${A.chosen.map(p => `${esc(p.first_name)} ${esc(p.last_name)}`).join(", ") || "—"}</td></tr>
            <tr><td class="thin">Picks</td>
              <td>${B.picks.map(p => esc(p.label)).join(", ") || "—"}</td>
              <td>${A.picks.map(p => esc(p.label)).join(", ") || "—"}</td></tr>
            <tr><td class="thin">Pick points</td>
              <td class="num">${B.points}</td><td class="num">${A.points}</td></tr>
            <tr><td class="thin">Net list spots</td>
              <td class="num">${B.chosen.length - A.chosen.length > 0 ? "+" : ""}${B.chosen.length - A.chosen.length}</td>
              <td class="num">${A.chosen.length - B.chosen.length > 0 ? "+" : ""}${A.chosen.length - B.chosen.length}</td></tr>
          </tbody>
        </table></div>
        <p class="sub" style="margin-top:12px">${esc(verdict)}</p>
        ${[...A.warnings, ...B.warnings].map(w => `<p class="tm-warn">⚠ ${esc(w)}</p>`).join("")}
        ` : `<p class="thin">Select players and picks on each side to build a trade.</p>`}
      </div>`;

    view.querySelectorAll(".tm-club").forEach(sel => sel.addEventListener("change", async e => {
      const side = e.target.dataset.side;
      state[side] = { club: e.target.value, players: [], picks: [] };
      tmSave(state); await render();
    }));
    view.querySelectorAll(".tm-asset input").forEach(cb => cb.addEventListener("change", async e => {
      const { side, kind, id } = e.target.dataset;
      const arr = state[side][kind];
      const val = kind === "players" ? Number(id) : id;
      const i = arr.indexOf(val);
      if (i === -1) arr.push(val); else arr.splice(i, 1);
      tmSave(state); await render();
    }));
    view.querySelector("#tm-reset").addEventListener("click", async () => {
      state = { a: { club: state.a.club, players: [], picks: [] }, b: { club: state.b.club, players: [], picks: [] } };
      tmSave(state); await render();
    });
    view.querySelector("#tm-copy").addEventListener("click", async () => {
      const line = (name, recv) => `${name} receive: ${recv.join(", ") || "nothing"}`;
      const text = ["ListTrac trade machine",
        line(A.info.name, [...B.chosen.map(p => p.first_name + " " + p.last_name), ...B.picks.map(p => p.label)]),
        line(B.info.name, [...A.chosen.map(p => p.first_name + " " + p.last_name), ...A.picks.map(p => p.label)]),
        verdict].filter(Boolean).join("\n");
      try { await navigator.clipboard.writeText(text); } catch {}
    });
  }
  await render();
}

async function playersView() {
  const clubList = await api("/clubs").catch(() => []);
  view.innerHTML = `
    <div class="card">
      <h3>Find a player</h3>
      <input id="pfind" class="poolsearch" type="search" placeholder="Start typing a name…" autocomplete="off">
      <div id="presults"></div>
    </div>
    <div class="card">
      <h3>Quick lists</h3>
      <p class="feature-ctas" style="margin-top:10px">
        <a class="cta" href="#/free-agents">Free agents 2026</a>
        <a class="cta quiet" href="#/free-agents/restricted_fa">Restricted FAs</a>
        <a class="cta quiet" href="#/free-agents/out_of_contract">Out of contract</a>
      </p>
    </div>
    <div class="card">
      <h3>Browse by club</h3>
      <div class="clubstrip" style="margin-top:10px">
        ${clubList.filter(c => c.listed_players > 0).map(c => `
          <a href="#/club/${esc(c.abbreviation)}">
            <span class="badge" style="--club:${esc(c.primary_color || "#888")}">${esc(c.abbreviation)}</span>
            ${esc(c.name)}</a>`).join("")}
      </div>
    </div>
    <div class="card" id="ratings-card">
      <h3>Player rankings</h3>
      <p class="sub">Loading the official ratings…</p>
    </div>`;

  const loadRatings = year => api(`/api/ratings?limit=50${year ? "&year=" + year : ""}`).then(data => {
    const card = document.getElementById("ratings-card");
    if (!card) return;
    const yrs = data.years || [data.year];
    card.innerHTML = `
      <h3>Player rankings</h3>
      <div class="controls" style="margin-top:6px">
        <label class="eyebrow" style="margin:0" for="ratingsyear">Season</label>
        <select id="ratingsyear">${yrs.slice().reverse().map(y =>
          `<option ${y === data.year ? "selected" : ""}>${y}</option>`).join("")}</select>
      </div>
      <p class="sub" style="margin-top:10px">${esc(data.attribution)} — top ${data.ratings.length} of ${data.count} rated players, ${data.year}.</p>
      <div class="tablewrap"><table>
        <thead><tr><th class="num">Rank</th><th>Player</th><th>Club</th><th class="num">Games</th><th class="num">Rating</th></tr></thead>
        <tbody>${data.ratings.map(r => `
          <tr><td class="num"><b>${r.rank ?? "—"}</b></td>
            <td>${r.player_id ? `<a href="#/player/${r.player_id}">${esc(r.name)}</a>` : esc(r.name)}</td>
            <td class="thin">${esc(r.team)}</td><td class="num">${r.games ?? ""}</td>
            <td class="num"><b>${r.rating}</b></td></tr>`).join("")}
        </tbody>
      </table></div>
      <p class="srcline">Source: <a href="${esc(data.source_url)}" target="_blank" rel="noopener">${esc(data.attribution)} ↗</a></p>`;
    document.getElementById("ratingsyear").addEventListener("change", e => loadRatings(+e.target.value));
  }).catch(() => {
    const card = document.getElementById("ratings-card");
    if (card) card.querySelector(".sub").textContent = "Ratings unavailable right now.";
  });
  loadRatings();

  const box = document.getElementById("pfind"), out = document.getElementById("presults");
  let timer;
  box.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      const q = box.value.trim();
      if (q.length < 2) { out.innerHTML = ""; return; }
      const players = await api(`/players?q=${encodeURIComponent(q)}`).catch(() => []);
      out.innerHTML = players.length ? `
        <div class="tablewrap" style="margin-top:10px"><table>
          <tbody>${players.map(x => `
            <tr><td>${playerLink(x)}</td><td class="thin">${esc(x.club || "—")}</td>
              <td class="num">${age(x.dob)}</td></tr>`).join("")}
          </tbody>
        </table></div>` : `<p class="thin" style="margin-top:10px">No matches.</p>`;
    }, 250);
  });
  box.focus();
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
  const fullName = `${p.first_name} ${p.last_name}`;
  const news = await api(`/api/player-news?name=${encodeURIComponent(fullName)}`).catch(() => []);
  const current = p.contract_status.find(cs => cs.is_current);
  const heroA = p.club_primary || "#333", heroTrim = p.club_secondary || "#ddd";
  const isFA = current && (current.status === "restricted_fa" || current.status === "unrestricted_fa");

  const txRows = [];
  if (p.drafted) txRows.push(`
    <tr><td class="thin">Nov ${p.drafted.year}</td><td><span class="chip ok">Drafted</span></td>
      <td>${p.drafted.year} ${esc(p.drafted.draft_type)} draft${p.drafted.pick_number ? ", pick " + p.drafted.pick_number : ""} — ${esc(p.drafted.club)}</td></tr>`);
  for (const t of p.transactions) {
    const label = { trade: "Trade", sign_fa: "FA signing", sign_rookie: "Rookie signing", delist: "Delisted", retire: "Retired", rookie_elevate: "Elevated" }[t.type] || t.type;
    const cls = t.type === "trade" ? "warn" : "plain";
    txRows.push(`
      <tr><td class="thin">${esc((t.date || "").slice(0, 4))}</td><td><span class="chip ${cls}">${esc(label)}</span></td>
        <td>${t.from_club ? esc(t.from_club) + " → " : ""}${esc(t.to_club || "")}${t.notes ? ` <span class="thin">· ${esc(t.notes.replace("; date approximate (year-level from Draftguru)", ""))}</span>` : ""}</td></tr>`);
  }
  if (current && isFA) txRows.push(`
    <tr><td class="thin">Jul 2026</td><td>${chip(current.status)}</td>
      <td>Named ${esc(STATUS[current.status].label.toLowerCase())} for end of ${current.contracted_through_year}</td></tr>`);

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
        <p class="statusline">${current ? chip(current.status) : ""}${p.rating ? `
          <span class="chip" style="background:rgba(0,0,0,0.35);border:1px solid rgba(255,255,255,0.45);color:#fff">AFL Player Rating #${p.rating.rank} · ${p.rating.rating}</span>` : ""}</p>
        <dl class="hero-facts">
          ${p.dob ? `<div><dt>Age</dt><dd>${age(p.dob)} (${esc(p.dob)})</dd></div>` : ""}
          ${p.height_cm ? `<div><dt>Height</dt><dd>${p.height_cm} cm</dd></div>` : ""}
          ${p.jumper_number ? `<div><dt>Guernsey</dt><dd>#${p.jumper_number}</dd></div>` : ""}
          ${p.drafted ? `<div><dt>Drafted</dt><dd>${p.drafted.year} ${esc(p.drafted.draft_type)}${p.drafted.pick_number ? " · Pick " + p.drafted.pick_number : ""}</dd></div>
          <div><dt>Drafted by</dt><dd>${esc(p.drafted.club)}</dd></div>` : ""}
          ${current && current.contracted_through_year ? `<div><dt>Contracted through</dt><dd>${current.contracted_through_year}</dd></div>` : ""}
        </dl>
      </div>
    </div>
    <div class="cols">
      <div>
        ${current ? `<div class="card">
          <h3>Contract status</h3>
          <p class="sub">Status by season — ListTrac tracks status, never dollars.</p>
          ${timelineHTML(p)}
        </div>` : ""}
        <div class="card">
          <h3>Transactions</h3>
          <div class="tablewrap"><table>
            <thead><tr><th>When</th><th>Type</th><th>Detail</th></tr></thead>
            <tbody>${txRows.join("") || `<tr><td colspan="4" class="thin">No recorded movements — original-list player.</td></tr>`}</tbody>
          </table></div>
        </div>
        ${p.rating_history && p.rating_history.length ? `
        <div class="card">
          <h3>AFL Player Rating history</h3>
          <p class="sub">Champion Data season rating and league rank, ${p.rating_history[0].year}–${p.rating_history[p.rating_history.length - 1].year}.</p>
          ${sparkline(p.rating_history)}
          <div class="tablewrap"><table>
            <thead><tr><th class="num">Season</th><th>Club</th><th class="num">Rating</th><th class="num">League rank</th></tr></thead>
            <tbody>${p.rating_history.slice().reverse().map(s => `
              <tr><td class="num">${s.year}</td><td class="thin">${esc(s.team)}</td>
                <td class="num"><b>${s.rating}</b></td><td class="num">${s.rank ? "#" + s.rank : "—"}</td></tr>`).join("")}
            </tbody>
          </table></div>
          <p class="srcline">Official AFL Player Ratings, powered by Champion Data.</p>
        </div>` : ""}
        ${p.contract_status.length > 1 ? `
        <div class="card">
          <h3>Contract status history</h3>
          <p class="sub">How ListTrac has tracked ${esc(p.first_name)}'s status over time.</p>
          <div class="tablewrap"><table>
            <thead><tr><th>Recorded</th><th>Club</th><th>Status</th><th class="num">Through</th></tr></thead>
            <tbody>${p.contract_status.map(cs => `
              <tr><td class="thin">${esc(cs.last_confirmed_date || "")}</td>
                <td>${esc(cs.club)}</td><td>${chip(cs.status)}${cs.is_current ? "" : ` <span class="thin">superseded</span>`}</td>
                <td class="num">${cs.contracted_through_year ?? "—"}</td></tr>`).join("")}
            </tbody>
          </table></div>
        </div>` : ""}
      </div>
      <aside class="rail">
        <div class="card">
          <p class="eyebrow">${esc(p.last_name)} in the news</p>
          ${news.length ? news.slice(0, 8).map(n => `
            <div class="spot">
              <span class="src">${esc(n.source)} <span class="thin">· ${timeAgo(n.published)}</span></span>
              <p><a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a></p>
            </div>`).join("") : `<p class="thin">No recent movement coverage.</p>`}
        </div>
        ${sameBoat}
      </aside>
    </div>`;
}

async function draftView(year, draftType = "national", chrome = "") {
  let picks = [], picksErr = "";
  const intel = await api("/api/pick-intel").catch(() => null);
  try { picks = await api(`/drafts/${year}?draft_type=${encodeURIComponent(draftType)}`); }
  catch { picksErr = `No ${draftType.replace("_", "-")} draft recorded for ${year}.`; }
  let trades = { players: [], picks: [] };
  try { trades = await api(`/trades/${year}`); } catch { /* none that year */ }

  const years = [];
  for (let y = 2026; y >= 1986; y--) years.push(y);
  view.innerHTML = `${chrome}
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
      <p class="srcline">Hover a row for the pick's historical outcome profile ·
        <a href="#/trades/history/${esc(year)}">full ${esc(year)} trade period →</a></p>`}
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
    </div>` : ""}`;

  document.getElementById("dyear").addEventListener("change", e => location.hash = `#/draft/history/${e.target.value}/${document.getElementById("dtype").value}`);
  document.getElementById("dtype").addEventListener("change", e => location.hash = `#/draft/history/${document.getElementById("dyear").value}/${e.target.value}`);
}

async function tradesView(year, chrome = "") {
  let trades = { players: [], picks: [] };
  let empty = "";
  try { trades = await api(`/trades/${year}`); } catch { empty = `No trade data recorded for ${year}.`; }
  const years = [];
  for (let y = 2025; y >= 1986; y--) years.push(y);
  view.innerHTML = `${chrome}
    <div class="controls">
      <label class="eyebrow" style="margin:0" for="tyear">Trade period</label>
      <select id="tyear">${years.map(y => `<option ${y === +year ? "selected" : ""}>${y}</option>`).join("")}</select>
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
      <p class="srcline"><a href="#/draft/history/${esc(year)}">see the resulting draft board →</a></p>
    </div>`}`;
  document.getElementById("tyear").addEventListener("change", e => location.hash = `#/trades/history/${e.target.value}`);
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
      <p class="sub">${players.length} players.</p>
      <div class="tablewrap"><table>
        <thead><tr><th>Player</th><th>Club</th><th class="num">Age</th><th>Status</th></tr></thead>
        <tbody>${players.map(x => `
          <tr><td>${playerLink(x)}</td><td class="thin">${esc(x.club)}</td>
            <td class="num">${age(x.dob)}</td><td>${chip(x.contract_status)}</td></tr>`).join("")}
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

const draftChrome = act => `<div class="subtabs">
  <a href="#/draft" class="${act === "order" ? "active" : ""}">Projected order</a>
  <a href="#/draft/mock" class="${act === "mock" ? "active" : ""}">Mock draft</a>
  <a href="#/draft/history/2025" class="${act === "history" ? "active" : ""}">Draft history</a>
</div>`;
const tradesChrome = act => `<div class="subtabs">
  <a href="#/trades" class="${act === "machine" ? "active" : ""}">Trade machine</a>
  <a href="#/trades/history/2025" class="${act === "history" ? "active" : ""}">Trade history</a>
</div>`;
const go = hash => { location.replace(hash); return Promise.resolve(); };

const routes = [
  [/^#?\/?$/,                       () => landingView()],
  [/^#\/clubs$/,                    () => clubsView()],
  [/^#\/players$/,                  () => playersView()],
  [/^#\/draft$/,                    () => draftOrderView(draftChrome("order"))],
  [/^#\/draft\/mock$/,              () => mockDraftView(draftChrome("mock"))],
  [/^#\/draft\/history\/(\d{4})(?:\/(\w+))?$/, m => draftView(m[1], m[2] || "national", draftChrome("history"))],
  [/^#\/trades$/,                   () => tradeMachineView(tradesChrome("machine"))],
  [/^#\/trades\/history\/(\d{4})$/, m => tradesView(m[1], tradesChrome("history"))],
  // legacy hashes redirect into the hubs
  [/^#\/draft-order$/,              () => go("#/draft")],
  [/^#\/mock-draft$/,               () => go("#/draft/mock")],
  [/^#\/trade-machine$/,            () => go("#/trades")],
  [/^#\/trades\/(\d{4})$/,          m => go(`#/trades/history/${m[1]}`)],
  [/^#\/draft\/(\d{4})(?:\/(\w+))?$/, m => go(`#/draft/history/${m[1]}${m[2] ? "/" + m[2] : ""}`)],
  [/^#\/club\/([A-Za-z]+)$/,        m => clubView(m[1])],
  [/^#\/player\/(\d+)$/,            m => playerView(m[1])],
  [/^#\/free-agents(?:\/(\w+))?$/,  m => faView(m[1] || "all")],
  [/^#\/search\/(.+)$/,             m => searchView(decodeURIComponent(m[1]))],
];

async function route() {
  const hash = location.hash || "#/";
  document.querySelectorAll("#nav a").forEach(a => {
    const href = a.getAttribute("href");
    a.classList.toggle("active", href === "#/"
      ? (hash === "#/" || hash === "" || hash === "#")
      : hash === href || hash.startsWith(href + "/"));
  });
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
