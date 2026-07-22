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

/* Star / popularity button. Renders a placeholder; mountStars() wires counts
   + toggle after the view renders. One star per person, tracked in localStorage. */
const starButton = (kind, id, label = "") => id
  ? `<button class="starbtn" data-kind="${esc(kind)}" data-id="${esc(String(id))}" hidden>
       <span class="star-ico">★</span><span class="starcount"></span>${label ? ` <span class="thin">${esc(label)}</span>` : ""}</button>`
  : "";

async function mountStars() {
  const btns = [...document.querySelectorAll(".starbtn:not([data-mounted])")];
  if (!btns.length) return;
  const byKind = {};
  btns.forEach(b => (byKind[b.dataset.kind] = byKind[b.dataset.kind] || []).push(b.dataset.id));
  for (const kind of Object.keys(byKind)) {
    const data = await api(`/api/stars?kind=${kind}&ids=${encodeURIComponent([...new Set(byKind[kind])].join(","))}`).catch(() => null);
    btns.filter(b => b.dataset.kind === kind).forEach(b => {
      b.dataset.mounted = "1";
      if (!data || !data.configured) return;  // store not set up — leave hidden
      const starredKey = `starred:${kind}:${b.dataset.id}`;
      const setUI = (count, on) => {
        b.hidden = false;
        b.classList.toggle("on", on);
        b.querySelector(".starcount").textContent = count > 0 ? count : "";
        b.title = on ? "Remove your star" : "Star this";
      };
      let count = (data.counts || {})[b.dataset.id] || 0;
      let on = localStorage.getItem(starredKey) === "1";
      setUI(count, on);
      b.addEventListener("click", async () => {
        on = !on; count += on ? 1 : -1;
        localStorage.setItem(starredKey, on ? "1" : "0");
        setUI(Math.max(0, count), on);
        const res = await api("/api/star", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ kind, id: b.dataset.id, delta: on ? 1 : -1 }) }).catch(() => null);
        if (res && typeof res.count === "number") setUI(res.count, on);
      });
    });
  }
}

const SOCIAL_ICON = { x: "𝕏", instagram: "IG", tiktok: "TT", website: "WWW" };
const socialLinks = (links, extraClass = "") => {
  const order = ["x", "instagram", "tiktok", "website"];
  const items = order.filter(k => links[k]).map(k =>
    `<a class="social ${k}" href="${esc(links[k])}" target="_blank" rel="noopener" aria-label="${k}">${SOCIAL_ICON[k]}</a>`);
  return items.length ? `<span class="socials ${extraClass}">${items.join("")}</span>` : "";
};
const playerSocialSearch = name => socialLinks({
  x: `https://x.com/search?q=${encodeURIComponent(name + " AFL")}`,
  instagram: `https://www.instagram.com/explore/search/keyword/?q=${encodeURIComponent(name)}`,
  tiktok: `https://www.tiktok.com/search?q=${encodeURIComponent(name + " AFL")}`,
});

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

/* Guernsey icons — our own hand-drawn jumper tiles, one per club, matching
   each side's real design and full colour scheme (base + inner markup on a
   fixed 24x28 canvas). Drawn from scratch: no official logos, crests or
   third-party assets — just the colours and patterns of the jumper itself. */
const CLUB_GUERNSEY = {
  // Crows — navy with red/gold radiating centre stripes
  ADE: { b: "#002B5C", in: `<rect x="9" width="6" height="28" fill="#FFD200"/><rect x="7" width="2" height="28" fill="#E4002B"/><rect x="15" width="2" height="28" fill="#E4002B"/>` },
  // Lions — maroon with royal-blue centre panel, gold trim
  BRI: { b: "#6A0F2E", in: `<rect x="9" width="6" height="28" fill="#0C4DA2"/><rect x="8" width="1" height="28" fill="#F2C14E"/><rect x="15" width="1" height="28" fill="#F2C14E"/>` },
  // Blues — solid navy
  CAR: { b: "#0A1F33", in: `` },
  // Magpies — black & white vertical stripes
  COL: { b: "#0A0A0A", in: `<rect x="3.4" width="3.4" height="28" fill="#fff"/><rect x="10.3" width="3.4" height="28" fill="#fff"/><rect x="17.2" width="3.4" height="28" fill="#fff"/>` },
  // Bombers — red with black sash
  ESS: { b: "#C7132B", in: `<path d="M-4,28 L24,0" stroke="#0A0A0A" stroke-width="8"/>` },
  // Dockers — purple with white anchor chevrons
  FRE: { b: "#2A1A54", in: `<polyline points="0,6 12,15 24,6" fill="none" stroke="#fff" stroke-width="3"/><polyline points="0,13 12,22 24,13" fill="none" stroke="#fff" stroke-width="3"/>` },
  // Cats — navy & white hoops
  GEE: { b: "#11315C", in: `<rect y="4.5" width="24" height="3" fill="#fff"/><rect y="12.5" width="24" height="3" fill="#fff"/><rect y="20.5" width="24" height="3" fill="#fff"/>` },
  // Suns — red with gold sash, navy edge
  GCS: { b: "#D2222A", in: `<path d="M-4,28 L24,0" stroke="#FFC72C" stroke-width="7"/><path d="M3,29 L27,5" stroke="#0C2340" stroke-width="1.6"/>` },
  // Giants — charcoal with orange flash
  GWS: { b: "#3A3A3C", in: `<path d="M-4,28 L24,0" stroke="#F47920" stroke-width="8"/>` },
  // Hawks — brown & gold vertical stripes
  HAW: { b: "#4A1D03", in: `<rect x="3.4" width="3.4" height="28" fill="#F4B41A"/><rect x="10.3" width="3.4" height="28" fill="#F4B41A"/><rect x="17.2" width="3.4" height="28" fill="#F4B41A"/>` },
  // Demons — navy with red V
  MEL: { b: "#0B1A38", in: `<polyline points="0,5 12,16 24,5" fill="none" stroke="#C7132B" stroke-width="5"/>` },
  // Kangaroos — royal blue & white vertical stripes
  NM:  { b: "#0A3EA0", in: `<rect x="3.4" width="3.4" height="28" fill="#fff"/><rect x="10.3" width="3.4" height="28" fill="#fff"/><rect x="17.2" width="3.4" height="28" fill="#fff"/>` },
  // Power — black with teal + white "prison bar" chevrons
  PA:  { b: "#0A0A0A", in: `<polyline points="0,5 12,16 24,5" fill="none" stroke="#00A9B7" stroke-width="4.5"/><polyline points="0,11 12,22 24,11" fill="none" stroke="#fff" stroke-width="1.8"/>` },
  // Tigers — black with yellow sash
  RIC: { b: "#151515", in: `<path d="M-4,28 L24,0" stroke="#FFD200" stroke-width="8"/>` },
  // Saints — white with red & black vertical tricolour
  STK: { b: "#FFFFFF", in: `<rect x="8" width="3" height="28" fill="#ED1B2E"/><rect x="13" width="3" height="28" fill="#0A0A0A"/>` },
  // Swans — red with white V yoke
  SYD: { b: "#E1121C", in: `<polyline points="0,5 12,16 24,5" fill="none" stroke="#fff" stroke-width="5"/>` },
  // Devils — green with gold band, red edges
  TAS: { b: "#0E5A3C", in: `<rect y="10.5" width="24" height="6" fill="#F0C244"/><rect y="9" width="24" height="1.5" fill="#C7132B"/><rect y="16.5" width="24" height="1.5" fill="#C7132B"/>` },
  // Bulldogs — royal blue / white / red horizontal tricolour
  WB:  { b: "#0A47A1", in: `<rect y="9.33" width="24" height="9.33" fill="#fff"/><rect y="18.66" width="24" height="9.34" fill="#D2222A"/>` },
  // Eagles — royal blue with gold V
  WCE: { b: "#062F87", in: `<polyline points="0,5 12,16 24,5" fill="none" stroke="#F2A900" stroke-width="5"/>` },
};
let _gsyId = 0;
function guernsey(abbrev, size = 22) {
  const c = CLUB_GUERNSEY[String(abbrev || "").toUpperCase()] || { b: "#556270", in: "" };
  const id = "gsy" + (++_gsyId), W = 24, H = 28;
  return `<svg class="gsy" width="${size}" height="${(size * H / W).toFixed(1)}" viewBox="0 0 ${W} ${H}" aria-hidden="true">`
    + `<defs><clipPath id="${id}"><rect x="1" y="1" width="${W - 2}" height="${H - 2}" rx="4"/></clipPath></defs>`
    + `<g clip-path="url(#${id})"><rect width="${W}" height="${H}" fill="${c.b}"/>${c.in}</g>`
    + `<rect x="1" y="1" width="${W - 2}" height="${H - 2}" rx="4" fill="none" stroke="rgba(0,0,0,0.3)"/></svg>`;
}
// guernsey + club name, optionally linked
const clubTag = (abbrev, name, link = true) => {
  const g = guernsey(abbrev, 20);
  const label = link && abbrev ? `<a href="#/club/${esc(abbrev)}">${esc(name)}</a>` : esc(name);
  return `<span class="clubtag">${g}${label}</span>`;
};
// Champion Data team code (ratings/fantasy feeds) -> our club abbreviation
const CD_ABBR = {
  ADEL: "ADE", BL: "BRI", CARL: "CAR", COLL: "COL", ESS: "ESS", FRE: "FRE",
  GCFC: "GCS", GEEL: "GEE", GWS: "GWS", HAW: "HAW", MELB: "MEL", NMFC: "NM",
  PORT: "PA", RICH: "RIC", STK: "STK", SYD: "SYD", WB: "WB", WCE: "WCE",
};
const teamTag = cd => { const a = CD_ABBR[String(cd || "").toUpperCase()] || cd; return clubTag(a, a); };

/* Draft-pathway icons — our own shield tiles for a prospect's championship
   zone or academy. Zones get their own colour; academy-tied prospects take
   their club's base colour + code, so you can see who has priority access. */
const ACADEMY_CLUB = { "brisbane academy": "BRI", "gws academy": "GWS", "gold coast academy": "GCS", "sydney academy": "SYD" };
const STATE_META = {
  "vic metro": { code: "VM", c: "#1F3A93" }, "vic country": { code: "VC", c: "#1E7A46" },
  "south australia": { code: "SA", c: "#C8102E" }, "western australia": { code: "WA", c: "#C08A1E" },
  "allies": { code: "ALL", c: "#6A2C91" }, "tasmania": { code: "TAS", c: "#0E7C4B" },
  "northern territory": { code: "NT", c: "#B5651D" },
};
function pathwayIcon(stateTeam, size = 22) {
  const key = String(stateTeam || "").toLowerCase().trim();
  let code, color;
  if (ACADEMY_CLUB[key]) { const ab = ACADEMY_CLUB[key]; code = ab; color = (CLUB_GUERNSEY[ab] || {}).b || "#3a4750"; }
  else { const m = STATE_META[key]; code = m ? m.code : (stateTeam || "?").split(" ").map(w => w[0]).join("").slice(0, 3).toUpperCase(); color = m ? m.c : "#3a4750"; }
  const W = 22, H = 26, fs = code.length >= 3 ? 7 : 9;
  return `<svg class="pway" width="${size}" height="${(size * H / W).toFixed(1)}" viewBox="0 0 ${W} ${H}" aria-hidden="true">`
    + `<path d="M2,2 H20 V13 C20,20 11,24 11,24 C11,24 2,20 2,13 Z" fill="${color}" stroke="rgba(0,0,0,0.22)"/>`
    + `<text x="11" y="${fs >= 9 ? 15 : 14.5}" text-anchor="middle" font-size="${fs}" font-weight="800" fill="#fff" font-family="system-ui,sans-serif">${esc(code)}</text></svg>`;
}
const pathwayTag = stateTeam => stateTeam
  ? `<span class="clubtag">${pathwayIcon(stateTeam, 18)}<span>${esc(stateTeam)}</span></span>` : "";

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
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const monthYear = d => {
  if (!d) return "";
  const [y, m] = d.split("-");
  return m ? `${MONTHS[+m - 1]} ${y}` : y;
};

async function landingView() {
  const [summary, order, newsItems, trend, clubList, adminUpdates, trendingPlayers] = await Promise.all([
    api("/api/summary"),
    api("/api/draft-order").catch(() => null),
    api("/api/news").catch(() => []),
    api("/api/trending").catch(() => []),
    api("/clubs").catch(() => []),
    api("/api/updates").catch(() => []),
    api("/api/trending-players").catch(() => []),
  ]);
  const s = summary.contract_statuses;
  const rfas = trend.filter(t => t.kind === "rfa");
  const clubColor = ab => (clubList.find(c => c.abbreviation === ab) || {}).primary_color || "#555";

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

        ${trendingPlayers.length ? `
        <div class="card">
          <h3>Trending players</h3>
          <p class="sub">Who the league is talking about right now — ranked by how often they're
            appearing in movement coverage.</p>
          <div class="trendcards">
            ${trendingPlayers.map((t, i) => `
              <a class="trendcard" href="${t.id ? `#/player/${t.id}` : "#/players"}">
                <span class="tc-rank">${i + 1}</span>
                ${guernsey(t.abbrev, 26)}
                <span class="tc-body">
                  <b>${esc(t.first_name)} ${esc(t.last_name)}</b>
                  <span class="tc-why">${t.mentions
                    ? esc(t.headline || `${t.mentions} recent mentions`)
                    : esc(t.reason || t.club || "")}</span>
                </span>
              </a>`).join("")}
          </div>
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
                <td>${clubTag(p.abbrev, p.club)}
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
                ${guernsey(c.abbreviation, 20)}
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

let draftBoardMode = "board";  // board | 1 | 2 | 3 | 4 | club

async function draftOrderView(chrome = "") {
  const [order, intel] = await Promise.all([
    api("/api/draft-order"), api("/api/pick-intel").catch(() => null)]);
  const rounds = order.rounds || [{ round: 1, picks: order.picks }];
  const allPicks = rounds.flatMap(r => r.picks);
  const cell = (n, key, suffix = "") => {
    const s = intel && intel.picks[n];
    return s ? `${s[key] ?? "—"}${s[key] != null ? suffix : ""}` : "—";
  };
  const viaChip = p => p.via
    ? ` <span class="chip warn" title="Natural slot belongs to ${esc(p.via)} — traded">via ${esc(p.via)}</span>` : "";

  // Board = full list with outcome intel. Fixed column widths keep the numeric
  // columns evenly spaced; the club column absorbs the slack. Short stat
  // headers (AA/RS/Prem) are spelled out in the legend below.
  const boardRow = p => `
    <tr><td class="num"><b>${p.pick}</b></td>
      <td class="clubcell">${clubTag(p.abbrev, p.club)}${viaChip(p)}</td>
      <td class="num">${p.round === 1 ? `${p.wins}–${p.losses}` : ""}</td>
      <td class="num thin">${p.round === 1 && p.percentage != null ? p.percentage.toFixed(1) : ""}</td>
      <td class="num">${p.dvi || "—"}</td>
      <td class="num">${cell(p.pick, "avg_games")}</td>
      <td class="num">${cell(p.pick, "aa_pct", "%")}</td>
      <td class="num">${cell(p.pick, "prem_pct", "%")}</td>
      <td class="num">${cell(p.pick, "rs_pct", "%")}</td></tr>`;
  const boardHTML = () => `
    <div class="tablewrap"><table class="drafttable">
      <colgroup><col class="c-pick"><col class="c-club"><col class="c-wl"><col class="c-pct"><col class="c-dvi">
        <col class="c-st"><col class="c-st"><col class="c-st"><col class="c-st"></colgroup>
      <thead><tr><th class="num">Pick</th><th>Owner</th><th class="num">W–L</th><th class="num">%</th>
        <th class="num">DVI</th><th class="num">Games</th>
        <th class="num" title="All-Australian rate">AA %</th>
        <th class="num" title="Premiership rate">Prem %</th>
        <th class="num" title="Rising Star nomination rate">RS %</th></tr></thead>
      <tbody>${rounds.map(r => `
        <tr><td colspan="9" class="rndhead">Round ${r.round}</td></tr>
        ${r.picks.map(boardRow).join("")}`).join("")}
      </tbody>
    </table></div>
    ${intel ? `
    <div class="statlegend">
      <p class="eyebrow">Reading this table</p>
      <dl>
        <div><dt>via</dt><dd>the pick changed hands — shown against the club that now owns it, named for the club whose ladder position sets the slot</dd></div>
        <div><dt>%</dt><dd>the club's ladder percentage — the tiebreaker that orders clubs level on wins–losses</dd></div>
        <div><dt>DVI</dt><dd>the pick's value on the AFL's official Draft Value Index — the points currency used to match academy and father-son bids</dd></div>
        <div><dt>Games</dt><dd>average career games played by every player ever taken at that pick</dd></div>
        <div><dt>AA %</dt><dd>share of players taken at that pick who made an All-Australian team</dd></div>
        <div><dt>Prem %</dt><dd>share who played in a premiership</dd></div>
        <div><dt>RS %</dt><dd>share who earned a Rising Star nomination in their early seasons</dd></div>
      </dl>
      <p class="thin" style="font-size:11.5px;margin:8px 0 0">Outcome stats cover the
        ${intel.cohort.from}–${intel.cohort.to} drafts — more recent draftees are still mid-career
        and would drag the numbers down.</p>
    </div>` : ""}`;

  // Single round — clean pick / club / via / DVI
  const roundHTML = n => {
    const r = rounds.find(x => x.round === n) || { picks: [] };
    const total = r.picks.reduce((s, p) => s + (p.dvi || 0), 0);
    return `<div class="tablewrap"><table>
      <thead><tr><th class="num">Pick</th><th>Club</th><th>From</th><th class="num">DVI pts</th></tr></thead>
      <tbody>${r.picks.map(p => `
        <tr><td class="num"><b>${p.pick}</b></td>
          <td>${clubTag(p.abbrev, p.club)}</td>
          <td class="thin">${p.via ? "received from " + esc(p.via) : ""}</td>
          <td class="num">${p.dvi || "—"}</td></tr>`).join("")}
        <tr class="totrow"><td></td><td colspan="2">Round ${n} — ${r.picks.length} picks</td>
          <td class="num"><b>${total.toLocaleString()}</b></td></tr>
      </tbody>
    </table></div>`;
  };

  // By club — draft capital summary
  const clubHTML = () => {
    const byClub = {};
    for (const p of allPicks) {
      const k = p.abbrev || p.club;
      (byClub[k] = byClub[k] || { abbrev: p.abbrev, club: p.club, picks: [], pts: 0 });
      byClub[k].picks.push(p.pick); byClub[k].pts += p.dvi || 0;
    }
    const clubs = Object.values(byClub).sort((a, b) => b.pts - a.pts);
    const maxPts = Math.max(...clubs.map(c => c.pts), 1);
    return `<p class="sub">Every 2026 pick a club currently holds across all four rounds, and its total Draft Value Index capital. Sorted by draft capital.</p>
      <div class="tablewrap"><table>
        <thead><tr><th>Club</th><th>Picks</th><th class="num">Total DVI</th></tr></thead>
        <tbody>${clubs.map((c, i) => `
          <tr><td>${clubTag(c.abbrev, c.club)}</td>
            <td class="thin">${c.picks.sort((a, b) => a - b).join(", ")}</td>
            <td class="num"><span class="dvibar" style="--w:${(c.pts / maxPts * 100).toFixed(1)}%"><b>${c.pts.toLocaleString()}</b></span></td></tr>`).join("")}
        </tbody>
      </table></div>`;
  };

  const renderBody = () =>
    draftBoardMode === "board" ? boardHTML()
      : draftBoardMode === "club" ? clubHTML()
        : roundHTML(+draftBoardMode);

  const TABS = [["board", "Board"], ["1", "R1"], ["2", "R2"], ["3", "R3"], ["4", "R4"], ["club", "By club"]];
  view.innerHTML = `${chrome}
    <div class="card">
      <h3>Projected 2026 national draft order</h3>
      <p class="sub">Live reverse ladder, ${order.as_of_round} games in, with all
        ${order.traded_slots} already-traded 2026 picks applied ("via" / "from" = the club whose natural slot it is).</p>
      <div class="draftviews" role="tablist">
        ${TABS.map(([m, l]) => `<button data-m="${m}" role="tab">${l}</button>`).join("")}
      </div>
      <div id="draftbody">${renderBody()}</div>
    </div>`;
  const body = view.querySelector("#draftbody");
  const buttons = [...view.querySelectorAll(".draftviews button")];
  const syncTabs = () => buttons.forEach(b => {
    const on = b.dataset.m === draftBoardMode;
    b.classList.toggle("on", on); b.setAttribute("aria-selected", on);
  });
  buttons.forEach(b => b.addEventListener("click", () => {
    if (draftBoardMode === b.dataset.m) return;
    draftBoardMode = b.dataset.m; syncTabs(); body.innerHTML = renderBody();
  }));
  syncTabs();
}

/* ---------- interactive mock draft ---------- */

const MOCK_KEY = "mock_draft_2026";
const loadMock = () => {
  // a shared board in the URL (?d=) beats whatever's saved locally
  const m = location.hash.match(/[?&]d=([^&]+)/);
  if (m) { try { return JSON.parse(decodeURIComponent(escape(atob(m[1].replace(/-/g, "+").replace(/_/g, "/"))))).filter(Boolean); } catch { /* fall through */ } }
  try { return (JSON.parse(localStorage.getItem(MOCK_KEY)) || []).filter(Boolean); } catch { return []; }
};
const saveMock = events => localStorage.setItem(MOCK_KEY, JSON.stringify(events));
const encodeMock = events => btoa(unescape(encodeURIComponent(JSON.stringify(events)))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

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

/* how many picks are actually made — controls whether share/download is live */
const shownAny = sim => sim.rows.some(r => !r.absorbed && r.assigned);

/* Shareable mock-draft graphic: the first-round board, club-coloured, matched
   bids marked. Two columns so a full round fits one social card. */
function mockSVG(sim) {
  const picks = [];
  let n = 0;
  for (const r of sim.rows) {
    if (r.absorbed) continue;
    n++;
    if (!r.assigned && n > 30) break;
    picks.push({ n, club: r.club, p: r.assigned, matched: r.kind === "matched" });
  }
  const shown = picks.filter(p => p.p).length ? picks.filter((p, i) => p.p || i < 24) : picks.slice(0, 24);
  const W = 1080, H = 1350, cols = 2, per = Math.ceil(shown.length / cols);
  const colW = 480, rowH = 40, top = 210, gap = 60;
  const rows = shown.map((pk, i) => {
    const col = Math.floor(i / per), row = i % per;
    const x = 40 + col * (colW + gap), y = top + row * rowH;
    const c = pk.club.primary_color || "#555";
    const name = pk.p ? pk.p.name : "—";
    return `<g transform="translate(${x} ${y})">
      <rect x="0" y="0" width="${colW}" height="34" rx="6" fill="#182129"/>
      <rect x="0" y="0" width="6" height="34" rx="3" fill="${c}"/>
      <text x="20" y="24" font-size="19" font-weight="800" fill="#BF4226" font-family="system-ui,sans-serif">${pk.n}</text>
      <text x="58" y="24" font-size="16" font-weight="800" fill="#93A1A8" font-family="system-ui,sans-serif">${esc(pk.club.abbrev || "")}</text>
      <text x="128" y="24" font-size="18" font-weight="600" fill="#E6EBE9" font-family="system-ui,sans-serif">${esc(name.length > 24 ? name.slice(0, 23) + "…" : name)}</text>
      ${pk.matched ? `<circle cx="${colW - 16}" cy="17" r="5" fill="#E07A8B"/>` : ""}
    </g>`;
  }).join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
    <rect width="${W}" height="${H}" fill="#10171C"/>
    <rect width="${W}" height="130" fill="#131c24"/><rect y="130" width="${W}" height="5" fill="#BF4226"/>
    <text x="40" y="66" font-size="42" font-weight="800" fill="#F2F4F3" font-family="system-ui,sans-serif">List<tspan fill="#BF4226">Trac</tspan></text>
    <text x="40" y="104" font-size="22" font-weight="700" fill="#93A1A8" font-family="system-ui,sans-serif" letter-spacing="1">MY 2026 MOCK DRAFT · FIRST ROUND</text>
    ${rows}
    <text x="40" y="${H - 34}" font-size="20" fill="#55636D" font-family="system-ui,sans-serif">list-trac.vercel.app · ● = matched academy/father-son bid</text>
  </svg>`;
}

async function downloadMock(sim) {
  const msg = document.getElementById("md-msg");
  try {
    const png = await svgToPng(mockSVG(sim));
    const a = document.createElement("a");
    a.href = URL.createObjectURL(png); a.download = "listtrac-mock-draft-2026.png"; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    if (msg) msg.textContent = "Board downloaded.";
  } catch { if (msg) msg.textContent = "Couldn't render the board here."; }
}

async function shareMock(sim, events) {
  const msg = document.getElementById("md-msg");
  const link = `${location.origin}/#/draft/mock?d=${encodeMock(events)}`;
  try {
    const png = await svgToPng(mockSVG(sim));
    const file = new File([png], "listtrac-mock-draft.png", { type: "image/png" });
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      await navigator.share({ title: "My 2026 AFL mock draft", text: "My 2026 AFL mock draft — built on ListTrac", files: [file] });
      return;
    }
    if (navigator.share) { await navigator.share({ title: "My 2026 AFL mock draft", url: link }); return; }
  } catch { /* clipboard fallback */ }
  try { await navigator.clipboard.writeText(link); if (msg) msg.textContent = "Share link copied — it rebuilds your exact board."; }
  catch { if (msg) msg.textContent = link; }
}

async function prospectsView(year = 2027) {
  const [runway, pool] = await Promise.all([
    api("/api/prospect-runway").catch(() => []),
    api(`/api/prospects?year=${year}`).catch(() => null),
  ]);
  const stageLabel = { u18: "U18 championships", u16: "U16 championships" };
  view.innerHTML = `${draftChrome("prospects")}
    <div class="card">
      <h3>Draft prospect runway</h3>
      <p class="sub">Three draft classes in the pipeline. The 2026 class is this year's U18 championships
        pool; 2027 and 2028 are the full pathway pools — every Coates Talent League and national-
        championship player eligible for that draft, classified by date of birth. Award winners are
        tagged; it's a wide field this far out, not a ranking. Click any prospect for their full
        playing history across the Coates Talent League, VFL/SANFL/WAFL and national championships.</p>
      <div class="runway">
        ${runway.map(r => `
          <a class="runwaycard ${r.year === year ? "on" : ""}" href="#/draft/prospects/${r.year}">
            <div class="rw-year">${r.year}<span>draft</span></div>
            <div class="rw-stage">${esc(stageLabel[r.stage] || r.stage)}</div>
            <div class="rw-count">${r.forming ? "class forming" : r.count + " prospects"}</div>
            ${r.top.length ? `<div class="rw-top">${r.top.map(t => esc(t.name.split(" ").slice(-1)[0])).join(" · ")}</div>` : ""}
          </a>`).join("")}
      </div>
    </div>
    ${pool ? prospectPoolCard(pool, year) : `<div class="card"><p class="thin">No prospect pool for ${year}.</p></div>`}`;

  const psearch = document.getElementById("poolsearch");
  if (psearch) {
    const pstate = document.getElementById("poolstate");
    const prows = [...document.querySelectorAll("#poollist tr")];
    const pcount = document.getElementById("poolcount");
    const applyPool = () => {
      const q = psearch.value.toLowerCase().trim(), st = pstate.value;
      let shown = 0;
      prows.forEach(r => {
        const ok = (!q || r.dataset.name.includes(q)) && (!st || r.dataset.state === st);
        r.hidden = !ok; if (ok) shown++;
      });
      pcount.textContent = `${shown} of ${prows.length} shown`;
    };
    psearch.addEventListener("input", applyPool);
    pstate.addEventListener("change", applyPool);
    applyPool();
  }
}

async function prospectProfileView(name) {
  const p = await api(`/api/prospect?name=${encodeURIComponent(name)}`).catch(() => null);
  if (!p) { view.innerHTML = `<p class="error">Prospect not found.</p>`; return; }
  const initials = (p.state_team || "").split(" ").map(w => w[0]).join("").slice(0, 3).toUpperCase();
  const stageLabel = { u18: "2026 draft class · U18", u16: `${p.draft_year} draft class · U16` };
  const hist = p.history || [];

  view.innerHTML = `
    <p class="thin" style="margin:16px 0 0"><a href="#/draft/prospects/${p.draft_year}">← ${p.draft_year} prospects</a></p>
    <div class="hero" style="--hero-a:#232f38;--hero-b:#2d3a44;--hero-trim:var(--accent)">
      <div class="hero-inner">
        <p class="club-line">${p.state_team ? pathwayIcon(p.state_team, 20) : ""}${esc(p.state_team || "")}${p.position ? " · " + esc(p.position) : ""}</p>
        <h2>${esc(p.name)}</h2>
        <p class="statusline">
          <span class="chip plain" style="background:rgba(0,0,0,0.35);border:1px solid rgba(255,255,255,0.45);color:#fff">${esc(stageLabel[p.stage] || p.draft_year + " draft")}</span>
          ${p.award ? `<span class="chip" style="background:#f5e3a8;color:#7a5c00">${esc(p.award)}</span>` : ""}
          ${p.tie ? `<span class="chip warn">${esc(p.tie)}</span>` : ""}
        </p>
        <dl class="hero-facts">
          ${p.rank && p.stage === "u18" ? `<div><dt>Consensus rank</dt><dd>#${p.rank}</dd></div>` : ""}
          ${p.position ? `<div><dt>Position</dt><dd>${esc(p.position)}</dd></div>` : ""}
          <div><dt>State / academy</dt><dd>${esc(p.state_team || "")}</dd></div>
          <div><dt>Draft class</dt><dd>${p.draft_year}</dd></div>
          ${p.headline ? `<div><dt>Latest form</dt><dd>${p.headline.avg_disposals ?? "—"} disp · ${esc(p.headline.season)} ${esc(p.headline.league)}</dd></div>` : ""}
        </dl>
      </div>
    </div>
    <div class="card">
      <h3>Playing history</h3>
      <p class="sub">Games across the Coates Talent League, national championships, VFL/SANFL/WAFL and academy football — including senior state-league games as they step up.</p>
      <p class="sub" style="margin-top:-6px;font-size:11.5px">Per-game averages.</p>
      ${hist.length ? `
      <div class="tablewrap"><table>
        <thead><tr><th>Season</th><th>Competition</th><th>Team</th><th class="num">GP</th>
          <th class="num">Disp</th><th class="num">Kick</th><th class="num">HB</th><th class="num">Mark</th>
          <th class="num">Tack</th><th class="num">Clr</th><th class="num">I50</th><th class="num">Goal</th></tr></thead>
        <tbody>${hist.map(r => {
          const per = (t) => (t == null || !r.gamesplayed) ? "—" : (t / r.gamesplayed).toFixed(1);
          return `
          <tr><td>${esc(r.season)}</td><td>${esc(r.league)}</td><td class="thin">${esc(r.team)}</td>
            <td class="num">${r.gamesplayed ?? ""}</td>
            <td class="num"><b>${per(r.disposals)}</b></td><td class="num">${per(r.kicks)}</td>
            <td class="num">${per(r.handballs)}</td><td class="num">${per(r.marks)}</td>
            <td class="num">${per(r.tackles)}</td><td class="num">${per(r.clr)}</td>
            <td class="num">${per(r.i)}</td><td class="num">${per(r.goals)}</td></tr>`;
        }).join("")}
        </tbody>
      </table></div>`
      : `<p class="thin">No recorded games yet — this profile fills in as ${esc(p.name.split(" ")[0])} plays underage and state-league football.</p>`}
    </div>`;
}

/* Award text -> honour chip class. Top honours (championship medals, AA
   captaincy) get the gold treatment; state/team MVPs a lighter one. */
function honourChip(award) {
  if (!award) return "";
  const top = /Kevin Sheehan|Alan McLean|captain|All-Australian/i.test(award);
  return `<span class="honour-chip ${top ? "gold" : ""}">${esc(award)}</span>`;
}

function prospectPoolCard(pool, year) {
  const ps = pool.prospects || [];
  const src = pool.sources || {};
  const srcLink = "";  // provenance lives in the footer acknowledgements

  if (pool.forming || !ps.length) {
    return `<div class="card">
      <h3>${year} class — forming</h3>
      <p class="sub">${esc(pool.note || "")}</p>
      ${pool.pool_results ? `<div class="tablewrap"><table>
        <thead><tr><th>Pool</th><th>Winner</th></tr></thead>
        <tbody>${pool.pool_results.map(r => `<tr><td class="thin">Pool ${esc(r.pool)}</td><td>${esc(r.winner)}</td></tr>`).join("")}</tbody>
      </table></div>` : ""}${srcLink}
    </div>`;
  }

  // U18 (2026) has a genuine ranking (Twomey/RTP); keep the numbered ladder.
  if ((pool.stage || "u18") === "u18") {
    const ranked = [...ps].sort((a, b) => (a.rank || 999) - (b.rank || 999));
    return `<div class="card">
      <h3>${year} prospect pool <span class="thin" style="font-weight:400">· ${ranked.length}</span></h3>
      <p class="sub">${esc(pool.note || "")}</p>
      <div class="tablewrap"><table>
        <thead><tr><th class="num">#</th><th>Player</th><th>State / academy</th><th>Position</th></tr></thead>
        <tbody>${ranked.map(p => `
          <tr${p.bottom_ager ? ' class="thin"' : ""}><td class="num"><b>${p.rank ?? "—"}</b></td>
            <td><a href="#/prospect/${encodeURIComponent(p.name)}">${esc(p.name)}</a>${p.tie ? ` <span class="chip warn" style="font-size:9px">${esc(p.tie)}</span>` : ""}${p.bottom_ager ? ` <span class="chip ufa" style="font-size:9px">→ ${p.true_class} bottom-age</span>` : ""}</td>
            <td>${pathwayTag(p.state_team)}</td>
            <td class="thin">${esc(p.position || "")}</td></tr>`).join("")}
        </tbody>
      </table></div>
      <p class="thin" style="font-size:12px;margin-top:8px">Players tagged <span class="chip ufa" style="font-size:9px">bottom-age</span>
        played up a level and are draft-eligible in their tagged year, not ${year}.</p>${srcLink}
    </div>`;
  }

  // 2027/2028: the full potential-draftee pool — every pathway player,
  // searchable and filterable by state, honour winners flagged (not ranked).
  const order = [...ps].sort((a, b) =>
    (a.rank || 999) - (b.rank || 999) || (b.games || 0) - (a.games || 0) || a.name.localeCompare(b.name));
  const states = [...new Set(order.map(p => p.state_team).filter(Boolean))].sort();
  return `<div class="card">
    <h3>${year} draft pool <span class="thin" style="font-weight:400">· ${order.length} players</span></h3>
    <p class="sub">${esc(pool.note || "")}</p>
    <div class="poolctl">
      <input id="poolsearch" class="poolsearch" type="search" placeholder="Search ${order.length} prospects…" autocomplete="off">
      <select id="poolstate" class="poolstate"><option value="">All states / pathways</option>${states.map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join("")}</select>
      <span class="thin" id="poolcount"></span>
    </div>
    <div class="tablewrap"><table>
      <thead><tr><th>Player</th><th>State / pathway</th><th>Club</th><th>Pos</th><th class="num">GP</th></tr></thead>
      <tbody id="poollist">${order.map(p => `
        <tr data-name="${esc((p.name || "").toLowerCase())}" data-state="${esc(p.state_team || "")}">
          <td><a href="#/prospect/${encodeURIComponent(p.name)}">${esc(p.name)}</a>${p.award ? " " + honourChip(p.award) : ""}${p.tie ? ` <span class="chip warn" style="font-size:9px">${esc(p.tie)}</span>` : ""}</td>
          <td>${pathwayTag(p.state_team)}</td>
          <td class="thin">${esc(p.junior_club || "")}</td>
          <td class="thin">${esc(p.position || "")}</td>
          <td class="num">${p.games ?? ""}</td>
        </tr>`).join("")}
      </tbody>
    </table></div>
  </div>`;
}

async function mockDraftView(chrome = "") {
  const [order, pool, intel] = await Promise.all([
    api("/api/draft-order"), api("/api/prospects"), api("/api/pick-intel").catch(() => null)]);
  // only draft-eligible prospects — bottom-agers playing up a level can't be
  // drafted this year, so they're excluded from the pool
  const prospects = pool.prospects.filter(p => !p.bottom_ager);
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
        <button class="cta quiet" id="md-download" ${shownAny(sim) ? "" : "disabled"}>Download board</button>
        <button class="cta quiet" id="md-share" ${shownAny(sim) ? "" : "disabled"}>Share</button>
        <span class="thin" style="font-size:12px" id="md-msg">Saves automatically in this browser.</span>
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
                  <span class="picknum">·</span>${guernsey(r.club.abbrev, 18)}
                  <span class="pickclub">${esc(r.club.abbrev)}</span>
                  <span class="thin" style="font-size:12px">${esc(r.absorbed)}</span></div>`;
                shown++;
                return `<div class="pickrow ${isCur ? "otc" : ""} ${r.kind === "matched" ? "matched" : ""}"
                    title="${esc(intelTip(intel, shown))}">
                  <span class="picknum">${shown}</span>
                  ${guernsey(r.club.abbrev, 18)}
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
    view.querySelector("#md-download").addEventListener("click", () => downloadMock(sim));
    view.querySelector("#md-share").addEventListener("click", () => shareMock(sim, events));
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
          ${guernsey(s.st.club, 24)}
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

/* ---------- Top 10 builder (interactive, shareable) ---------- */

const playersChrome = act => `<div class="subtabs">
  <a href="#/players" class="${act === "dir" ? "active" : ""}">Directory</a>
  <a href="#/players/rankings" class="${act === "rank" ? "active" : ""}">Rankings</a>
  <a href="#/players/fantasy" class="${act === "fantasy" ? "active" : ""}">Fantasy</a>
  <a href="#/players/top10" class="${act === "top10" ? "active" : ""}">Build a Top 10</a>
</div>`;

/* Champion Data team code -> our club abbreviation, for colour + linking. */
const CD_TEAM = {
  ADEL: "ADE", BL: "BRI", CARL: "CAR", COLL: "COL", ESS: "ESS", FRE: "FRE",
  GCFC: "GCS", GEEL: "GEE", GWS: "GWS", HAW: "HAW", MELB: "MEL", NMFC: "NM",
  PORT: "PA", RICH: "RIC", STK: "STK", SYD: "SYD", WB: "WB", WCE: "WCE",
};

const TOP10_KEY = "top10_v1";
const decodeTop10 = () => {
  const m = location.hash.match(/[?&]t=([^&]+)/);
  if (m) { try { return JSON.parse(decodeURIComponent(escape(atob(m[1].replace(/-/g, "+").replace(/_/g, "/"))))); } catch { /* fall through */ } }
  try { return JSON.parse(localStorage.getItem(TOP10_KEY)); } catch { return null; }
};
const encodeTop10 = state => btoa(unescape(encodeURIComponent(JSON.stringify(state)))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

/* How a user's Top 10 stacks against Champion Data's actual ranking. `pool`
   is already sorted by rating (CD order), so slices give CD's top N. */
function cdCompare(picks, pool) {
  if (picks.length < 3) return "";
  const cdTop10 = pool.slice(0, 10).map(p => p.name);
  const cdTop25 = new Set(pool.slice(0, 25).map(p => p.name));
  const cdRankOf = Object.fromEntries(pool.map((p, i) => [p.name, i + 1]));
  const inCdTop10 = picks.filter(p => cdTop10.includes(p.name)).length;
  const bold = picks.filter(p => !cdTop25.has(p.name));            // outside CD's top 25
  const snubs = pool.slice(0, 10).filter(p => !picks.some(x => x.name === p.name)); // CD top-10 you left out
  const agree = Math.round(100 * inCdTop10 / Math.min(picks.length, 10));
  return `
    <div class="cdcompare">
      <p class="eyebrow">You vs Champion Data</p>
      <p class="sub"><b>${agree}% agreement</b> — ${inCdTop10} of your ${Math.min(picks.length, 10)}
        are in Champion Data's official top 10 this season.</p>
      ${bold.length ? `<p class="cdc-line"><span class="cdc-tag hot">Hot takes</span>
        ${bold.map(p => `${esc(p.name)} <span class="thin">(CD #${cdRankOf[p.name] || "200+"})</span>`).join(", ")}</p>` : ""}
      ${snubs.length ? `<p class="cdc-line"><span class="cdc-tag cool">You snubbed</span>
        ${snubs.map(p => `${esc(p.name)} <span class="thin">(CD #${cdRankOf[p.name]})</span>`).join(", ")}</p>` : ""}
    </div>`;
}

async function top10View() {
  const [ratings, clubs] = await Promise.all([
    api("/api/ratings?limit=812"), api("/clubs")]);
  const colorOf = ab => (clubs.find(c => c.abbreviation === ab) || {}).primary_color || "#555";
  const pool = ratings.ratings.map(r => ({
    name: r.name, cd: r.team, abbr: CD_TEAM[r.team] || r.team,
    rating: r.rating, rank: r.rank, player_id: r.player_id,
  }));
  const byName = Object.fromEntries(pool.map(p => [p.name, p]));

  let state = decodeTop10() || { title: "My Top 10", picks: [] };
  state.picks = (state.picks || []).slice(0, 10);
  let filter = "";

  const save = () => { localStorage.setItem(TOP10_KEY, JSON.stringify(state)); };

  function render() {
    const filled = state.picks.filter(Boolean).length;
    const available = pool.filter(p => !state.picks.some(x => x && x.name === p.name));

    view.innerHTML = `${playersChrome("top10")}
      <p class="sub" style="margin-top:14px">Pick your ten best players, drag the order how you like it,
        then save the card or share the link. Ratings are the current-season <strong>AFL Player Rating</strong>.</p>
      <div class="top10cols">
        <div class="card">
          <input id="t10-title" class="t10-title" value="${esc(state.title)}" maxlength="42" aria-label="Board title">
          <div class="t10-board" id="t10-board">
            ${Array.from({ length: 10 }, (_, i) => {
              const p = state.picks[i];
              return `<div class="t10-slot ${p ? "filled" : "empty"}" data-i="${i}"
                        ${p ? 'draggable="true"' : ""}>
                <span class="t10-rank">${i + 1}</span>
                ${p ? `
                  ${guernsey(p.abbr, 22)}
                  <span class="t10-name">${p.player_id ? `<a href="#/player/${p.player_id}">${esc(p.name)}</a>` : esc(p.name)}
                    <span class="thin">${esc(p.abbr)} · rating ${p.rating}</span></span>
                  <span class="t10-ctrls">
                    <button data-up="${i}" ${i === 0 ? "disabled" : ""} aria-label="Move up">▲</button>
                    <button data-down="${i}" ${i === filled - 1 || i >= filled ? "disabled" : ""} aria-label="Move down">▼</button>
                    <button data-rm="${i}" aria-label="Remove">✕</button>
                  </span>`
                  : `<span class="t10-empty-label">Empty — pick a player →</span>`}
              </div>`;
            }).join("")}
          </div>
          <div class="feature-ctas" style="margin-top:14px">
            <button class="cta" id="t10-save" ${filled ? "" : "disabled"}>Download card</button>
            <button class="cta quiet" id="t10-share" ${filled ? "" : "disabled"}>Share</button>
            <button class="cta quiet" id="t10-reset">Reset</button>
          </div>
          <p class="srcline" id="t10-msg"></p>
          ${cdCompare(state.picks.filter(Boolean), pool)}
        </div>
        <div class="card">
          <h3>Add players <span class="thin" style="font-weight:400">(${filled}/10)</span></h3>
          <input id="t10-search" class="poolsearch" type="search" placeholder="Filter by name or club…" value="${esc(filter)}">
          <div class="poollist">
            ${available
              .filter(p => !filter || `${p.name} ${p.abbr}`.toLowerCase().includes(filter.toLowerCase()))
              .slice(0, 80).map(p => `
              <button class="poolrow" data-add="${esc(p.name)}" ${filled >= 10 ? "disabled" : ""}>
                <span class="rankchip">${p.rank ?? "–"}</span>
                <span class="poolinfo"><b>${esc(p.name)}</b>
                  <span class="thin">${esc(p.abbr)} · rating ${p.rating}</span></span>
              </button>`).join("")}
          </div>
        </div>
      </div>`;

    const board = document.getElementById("t10-board");
    const compact = () => { state.picks = state.picks.filter(Boolean); save(); };

    view.querySelectorAll("[data-add]").forEach(b => b.addEventListener("click", () => {
      if (state.picks.filter(Boolean).length >= 10) return;
      state.picks.push(byName[b.dataset.add]); compact(); render();
    }));
    board.querySelectorAll("[data-rm]").forEach(b => b.addEventListener("click", () => {
      state.picks.splice(+b.dataset.rm, 1); compact(); render();
    }));
    board.querySelectorAll("[data-up]").forEach(b => b.addEventListener("click", () => {
      const i = +b.dataset.up;[state.picks[i - 1], state.picks[i]] = [state.picks[i], state.picks[i - 1]];
      compact(); render();
    }));
    board.querySelectorAll("[data-down]").forEach(b => b.addEventListener("click", () => {
      const i = +b.dataset.down;[state.picks[i + 1], state.picks[i]] = [state.picks[i], state.picks[i + 1]];
      compact(); render();
    }));

    // drag to reorder
    let dragI = null;
    board.querySelectorAll(".t10-slot.filled").forEach(s => {
      s.addEventListener("dragstart", () => { dragI = +s.dataset.i; });
      s.addEventListener("dragover", e => e.preventDefault());
      s.addEventListener("drop", e => {
        e.preventDefault();
        const to = +s.dataset.i;
        if (dragI === null || dragI === to) return;
        const [m] = state.picks.splice(dragI, 1);
        state.picks.splice(to, 0, m); compact(); render();
      });
    });

    const title = document.getElementById("t10-title");
    title.addEventListener("input", () => { state.title = title.value; save(); });

    document.getElementById("t10-reset").addEventListener("click", () => {
      state = { title: "My Top 10", picks: [] }; save();
      location.hash = "#/players/top10"; render();
    });
    document.getElementById("t10-save").addEventListener("click", () => downloadCard(state, colorOf));
    document.getElementById("t10-share").addEventListener("click", () => shareCard(state, colorOf));

    const search = document.getElementById("t10-search");
    search.addEventListener("input", () => {
      filter = search.value; const pos = search.selectionStart; render();
      const s2 = document.getElementById("t10-search"); s2.focus(); s2.setSelectionRange(pos, pos);
    });
  }
  render();
}

/* Build the shareable card as an SVG we fully control (no external libs,
   CSP-safe), rasterise to PNG via canvas. */
function top10SVG(state, colorOf) {
  const W = 1080, H = 1350, picks = state.picks.filter(Boolean).slice(0, 10);
  const rowH = 104, top = 250;
  const rows = picks.map((p, i) => {
    const y = top + i * rowH, c = colorOf(p.abbr);
    return `
      <g transform="translate(60 ${y})">
        <rect x="0" y="0" width="960" height="88" rx="12" fill="#182129"/>
        <rect x="0" y="0" width="8" height="88" rx="4" fill="${c}"/>
        <text x="34" y="58" font-size="44" font-weight="800" fill="#BF4226" font-family="system-ui,sans-serif">${i + 1}</text>
        <rect x="86" y="22" width="86" height="44" rx="8" fill="${c}"/>
        <text x="129" y="52" font-size="20" font-weight="800" fill="#fff" text-anchor="middle" font-family="system-ui,sans-serif">${esc(p.abbr)}</text>
        <text x="196" y="56" font-size="34" font-weight="700" fill="#E6EBE9" font-family="system-ui,sans-serif">${esc(p.name)}</text>
        <text x="944" y="56" font-size="30" font-weight="800" fill="#93A1A8" text-anchor="end" font-family="system-ui,sans-serif">${p.rating}</text>
      </g>`;
  }).join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
    <rect width="${W}" height="${H}" fill="#10171C"/>
    <rect width="${W}" height="150" fill="#131c24"/>
    <rect y="150" width="${W}" height="5" fill="#BF4226"/>
    <text x="60" y="80" font-size="46" font-weight="800" fill="#F2F4F3" font-family="system-ui,sans-serif">List<tspan fill="#BF4226">Trac</tspan></text>
    <text x="60" y="120" font-size="24" font-weight="700" fill="#93A1A8" font-family="system-ui,sans-serif" letter-spacing="1">${esc((state.title || "My Top 10").toUpperCase())}</text>
    ${rows}
    <text x="60" y="${H - 40}" font-size="22" fill="#55636D" font-family="system-ui,sans-serif">list-trac.vercel.app · ratings: Champion Data / AFL</text>
  </svg>`;
}

function svgToPng(svg) {
  return new Promise((resolve, reject) => {
    const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = 1080; canvas.height = 1350;
      canvas.getContext("2d").drawImage(img, 0, 0);
      URL.revokeObjectURL(url);
      canvas.toBlob(b => b ? resolve(b) : reject(new Error("render failed")), "image/png");
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("render failed")); };
    img.src = url;
  });
}

async function downloadCard(state, colorOf) {
  const msg = document.getElementById("t10-msg");
  try {
    const png = await svgToPng(top10SVG(state, colorOf));
    const a = document.createElement("a");
    a.href = URL.createObjectURL(png);
    a.download = `listtrac-top10-${(state.title || "top10").replace(/[^a-z0-9]+/gi, "-").toLowerCase()}.png`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    if (msg) msg.textContent = "Card downloaded. The link below reopens this exact board.";
  } catch { if (msg) msg.textContent = "Couldn't render the card in this browser."; }
}

async function shareCard(state, colorOf) {
  const msg = document.getElementById("t10-msg");
  const link = `${location.origin}/#/players/top10?t=${encodeTop10(state)}`;
  try {
    const png = await svgToPng(top10SVG(state, colorOf));
    const file = new File([png], "listtrac-top10.png", { type: "image/png" });
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      await navigator.share({ title: state.title || "My AFL Top 10", text: "My AFL Top 10 — built on ListTrac", files: [file] });
      return;
    }
    if (navigator.share) { await navigator.share({ title: state.title, text: "My AFL Top 10 — built on ListTrac", url: link }); return; }
  } catch { /* fall through to clipboard */ }
  try { await navigator.clipboard.writeText(link); if (msg) msg.textContent = "Share link copied to clipboard."; }
  catch { if (msg) msg.textContent = link; }
}

async function fantasyView() {
  view.innerHTML = `${playersChrome("fantasy")}
    <div class="card" id="fantasy-card"><h3>AFL Fantasy</h3><p class="sub">Loading fantasy averages…</p></div>`;
  const POS = [["", "All"], ["MID", "Midfielders"], ["FOR", "Forwards"], ["DEF", "Defenders"], ["RUC", "Rucks"]];
  const load = pos => api(`/api/fantasy?limit=100${pos ? "&position=" + pos : ""}`).then(data => {
    const card = document.getElementById("fantasy-card");
    if (!card) return;
    card.innerHTML = `
      <h3>AFL Fantasy <span class="thin" style="font-weight:400">· ${data.year}</span></h3>
      <div class="controls" style="margin-top:6px">
        ${POS.map(([k, label]) => `<button class="filterbtn ${k === pos ? "active" : ""}" data-pos="${k}">${label}</button>`).join("")}
      </div>
      <p class="sub" style="margin-top:10px">${esc(data.attribution)} — ranked by season average.
        SuperCoach scoring is a separate metric, coming soon.</p>
      <div class="tablewrap"><table>
        <thead><tr><th class="num">#</th><th>Player</th><th>Club</th><th>Pos</th><th class="num">Games</th><th class="num">Avg</th><th class="num">Total</th></tr></thead>
        <tbody>${data.players.map((p, i) => `
          <tr><td class="num">${i + 1}</td>
            <td>${p.player_id ? `<a href="#/player/${p.player_id}">${esc(p.name)}</a>` : esc(p.name)}</td>
            <td>${teamTag(p.team)}</td>
            <td class="thin">${esc((p.position || "").slice(0, 3))}</td>
            <td class="num">${p.games ?? ""}</td>
            <td class="num"><b>${p.af_avg}</b></td><td class="num">${p.af_total ?? ""}</td></tr>`).join("")}
        </tbody>
      </table></div>
      `;
    card.querySelectorAll("[data-pos]").forEach(b => b.addEventListener("click", () => load(b.dataset.pos)));
  }).catch(() => {
    const card = document.getElementById("fantasy-card");
    if (card) card.querySelector(".sub").textContent = "Fantasy data unavailable right now.";
  });
  load("");
}

async function rankingsView() {
  view.innerHTML = `${playersChrome("rank")}
    <div class="card" id="ratings-card"><h3>Player rankings</h3><p class="sub">Loading the official ratings…</p></div>`;
  const loadRatings = year => api(`/api/ratings?limit=100${year ? "&year=" + year : ""}`).then(data => {
    const card = document.getElementById("ratings-card");
    if (!card) return;
    const yrs = data.years || [data.year];
    card.innerHTML = `
      <h3>Player rankings</h3>
      <div class="controls" style="margin-top:6px">
        <label class="eyebrow" style="margin:0" for="ratingsyear">Season</label>
        <select id="ratingsyear">${yrs.slice().reverse().map(y =>
          `<option ${y === data.year ? "selected" : ""}>${y}</option>`).join("")}</select>
        <a class="cta" href="#/players/top10" style="margin:0">Build your own Top 10 →</a>
      </div>
      <p class="sub" style="margin-top:10px">${esc(data.attribution)} — top ${data.ratings.length} of ${data.count} rated players, ${data.year}.</p>
      <div class="tablewrap"><table>
        <thead><tr><th class="num">Rank</th><th>Player</th><th>Club</th><th class="num">Games</th><th class="num">Rating</th></tr></thead>
        <tbody>${data.ratings.map(r => `
          <tr><td class="num"><b>${r.rank ?? "—"}</b></td>
            <td>${r.player_id ? `<a href="#/player/${r.player_id}">${esc(r.name)}</a>` : esc(r.name)}</td>
            <td>${teamTag(r.team)}</td><td class="num">${r.games ?? ""}</td>
            <td class="num"><b>${r.rating}</b></td></tr>`).join("")}
        </tbody>
      </table></div>
      `;
    document.getElementById("ratingsyear").addEventListener("change", e => loadRatings(+e.target.value));
  }).catch(() => {
    const card = document.getElementById("ratings-card");
    if (card) card.querySelector(".sub").textContent = "Ratings unavailable right now.";
  });
  loadRatings();
}

async function playersView() {
  const clubList = await api("/clubs").catch(() => []);
  view.innerHTML = `${playersChrome("dir")}
    <div class="card">
      <h3>Find a player</h3>
      <input id="pfind" class="poolsearch" type="search" placeholder="Start typing a name…" autocomplete="off">
      <div id="presults"></div>
    </div>
    <div class="card">
      <h3>Quick lists</h3>
      <p class="feature-ctas" style="margin-top:10px">
        <a class="cta" href="#/players/rankings">Player rankings</a>
        <a class="cta quiet" href="#/players/fantasy">AFL Fantasy</a>
        <a class="cta quiet" href="#/players/top10">Build a Top 10</a>
        <a class="cta quiet" href="#/free-agents">Free agents 2026</a>
        <a class="cta quiet" href="#/free-agents/out_of_contract">Out of contract</a>
      </p>
    </div>
    <div class="card">
      <h3>Browse by club</h3>
      <div class="clubstrip" style="margin-top:10px">
        ${clubList.filter(c => c.listed_players > 0).map(c => `
          <a href="#/club/${esc(c.abbreviation)}">
            ${guernsey(c.abbreviation, 20)}
            ${esc(c.name)}</a>`).join("")}
      </div>
    </div>`;

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
          <div class="cchead">${guernsey(cl.abbreviation, 26)}<b>${esc(cl.name)}</b></div>
          <span>${cl.listed_players ? cl.listed_players + " listed · 2026" : "list forms for 2028 entry"}</span>
        </a>`).join("")}
    </div>`;
}

let clubViewMode = "list";  // persists the chosen club view between navigations

function clubMetaLine(info) {
  if (!info) return "";
  const bits = [];
  if (info.founded) bits.push(`Est. ${info.founded}`);
  if (typeof info.premierships === "number")
    bits.push(info.premierships === 0
      ? "No premierships yet"
      : `${info.premierships} premiership${info.premierships === 1 ? "" : "s"}${info.last_flag ? ` · last ${info.last_flag}` : ""}`);
  if (info.state) bits.push(info.state);
  return bits.length ? `<p class="clubmeta">${bits.map(esc).join(" &nbsp;·&nbsp; ")}</p>` : "";
}

const AWARD_LABEL = [
  ["brownlow", "Brownlow Medal", "league best & fairest"],
  ["coleman", "Coleman Medal", "leading goalkicker"],
  ["norm_smith", "Norm Smith Medal", "best afield, Grand Final"],
  ["rising_star", "Rising Star", "best young player"],
];
function honourRollCard(info) {
  const prem = info.premiership_years || [];
  const h = info.honours;
  const hasAwards = h && AWARD_LABEL.some(([k]) => (h[k] || []).length);
  if (!prem.length && !hasAwards) return "";
  const premBlock = `
    <div class="honour-prem">
      <div class="hp-num">${prem.length || 0}</div>
      <div class="hp-body">
        <b>VFL/AFL premiership${prem.length === 1 ? "" : "s"}</b>
        ${prem.length ? `<div class="hp-years">${prem.map(y => `<span>${y}</span>`).join("")}</div>`
          : `<span class="thin">None yet — ${esc(info.nickname || "the club")} are still chasing a first flag.</span>`}
      </div>
    </div>`;
  const awardBlocks = AWARD_LABEL.map(([key, label, sub]) => {
    const wins = (h && h[key]) || [];
    return `<div class="award">
      <div class="award-head"><span class="aw-num">${wins.length}</span>
        <span><b>${label}</b><span class="thin"> · ${sub}</span></span></div>
      ${wins.length
        ? `<div class="award-chips">${wins.map(w => `<span class="aw-win"><i>${w.y}</i> ${w.player_id ? `<a href="#/player/${w.player_id}">${esc(w.p)}</a>` : esc(w.p)}</span>`).join("")}</div>`
        : `<p class="thin" style="margin:4px 0 0;font-size:12px">No winners yet.</p>`}
    </div>`;
  }).join("");
  return `<div class="card honours">
    <h3>Honour roll</h3>
    <p class="sub">Premierships and the club's major individual medallists.</p>
    ${premBlock}
    <div class="medalgrid">${awardBlocks}</div>
  </div>`;
}

function ratingLeadersCard(info) {
  const leaders = (info && info.top_rated || []).filter(r => r.rating);
  if (!leaders.length) return "";
  return `<div class="card leaders">
    <h3>Rating leaders <span class="sub" style="font-weight:600">AFL Player Rating · ${esc(info.ratings_year)}</span></h3>
    <div class="leaderrow">${leaders.map((r, i) => `
      <div class="leader">
        <span class="lrank">${i === 0 ? "★" : "#" + r.rank}</span>
        <span class="lname">${r.player_id ? `<a href="#/player/${r.player_id}">${esc(r.name)}</a>` : esc(r.name)}</span>
        <span class="lval">${esc(r.rating)}</span>
      </div>`).join("")}</div>
  </div>`;
}

/* Year-by-year contract grid: each player sits in the column of the year
   their deal expires; free agents & out-of-contract players cluster in 2026.
   Colour = current contract status. Reads as a "contract cliff" per season. */
function contractGridHTML(list) {
  const STATUS_CLS = { contracted: "ok", restricted_fa: "rfa", unrestricted_fa: "ufa", out_of_contract: "warn" };
  const expiry = p => p.contracted_through_year || 2026;
  const maxYear = Math.max(2026, ...list.map(expiry));
  const years = [];
  for (let y = 2026; y <= maxYear; y++) years.push(y);
  const cols = years.map(y => {
    const players = list.filter(p => expiry(p) === y).sort((a, b) =>
      (URGENCY[a.contract_status] ?? 9) - (URGENCY[b.contract_status] ?? 9) ||
      String(a.last_name || "").localeCompare(String(b.last_name || "")));
    const chips = players.map(p =>
      `<a class="gchip ${STATUS_CLS[p.contract_status] || "plain"}" href="#/player/${p.id}"
          title="${esc((STATUS[p.contract_status] || {}).label || "")}">${esc((p.first_name || " ")[0])}. ${esc(p.last_name)}</a>`).join("");
    return `<div class="gcol${y === 2026 ? " now" : ""}">
      <div class="gcount">${players.length}<span>${players.length === 1 ? "player" : "players"}</span></div>
      <div class="gstack">${chips || '<span class="gempty">—</span>'}</div>
      <div class="gyear">${y}${y === 2026 ? '<span class="thin">expiring / FA</span>' : ""}</div>
    </div>`;
  }).join("");
  return `<div class="card">
    <h3>Contract timeline</h3>
    <p class="sub">Each player sits under the year their deal ends. Off-contract players &amp; free agents cluster in 2026 — the taller a column, the bigger that year's list turnover.</p>
    <div class="gridscroll"><div class="cgrid">${cols}</div></div>
    <div class="legend">
      <span><i style="background:var(--ok)"></i>Contracted</span>
      <span><i style="background:var(--warn)"></i>Out of contract</span>
      <span><i style="background:var(--rfa)"></i>Restricted FA</span>
      <span><i style="background:var(--ufa)"></i>Unrestricted FA</span>
    </div>
  </div>`;
}

function clubListHTML(sorted, first) {
  return `<div class="card">
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

/* Positional depth chart (Transfermarkt-style squad view): players grouped by
   their Champion Data position line, sorted by rating, coloured by contract
   status — reveals where a list is thin and who's off contract there. */
const DEPTH_LINES = [
  ["KEY_DEFENDER", "Key defenders"], ["MEDIUM_DEFENDER", "Small / medium defenders"],
  ["MIDFIELDER", "Midfielders"], ["MIDFIELDER_FORWARD", "Mid-forwards"], ["RUCK", "Rucks"],
  ["KEY_FORWARD", "Key forwards"], ["MEDIUM_FORWARD", "Small / medium forwards"],
];
function depthChartHTML(list) {
  const CLS = { contracted: "ok", restricted_fa: "rfa", unrestricted_fa: "ufa", out_of_contract: "warn" };
  const byPos = {};
  list.forEach(p => (byPos[p.position || "OTHER"] = byPos[p.position || "OTHER"] || []).push(p));
  const chip = p => `<a class="dchip ${CLS[p.contract_status] || "plain"}" href="#/player/${p.id}"
      title="${esc((STATUS[p.contract_status] || {}).label || "")}${p.rating ? " · AFL Player Rating " + p.rating : ""}">
      <b>${esc(p.last_name)}</b>${p.rating ? `<span>${p.rating}</span>` : ""}</a>`;
  const line = ([key, label]) => {
    const ps = (byPos[key] || []).sort((a, b) => (b.rating || 0) - (a.rating || 0));
    return ps.length ? `<div class="depthline">
      <div class="depth-pos">${label}<span>${ps.length}</span></div>
      <div class="depth-players">${ps.map(chip).join("")}</div></div>` : "";
  };
  const other = (byPos["OTHER"] || []).sort((a, b) => String(a.last_name).localeCompare(b.last_name));
  return `<div class="card">
    <h3>Positional depth</h3>
    <p class="sub">Every listed player by Champion Data position, sorted by AFL Player Rating; colour = contract status — so a thin line, or a position full of expiring deals, jumps out.</p>
    ${DEPTH_LINES.map(line).join("")}
    ${other.length ? `<div class="depthline"><div class="depth-pos">Rookies / unrated<span>${other.length}</span></div><div class="depth-players">${other.map(chip).join("")}</div></div>` : ""}
    <div class="legend" style="margin-top:14px">
      <span><i style="background:var(--ok)"></i>Contracted</span>
      <span><i style="background:var(--warn)"></i>Out of contract</span>
      <span><i style="background:var(--rfa)"></i>Restricted FA</span>
      <span><i style="background:var(--ufa)"></i>Unrestricted FA</span>
    </div>
  </div>`;
}

async function clubView(abbrev) {
  const [list, socials, info] = await Promise.all([
    api(`/clubs/${encodeURIComponent(abbrev)}/list`),
    api(`/api/club-socials?abbrev=${encodeURIComponent(abbrev)}`).catch(() => ({})),
    api(`/api/club-info?abbrev=${encodeURIComponent(abbrev)}`).catch(() => ({})),
  ]);
  const first = list[0];
  const n = k => list.filter(p => p.contract_status === k).length;
  const sorted = [...list].sort((a, b) =>
    (URGENCY[a.contract_status] ?? 9) - (URGENCY[b.contract_status] ?? 9) ||
    (a.jumper_number ?? 99) - (b.jumper_number ?? 99));
  const renderBody = () => clubViewMode === "grid" ? contractGridHTML(list)
    : clubViewMode === "depth" ? depthChartHTML(list)
    : clubListHTML(sorted, first);
  view.innerHTML = `
    <div class="clubhead">
      ${guernsey(abbrev, 38)}
      <div class="clubtitle">
        <h2>${esc(first.club)}${info && info.nickname ? ` <span class="clubnick">${esc(info.nickname)}</span>` : ""}</h2>
        ${clubMetaLine(info)}
      </div>
      <span class="clubactions">${starButton("club", abbrev)}${socialLinks(socials || {})}</span>
    </div>
    <div class="tiles">
      <div class="tile" style="border-left-color:${esc(first.club_primary || "var(--accent)")}"><p class="eyebrow">List size</p><b>${list.length}</b><span>players · 2026</span></div>
      <div class="tile g"><p class="eyebrow">Contracted past '26</p><b>${n("contracted")}</b><span>players</span></div>
      <div class="tile w"><p class="eyebrow">Off contract '26</p><b>${list.length - n("contracted")}</b><span>incl. free agents</span></div>
      <div class="tile r"><p class="eyebrow">Free agents</p><b>${n("restricted_fa") + n("unrestricted_fa")}</b><span>${n("restricted_fa")} restricted · ${n("unrestricted_fa")} unrestricted</span></div>
    </div>
    ${ratingLeadersCard(info)}
    ${honourRollCard(info)}
    <div class="viewtoggle" role="tablist" aria-label="Club view">
      <button data-mode="list" role="tab">List</button>
      <button data-mode="depth" role="tab">Depth chart</button>
      <button data-mode="grid" role="tab">Contract grid</button>
    </div>
    <div id="clubbody">${renderBody()}</div>`;
  const body = view.querySelector("#clubbody");
  view.querySelectorAll(".viewtoggle button").forEach(b => {
    b.classList.toggle("on", b.dataset.mode === clubViewMode);
    b.setAttribute("aria-selected", b.dataset.mode === clubViewMode);
    b.addEventListener("click", () => {
      if (clubViewMode === b.dataset.mode) return;
      clubViewMode = b.dataset.mode;
      view.querySelectorAll(".viewtoggle button").forEach(x => {
        const on = x.dataset.mode === clubViewMode;
        x.classList.toggle("on", on); x.setAttribute("aria-selected", on);
      });
      body.innerHTML = renderBody();
    });
  });
  mountStars();
}

function timelineHTML(p) {
  const current = p.contract_status.find(cs => cs.is_current) || {};
  const startYear = p.drafted ? p.drafted.year + 1 : 2022;
  const endYear = Math.max((current.contracted_through_year || 2026) + 1, 2027);
  const from = Math.max(startYear, endYear - 11);
  const statusCls = { restricted_fa: "rfa", unrestricted_fa: "ufa", out_of_contract: "warn", contracted: "ok" }[current.status] || "ok";
  // Reconstruct which seasons were under a known contract from the reported
  // signings/extensions, and flag the years a deal was actually signed.
  const covered = new Set(), signedYears = new Set();
  for (const e of (p.contract_events || [])) {
    if ((e.kind !== "signing" && e.kind !== "extension") || !e.end_year) continue;
    const y0 = +String(e.date).slice(0, 4);
    signedYears.add(y0);
    for (let y = y0; y <= e.end_year; y++) covered.add(y);
  }
  const hasSpans = covered.size > 0;
  let cells = "";
  for (let y = from; y <= endYear; y++) {
    let cls;
    if (y === 2026) cls = statusCls;
    else if (y < 2026) cls = covered.has(y) ? "ok" : "faded";
    else cls = (current.status === "contracted" && current.contracted_through_year >= y) || covered.has(y) ? "ok" : "tbd";
    const mark = signedYears.has(y) ? `<span class="signmark" title="Contract signed ${y}">✎</span>` : "";
    cells += `<div class="yr"><div class="bar ${cls}">${mark}</div><div class="lab">'${String(y).slice(2)}</div></div>`;
  }
  return `<div class="timeline" aria-label="Contract status timeline">${cells}</div>
    <div class="legend">
      <span><i style="background:var(--ok);opacity:.75"></i>Contracted${hasSpans ? " (reconstructed from signings)" : ""}</span>
      <span><i style="background:var(--ok);opacity:.28"></i>On list${hasSpans ? ", no deal on record" : " (status not tracked pre-2026)"}</span>
      <span><i style="background:var(--${statusCls === "ok" ? "rfa" : statusCls})"></i>${esc((STATUS[current.status] || {}).label || "")} year</span>
      <span><i style="background:var(--line)"></i>Unresolved</span>
      ${hasSpans ? '<span class="thin">✎ deal signed</span>' : ""}
    </div>`;
}

/* Shareable individual player card — club-coloured, key facts + headline
   metrics. Reuses the SVG->PNG pipeline. */
function playerCardSVG(p, heroA, heroTrim) {
  const W = 1080, H = 1350;
  const current = p.contract_status.find(cs => cs.is_current);
  const facts = [];
  if (p.dob) facts.push(["Age", age(p.dob)]);
  if (p.height_cm) facts.push(["Height", p.height_cm + " cm"]);
  if (p.jumper_number) facts.push(["Guernsey", "#" + p.jumper_number]);
  if (p.drafted) facts.push(["Drafted", `${p.drafted.year}${p.drafted.pick_number ? " · Pick " + p.drafted.pick_number : ""}`]);
  if (current && current.contracted_through_year) facts.push(["Contracted to", current.contracted_through_year]);
  const metrics = [];
  if (p.rating) metrics.push(["AFL Player Rating", `#${p.rating.rank} · ${p.rating.rating}`]);
  if (p.fantasy) metrics.push(["AFL Fantasy avg", p.fantasy.af_avg]);
  if (current) metrics.push(["Contract status", (STATUS[current.status] || {}).label || current.status]);

  const factRows = facts.map((f, i) => `
    <text x="70" y="${560 + i * 60}" font-size="24" fill="#93A1A8" font-family="system-ui,sans-serif">${esc(f[0])}</text>
    <text x="1010" y="${560 + i * 60}" font-size="26" font-weight="700" fill="#E6EBE9" text-anchor="end" font-family="system-ui,sans-serif">${esc(String(f[1]))}</text>`).join("");
  const metricRows = metrics.map((m, i) => `
    <g transform="translate(60 ${900 + i * 96})">
      <rect width="960" height="80" rx="10" fill="#182129"/>
      <text x="26" y="50" font-size="24" fill="#93A1A8" font-family="system-ui,sans-serif">${esc(m[0])}</text>
      <text x="934" y="50" font-size="30" font-weight="800" fill="#BF4226" text-anchor="end" font-family="system-ui,sans-serif">${esc(String(m[1]))}</text>
    </g>`).join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
    <rect width="${W}" height="${H}" fill="#10171C"/>
    <rect width="${W}" height="440" fill="${heroA}"/>
    <rect y="440" width="${W}" height="6" fill="${heroTrim}"/>
    <text x="60" y="90" font-size="30" font-weight="800" fill="#F2F4F3" font-family="system-ui,sans-serif" opacity="0.85">List<tspan fill="#BF4226">Trac</tspan></text>
    <text x="60" y="300" font-size="72" font-weight="800" fill="#F5F2EC" font-family="system-ui,sans-serif">${esc(p.first_name)}</text>
    <text x="60" y="380" font-size="72" font-weight="800" fill="#F5F2EC" font-family="system-ui,sans-serif">${esc(p.last_name)}</text>
    <text x="60" y="425" font-size="26" font-weight="700" fill="${heroTrim}" font-family="system-ui,sans-serif" letter-spacing="1">${esc((p.club || "Unattached").toUpperCase())}${p.fantasy && p.fantasy.position ? " · " + esc(p.fantasy.position.replace(/_/g, " ")) : ""}</text>
    ${factRows}
    ${metricRows}
    <text x="60" y="${H - 40}" font-size="20" fill="#55636D" font-family="system-ui,sans-serif">list-trac.vercel.app · ratings: Champion Data / AFL</text>
  </svg>`;
}

/* Percentile scouting report (the FBref move): a radar of the player's output
   ranked against same-position peers, plus per-stat percentile bars. */
const SCOUT_GROUP = { ball: "var(--ufa)", attack: "var(--accent)", defence: "var(--ok)" };
function scoutingRadar(sc) {
  const items = sc.order.filter(k => sc.stats[k]);
  const n = items.length, cx = 190, cy = 162, R = 106;
  const pt = (i, r) => {
    const a = (-90 + i * 360 / n) * Math.PI / 180;
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  };
  const poly = pts => pts.map(p => p.map(v => v.toFixed(1)).join(",")).join(" ");
  const rings = [25, 50, 75, 100].map(pc =>
    `<polygon points="${poly(items.map((_, i) => pt(i, R * pc / 100)))}" fill="none" stroke="var(--line)" stroke-width="1"/>`).join("");
  const axes = items.map((_, i) => { const [x, y] = pt(i, R); return `<line x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="var(--line)" stroke-width="0.5"/>`; }).join("");
  const shape = poly(items.map((k, i) => pt(i, R * sc.stats[k].pct / 100)));
  const dots = items.map((k, i) => { const [x, y] = pt(i, R * sc.stats[k].pct / 100); return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="2.6" fill="${SCOUT_GROUP[sc.stats[k].group]}"/>`; }).join("");
  const labels = items.map((k, i) => {
    const [x, y] = pt(i, R + 13), c = Math.cos((-90 + i * 360 / n) * Math.PI / 180);
    const anchor = c > 0.3 ? "start" : c < -0.3 ? "end" : "middle";
    return `<text x="${x.toFixed(1)}" y="${(y + 3).toFixed(1)}" text-anchor="${anchor}" font-size="10" fill="var(--ink-2)">${esc(sc.stats[k].label)}</text>`;
  }).join("");
  return `<svg viewBox="0 0 380 330" class="radar" width="100%">${rings}${axes}
    <polygon points="${shape}" fill="var(--accent)" fill-opacity="0.18" stroke="var(--accent)" stroke-width="1.5" stroke-linejoin="round"/>
    ${dots}${labels}</svg>`;
}
function scoutingBars(sc) {
  return sc.order.filter(k => sc.stats[k]).map(k => {
    const s = sc.stats[k];
    return `<div class="scrow" style="--pct:${s.pct}%;--g:${SCOUT_GROUP[s.group]}">
      <span class="sc-lab">${esc(s.label)}</span>
      <span class="sc-bar"><i></i></span>
      <span class="sc-val"><b>${s.pct}</b><span class="thin"> · ${s.avg}</span></span></div>`;
  }).join("");
}
function scoutingCard(sc) {
  return `<div class="card scouting">
    <h3>Scouting report <span class="thin" style="font-weight:400">· percentile vs ${esc(sc.position_label)}s</span></h3>
    <p class="sub">How this season's per-game output ranks against every ${esc(sc.position_label).toLowerCase()} in the league (min ${sc.min_games} games). 100 = best.</p>
    <div class="scoutcols">
      <div class="scoutradar">${scoutingRadar(sc)}
        <div class="scoutlegend"><span><i style="background:var(--ufa)"></i>Ball use</span><span><i style="background:var(--accent)"></i>Attack</span><span><i style="background:var(--ok)"></i>Defence</span></div>
      </div>
      <div class="scoutbars">${scoutingBars(sc)}</div>
    </div>
  </div>`;
}

async function playerView(id) {
  const p = await api(`/players/${id}`);
  const fullName = `${p.first_name} ${p.last_name}`;
  const news = await api(`/api/player-news?name=${encodeURIComponent(fullName)}`).catch(() => []);
  const current = p.contract_status.find(cs => cs.is_current);
  const heroA = p.club_primary || "#333", heroTrim = p.club_secondary || "#ddd";
  const isFA = current && (current.status === "restricted_fa" || current.status === "unrestricted_fa");

  // Unified, chronological movement timeline: draft + DB transactions + the
  // AFLRATINGS contract signings/extensions that fill the middle + FA naming.
  const events = [];
  if (p.drafted) events.push({
    date: `${p.drafted.year}-11-25`, when: `Nov ${p.drafted.year}`, cls: "ok", label: "Drafted",
    detail: `${p.drafted.year} ${esc(p.drafted.draft_type)} draft${p.drafted.pick_number ? ", pick " + p.drafted.pick_number : ""} — ${esc(p.drafted.club)}`,
  });
  for (const t of p.transactions) {
    const label = { trade: "Trade", sign_fa: "FA signing", sign_rookie: "Rookie signing", delist: "Delisted", retire: "Retired", rookie_elevate: "Elevated" }[t.type] || t.type;
    events.push({
      date: t.date || "", when: (t.date || "").length >= 7 ? monthYear(t.date) : (t.date || "").slice(0, 4),
      cls: t.type === "trade" ? "warn" : "plain", label,
      detail: `${t.from_club ? esc(t.from_club) + " → " : ""}${esc(t.to_club || "")}${t.notes ? ` <span class="thin">· ${esc(t.notes.replace("; date approximate (year-level from Draftguru)", ""))}</span>` : ""}`,
    });
  }
  const contractEvents = (p.contract_events || []).filter(e => e.kind === "signing" || e.kind === "extension");
  for (const e of contractEvents) {
    const parts = [];
    if (e.length) parts.push(`${e.length}-year deal`);
    if (e.end_year) parts.push(`contracted to end of ${e.end_year}${e.end_estimated ? " (est.)" : ""}`);
    events.push({
      date: e.date, when: monthYear(e.date), cls: "ok", label: e.kind === "extension" ? "Re-signed" : "Signed",
      detail: `${e.club ? esc(e.club) + " — " : ""}${parts.join(", ") || "terms not reported"}`
        + `${e.reporter ? ` · <span class="thin">${esc(e.reporter)}</span>` : ""}`
        + `${e.source_url ? ` <a class="srclink" href="${esc(e.source_url)}" target="_blank" rel="noopener">source ↗</a>` : ""}`,
    });
  }
  if (current && isFA) events.push({
    date: "2026-07-15", when: "Jul 2026", cls: STATUS[current.status].cls, label: STATUS[current.status].label,
    detail: `Named ${esc(STATUS[current.status].label.toLowerCase())} for end of ${current.contracted_through_year}`,
  });
  events.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
  const txRows = events.map(e =>
    `<tr><td class="thin">${esc(e.when)}</td><td><span class="chip ${e.cls}">${esc(e.label)}</span></td><td>${e.detail}</td></tr>`);

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
        <p class="club-line">${p.club ? `${guernsey(p.club_abbrev, 20)}<a href="#/club/${esc(p.club_abbrev)}">${esc(p.club)}</a>` : "Unattached"}</p>
        <h2>${esc(p.first_name)} ${esc(p.last_name)}</h2>
        <p class="statusline">${current ? chip(current.status) : ""}${p.rating ? `
          <span class="chip" style="background:rgba(0,0,0,0.35);border:1px solid rgba(255,255,255,0.45);color:#fff">AFL Player Rating #${p.rating.rank} · ${p.rating.rating}</span>` : ""}${p.fantasy ? `
          <span class="chip" style="background:rgba(0,0,0,0.35);border:1px solid rgba(255,255,255,0.45);color:#fff">AFL Fantasy avg ${p.fantasy.af_avg}</span>` : ""}</p>
        <dl class="hero-facts">
          ${p.dob ? `<div><dt>Age</dt><dd>${age(p.dob)} (${esc(p.dob)})</dd></div>` : ""}
          ${p.height_cm ? `<div><dt>Height</dt><dd>${p.height_cm} cm</dd></div>` : ""}
          ${p.jumper_number ? `<div><dt>Guernsey</dt><dd>#${p.jumper_number}</dd></div>` : ""}
          ${p.drafted ? `<div><dt>Drafted</dt><dd>${p.drafted.year} ${esc(p.drafted.draft_type)}${p.drafted.pick_number ? " · Pick " + p.drafted.pick_number : ""}</dd></div>
          <div><dt>Drafted by</dt><dd>${esc(p.drafted.club)}</dd></div>` : ""}
          ${current && current.contracted_through_year ? `<div><dt>Contracted through</dt><dd>${current.contracted_through_year}</dd></div>` : ""}
        </dl>
        <p class="feature-ctas" style="margin-top:16px;align-items:center">
          ${starButton("player", id)}
          ${playerSocialSearch(fullName)}
          <button class="cta quiet" id="pc-download" style="border-color:rgba(255,255,255,0.4);color:#fff">Download card</button>
          <button class="cta quiet" id="pc-share" style="border-color:rgba(255,255,255,0.4);color:#fff">Share</button>
        </p>
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
          <h3>Movement &amp; contracts</h3>
          <p class="sub">Draft, trades, contract signings and free agency${contractEvents.length ? " — the middle filled in from reported signings" : ""}. Status &amp; terms only; never dollars.</p>
          <div class="tablewrap"><table>
            <thead><tr><th>When</th><th>Type</th><th>Detail</th></tr></thead>
            <tbody>${txRows.join("") || `<tr><td colspan="4" class="thin">No recorded movements — original-list player.</td></tr>`}</tbody>
          </table></div>
        </div>
        ${p.scouting ? scoutingCard(p.scouting) : ""}
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

  mountStars();
  const cardPng = () => svgToPng(playerCardSVG(p, heroA, heroTrim));
  const dl = document.getElementById("pc-download");
  if (dl) dl.addEventListener("click", async () => {
    try {
      const png = await cardPng();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(png);
      a.download = `listtrac-${fullName.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}.png`;
      a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    } catch { /* unsupported browser */ }
  });
  const sh = document.getElementById("pc-share");
  if (sh) sh.addEventListener("click", async () => {
    const link = `${location.origin}/#/player/${id}`;
    try {
      const png = await cardPng();
      const file = new File([png], "listtrac-player.png", { type: "image/png" });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({ title: fullName, text: `${fullName} — ListTrac`, files: [file] });
        return;
      }
      if (navigator.share) { await navigator.share({ title: fullName, url: link }); return; }
    } catch { /* clipboard fallback */ }
    try { await navigator.clipboard.writeText(link); } catch { /* noop */ }
  });
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

const POS_SHORT = { MIDFIELDER: "Mid", MIDFIELDER_FORWARD: "Mid-fwd", KEY_FORWARD: "Key fwd",
  MEDIUM_FORWARD: "Sml fwd", KEY_DEFENDER: "Key def", MEDIUM_DEFENDER: "Sml def", RUCK: "Ruck" };

async function faView(filter = "all") {
  const statuses = filter === "all" ? ["restricted_fa", "unrestricted_fa"] : [filter];
  const lists = await Promise.all(statuses.map(s => api(`/contract-status?status=${s}`)));
  const players = lists.flat().sort((a, b) =>
    (b.rating || 0) - (a.rating || 0) || String(a.last_name).localeCompare(b.last_name));
  const rated = players.filter(p => p.rating).length;
  const buttons = [["all", "All free agents"], ["restricted_fa", "Restricted"], ["unrestricted_fa", "Unrestricted"], ["out_of_contract", "Out of contract"]];
  view.innerHTML = `
    <div class="controls">
      ${buttons.map(([k, label]) =>
        `<button class="filterbtn ${k === filter ? "active" : ""}" data-f="${k}">${label}</button>`).join("")}
    </div>
    <div class="card">
      <h3>${esc(buttons.find(b => b[0] === filter)[1])} — end of 2026</h3>
      <p class="sub">${players.length} players, ranked by AFL Player Rating — the best talent available on the open market. Players with no 2026 rating sit at the bottom.</p>
      <div class="tablewrap"><table>
        <thead><tr><th class="num">#</th><th>Player</th><th>Club</th><th>Pos</th><th class="num">Age</th><th class="num">Rating</th><th>Status</th></tr></thead>
        <tbody>${players.map((x, i) => `
          <tr><td class="num thin">${x.rating ? i + 1 : ""}</td>
            <td>${playerLink(x)}</td><td class="thin">${esc(x.club)}</td>
            <td class="thin">${esc(POS_SHORT[x.position] || "")}</td>
            <td class="num">${age(x.dob)}</td>
            <td class="num">${x.rating ? `<b>${x.rating}</b>${x.rating_rank ? ` <span class="thin">#${x.rating_rank}</span>` : ""}` : "—"}</td>
            <td>${chip(x.contract_status)}</td></tr>`).join("")}
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
            ${guernsey(c.abbreviation, 20)}
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
  <a href="#/draft/prospects" class="${act === "prospects" ? "active" : ""}">Prospects</a>
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
  [/^#\/players\/rankings$/,        () => rankingsView()],
  [/^#\/players\/fantasy$/,         () => fantasyView()],
  [/^#\/players\/top10(?:\?.*)?$/,  () => top10View()],
  [/^#\/draft$/,                    () => draftOrderView(draftChrome("order"))],
  [/^#\/draft\/mock(?:\?.*)?$/,     () => mockDraftView(draftChrome("mock"))],
  [/^#\/draft\/prospects(?:\/(\d{4}))?$/, m => prospectsView(+(m[1] || 2027))],
  [/^#\/prospect\/(.+)$/,           m => prospectProfileView(decodeURIComponent(m[1]))],
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
