/* Kino v2 — tek sayfa uygulama (vanilla JS) */
"use strict";

/* ------------------------------------------------------------------ utils */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const V = () => document.getElementById("view");
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const clamp = (n, a, b) => Math.max(a, Math.min(b, n));
const pct = (n, d) => (!d ? 0 : clamp(n / d * 100, 0, 100));

const ICONS = {
  home: '<path d="M3 10.7 12 3l9 7.7"/><path d="M5.5 9.5V21h13V9.5"/>',
  compass: '<circle cx="12" cy="12" r="9"/><path d="m15.6 8.4-2.1 5.1-5.1 2.1 2.1-5.1z"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2.5"/><path d="M8 3v4M16 3v4M3 11h18"/>',
  bookmark: '<path d="M6 3.5h12a1 1 0 0 1 1 1V21l-7-4.2L5 21V4.5a1 1 0 0 1 1-1z"/>',
  chart: '<path d="M4 20V11M10 20V4M16 20v-6M22 20H2"/>',
  download: '<path d="M12 3v11"/><path d="m7.5 10 4.5 4.5L16.5 10"/><path d="M4 20.5h16"/>',
  settings: '<circle cx="12" cy="12" r="3.2"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1A2 2 0 1 1 4.1 17l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1A2 2 0 1 1 7 4.1l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1A2 2 0 1 1 19.9 7l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.6-3.6"/>',
  command: '<path d="M9 6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3z"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  play: '<path d="M8 4.5v15l12-7.5z" fill="currentColor" stroke="none"/>',
  pause: '<path d="M8 4h3v16H8zM13 4h3v16h-3z" fill="currentColor" stroke="none"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  heart: '<path d="M12 20s-7-4.4-7-9.2A4.1 4.1 0 0 1 12 7a4.1 4.1 0 0 1 7 3.8C19 15.6 12 20 12 20z"/>',
  star: '<path d="m12 3.5 2.7 5.6 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1L3.2 10l6.1-.9z"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  left: '<path d="m14.5 5-7 7 7 7"/>',
  right: '<path d="m9.5 5 7 7-7 7"/>',
  down: '<path d="m5 9.5 7 7 7-7"/>',
  up: '<path d="m5 14.5 7-7 7 7"/>',
  refresh: '<path d="M20 11a8 8 0 1 0-2.3 6.4"/><path d="M20 4v7h-7"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5.3l3.4 2"/>',
  check: '<path d="m4.5 12.5 5 5L20 7"/>',
  film: '<rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4"/>',
  fire: '<path d="M12 3s5 4.5 5 9a5 5 0 0 1-10 0c0-2 1-3.5 1-3.5S9 11 10.5 11C12 11 12 8 12 3z"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/>',
  external: '<path d="M14 4h6v6"/><path d="M20 4 11 13"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  volume: '<path d="M11 5 6.5 9H3v6h3.5L11 19z"/><path d="M15 9a4 4 0 0 1 0 6"/>',
  pip: '<rect x="3" y="5" width="18" height="14" rx="2"/><rect x="12" y="11" width="7" height="6" rx="1"/>',
  loader: '<path d="M12 3a9 9 0 1 0 9 9"/>',
};
function icon(n) {
  return '<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">' + (ICONS[n] || "") + "</svg>";
}
function paintIcons(root = document) {
  $$("[data-icon]", root).forEach(el => {
    if (!el.dataset.painted) { el.innerHTML = icon(el.dataset.icon); el.dataset.painted = "1"; }
  });
}

/* ------------------------------------------------------------------ state */
const S = {
  lib: { animes: [], progress: {}, lists: {}, history: [], settings: {} },
  cache: {},
  timers: [],
  player: null,
  palette: { open: false, items: [], sel: 0, timer: null },
  detailTab: "eps",
  heroIdx: 0,
};

async function api(path, data) {
  const opt = data === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  };
  const r = await fetch(path, opt);
  if (!r.ok) {
    let m = "sunucu hatası";
    try { m = (await r.json()).error || m; } catch (e) { }
    throw new Error(m);
  }
  return r.json();
}
async function loadLib() { S.lib = await api("/api/library"); }
function applySettings() {
  const st = S.lib.settings || {};
  document.documentElement.dataset.theme = st.theme || "violet";
  document.documentElement.classList.toggle("no-motion", !!st.reduceMotion);
}
function toast(msg, cls = "") {
  const el = document.createElement("div");
  el.className = "toast " + cls;
  el.innerHTML = (cls === "err" ? icon("x") : cls === "ok" ? icon("check") : "") + "<span>" + esc(msg) + "</span>";
  $("#toast-root").appendChild(el);
  setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 260); }, 3400);
}
function poll(fn, ms) {
  const id = setInterval(fn, ms);
  S.timers.push(id);
  return id;
}
function stopPolls() {
  S.timers.forEach(clearInterval); S.timers = [];
  S.homePoll = null; S.detailPoll = null;
  if (S.heroTimer) { clearInterval(S.heroTimer); S.heroTimer = null; }
}
function cleanupPlayer() {
  const p = S.player;
  if (!p) return;
  try { p.video && p.video.pause(); } catch (e) { }
  try { p.stop && p.stop(); } catch (e) { }
  try { p.save && p.save(false); } catch (e) { }
  if (p.keys) document.removeEventListener("keydown", p.keys);
  if (p.onUnload) window.removeEventListener("beforeunload", p.onUnload);
  if (p.onVis) document.removeEventListener("visibilitychange", p.onVis);
  S.player = null;
}

/* ------------------------------------------------------------- time utils */
function fmtTime(s) {
  s = Math.max(0, Math.round(s || 0));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), q = s % 60;
  return h ? h + ":" + String(m).padStart(2, "0") + ":" + String(q).padStart(2, "0")
    : m + ":" + String(q).padStart(2, "0");
}
function fmtAgo(ts) {
  if (!ts) return "";
  const d = Math.max(0, Date.now() / 1000 - ts);
  if (d < 60) return "şimdi";
  if (d < 3600) return Math.floor(d / 60) + " dk önce";
  if (d < 86400) return Math.floor(d / 3600) + " sa önce";
  if (d < 86400 * 7) return Math.floor(d / 86400) + " gün önce";
  return new Date(ts * 1000).toLocaleDateString("tr-TR");
}
function fmtLeft(pos, dur) {
  if (!dur) return "";
  const left = dur - pos;
  if (left < 60) return "az kaldı";
  if (left < 3600) return Math.ceil(left / 60) + " dk kaldı";
  return Math.floor(left / 3600) + " sa " + Math.ceil((left % 3600) / 60) + " dk kaldı";
}
function fmtClock(ts) {
  return new Date(ts * 1000).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
}

/* ------------------------------------------------------------- lib helpers */
function animeById(id) { return S.lib.animes.find(a => a.id === id) || null; }
function progOf(aid, n) { return S.lib.progress[aid + ":" + n] || null; }
function listOf(aid) { return (S.lib.lists || {})[aid] || {}; }
function epStatus(aid, n) {
  const p = progOf(aid, n);
  if (!p) return "new";
  if (p.done) return "done";
  if (p.pos > 20) return "watching";
  return "new";
}
function nextEpisode(a) {
  for (const ep of a.episodes) {
    const p = progOf(a.id, ep.n);
    if (!p || (!p.done && p.pos < (p.dur || 1e9) * 0.95)) return ep;
  }
  return a.episodes[a.episodes.length - 1] || null;
}
function continueItems() {
  const out = [];
  for (const a of S.lib.animes) {
    for (const ep of a.episodes) {
      const p = progOf(a.id, ep.n);
      if (p && !p.done && p.pos > 20 && (!p.dur || p.pos < p.dur * 0.97)) {
        out.push({ a, ep, p });
      }
    }
  }
  return out.sort((x, y) => (y.p.updated || 0) - (x.p.updated || 0)).slice(0, 14);
}
function isFetching(a) {
  const s = (a && a.fetch && a.fetch.status) || "";
  return s === "queued" || s === "running";
}
function fetchLabel(a) {
  const f = a.fetch || {};
  if (f.status === "queued") return "Sırada";
  if (f.status === "running") return (f.got || 0) + "/" + (f.requested || 10);
  return "";
}
function anyFetching() { return S.lib.animes.some(isFetching); }
function addToLibrary(media) { return api("/api/add", { media }); }

/* --------------------------------------------------------------- navigation */
const NAV = [
  { key: "home", label: "Ana Sayfa", icon: "home", href: "#/" },
  { key: "guncel", label: "Güncel & Takip", icon: "clock", href: "#/guncel" },
  { key: "kesfet", label: "Keşfet", icon: "compass", href: "#/kesfet" },
  { key: "takvim", label: "Takvim", icon: "calendar", href: "#/takvim" },
  { key: "listem", label: "Listem", icon: "bookmark", href: "#/listem" },
  { key: "istatistik", label: "İstatistik", icon: "chart", href: "#/istatistik" },
  { key: "kuyruk", label: "Kuyruk", icon: "download", href: "#/kuyruk" },
  { key: "ayarlar", label: "Ayarlar", icon: "settings", href: "#/ayarlar" },
];
function renderNav(active) {
  $("#nav").innerHTML = NAV.map(n => `
    <a class="nav-item ${n.key === active ? "active" : ""}" href="${n.href}">
      ${icon(n.icon)}<span>${n.label}</span>
      ${n.key === "kuyruk" ? `<i class="nav-dot" id="navQueueDot" hidden></i>` : ""}
    </a>`).join("");
}
function updateQueueMini() {
  const n = (S.lib.animes || []).filter(isFetching).length;
  const el = $("#queueMini");
  if (el) {
    el.innerHTML = n
      ? `<span class="qm-spin"></span><div><b>${n} çekim</b><small>devam ediyor</small></div>`
      : `<span class="qm-idle">${icon("download")}</span><div><b>Kuyruk boş</b><small>her şey hazır</small></div>`;
  }
  const dot = $("#queueDot"); if (dot) dot.hidden = !n;
  const nd = $("#navQueueDot"); if (nd) nd.hidden = !n;
}

/* ------------------------------------------------------------------ router */
function parseHash() {
  const h = (location.hash || "#/").replace(/^#\/?/, "");
  const [path, qs] = h.split("?");
  return { parts: path.split("/").filter(Boolean), q: new URLSearchParams(qs || "") };
}
function nav(h) { location.hash = "#/" + String(h).replace(/^#?\/?/, ""); }

async function route() {
  S.routeVersion = (S.routeVersion || 0) + 1;
  stopPolls();
  cleanupPlayer();
  closePalette();
  document.title = "Kino — anime kütüphanesi";
  const { parts, q } = parseHash();
  const p0 = parts[0] || "home";
  renderNav(p0 === "" ? "home" : p0);
  updateQueueMini();
  window.scrollTo({ top: 0, behavior: "instant" in document.documentElement.style ? "instant" : "auto" });
  try {
    if (p0 === "home") return await renderHome();
    if (p0 === "guncel") return await renderCurrent(q);
    if (p0 === "kesfet") return await renderDiscover(q);
    if (p0 === "a") return await renderDetail(parts[1]);
    if (p0 === "d") return await renderDetail(null, parts[1]);
    if (p0 === "p") return await renderPlayer(parts[1], Number(parts[2]));
    if (p0 === "listem") return await renderList();
    if (p0 === "takvim") return await renderSchedule(q);
    if (p0 === "istatistik") return await renderStats();
    if (p0 === "kuyruk") return await renderQueue();
    if (p0 === "ayarlar") return await renderSettings();
    nav("");
  } catch (e) {
    V().innerHTML = `<div class="empty"><div class="big">⚠️</div><h2>Bir şeyler ters gitti</h2><p>${esc(e.message)}</p><button class="btn" onclick="location.reload()">Yenile</button></div>`;
  }
}

/* ------------------------------------------------------------------- cards */
function mediaCard(o) {
  const link = o.localId ? "#/a/" + encodeURIComponent(o.localId) : "#/d/" + encodeURIComponent(o.anilistId || "");
  const badge = o.badge ? `<span class="card-badge">${esc(o.badge)}</span>` : "";
  const score = o.score ? `<span class="card-score">${icon("star")}${(o.score / 10).toFixed(1)}</span>` : "";
  const fetch = o.fetching ? `<span class="card-fetch"><i></i>${esc(o.fetchLabel || "")}</span>` : "";
  const prog = o.progress ? `<div class="card-prog"><i style="width:${o.progress}%"></i></div>` : "";
  const sub = o.sub ? `<div class="card-sub">${esc(o.sub)}</div>` : "";
  return `<a class="card" href="${link}">
    <div class="card-poster">
      ${o.poster ? `<img src="${esc(o.poster)}" loading="lazy" referrerpolicy="no-referrer" alt="">`
      : `<div class="fallback">${esc((o.title || "?")[0])}</div>`}
      <div class="card-fade"></div>
      ${badge}${score}${fetch}
      <span class="card-play">${icon("play")}</span>
      ${prog}
    </div>
    <div class="card-body">
      <h3 class="card-title">${esc(o.title)}</h3>
      ${sub}
    </div>
  </a>`;
}
function libCard(a, extra = {}) {
  const p = extra.prog;
  return mediaCard({
    localId: a.id,
    title: a.title,
    poster: (a.meta || {}).poster,
    score: (a.meta || {}).score,
    badge: a.episodes.length + " bölüm",
    sub: extra.sub || ((a.meta || {}).year || ""),
    progress: p,
    fetching: isFetching(a),
    fetchLabel: fetchLabel(a),
  });
}
function catCard(r) {
  const sub = [r.year, r.format, r.episodes ? r.episodes + " bölüm" : ""].filter(Boolean).join(" · ");
  return mediaCard({
    anilistId: r.anilistId || r.id,
    title: r.title,
    poster: r.poster,
    score: r.score,
    sub,
  });
}
function rowHtml(title, cards, more) {
  if (!cards.length) return "";
  return `<section class="row">
    <div class="row-head">
      <h2 class="row-title">${esc(title)}</h2>
      ${more ? `<a class="row-more" href="${more}">Tümü ${icon("right")}</a>` : ""}
    </div>
    <div class="row-wrap">
      <button class="row-btn left" aria-label="geri">${icon("left")}</button>
      <div class="scroller">${cards.join("")}</div>
      <button class="row-btn right" aria-label="ileri">${icon("right")}</button>
    </div>
  </section>`;
}
function wireRows(root = document) {
  $$(".row-wrap", root).forEach(w => {
    const sc = $(".scroller", w);
    if (!sc || w.dataset.wired) return;
    w.dataset.wired = "1";
    $(".row-btn.left", w).onclick = () => sc.scrollBy({ left: -sc.clientWidth * 0.85, behavior: "smooth" });
    $(".row-btn.right", w).onclick = () => sc.scrollBy({ left: sc.clientWidth * 0.85, behavior: "smooth" });
  });
}
function skeletonRows(n = 3) {
  let out = '<div class="skeleton-hero"></div>';
  for (let i = 0; i < n; i++) {
    out += `<div class="sk-row"><div class="sk-title"></div><div class="sk-cards">` +
      Array.from({ length: 6 }).map(() => '<div class="sk-card"></div>').join("") + `</div></div>`;
  }
  return out;
}
async function cached(key, fn, ttl = 300000) {
  const c = S.cache[key];
  if (c && Date.now() - c.at < ttl) return c.val;
  const val = await fn();
  S.cache[key] = { at: Date.now(), val };
  return val;
}
function seasonNow() {
  const d = new Date(), m = d.getMonth() + 1;
  const season = m <= 3 ? "WINTER" : m <= 6 ? "SPRING" : m <= 9 ? "SUMMER" : "FALL";
  return { season, year: d.getFullYear() };
}

/* -------------------------------------------------------------------- home */
async function renderHome() {
  V().innerHTML = skeletonRows(3);
  const { season, year } = seasonNow();
  const [trend, seas, pop, top] = await Promise.all([
    cached("trend", () => api("/api/browse?sort=TRENDING_DESC&per=20")),
    cached("season", () => api(`/api/browse?season=${season}&year=${year}&sort=POPULARITY_DESC&per=20`)),
    cached("pop", () => api("/api/browse?sort=POPULARITY_DESC&per=20")),
    cached("top", () => api("/api/browse?sort=SCORE_DESC&per=20")),
  ]);
  const trendR = (trend.results || []).filter(r => r.banner);
  const heroList = (trendR.length ? trendR : trend.results || []).slice(0, 5);
  const cw = continueItems();
  const libCards = S.lib.animes.map(a => libCard(a, {
    prog: (() => { const e = nextEpisode(a); const p = e && progOf(a.id, e.n); return p && p.dur ? pct(p.pos, p.dur) : 0; })(),
  }));
  const topGenre = (() => {
    const counts = {};
    S.lib.animes.forEach(a => ((a.meta || {}).genres || []).forEach(g => counts[g] = (counts[g] || 0) + 1));
    const arr = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    return arr.length ? arr[0][0] : null;
  })();
  let forYou = null;
  if (topGenre) {
    try {
      forYou = await cached("foryou:" + topGenre, () =>
        api(`/api/browse?genre=${encodeURIComponent(topGenre)}&sort=SCORE_DESC&per=20`));
    } catch (e) { }
  }
  const hero = heroList[0];
  V().innerHTML = `
    ${hero ? heroMarkup(hero, heroList) : ""}
    <div class="home-body">
      <a href="#/guncel" class="tracking-banner"><span>${icon("calendar")} GÜNCEL & TAKİP</span><div><b>Yeni bölümleri kaçırma.</b><p>Sezonu keşfet, yayın saatlerini gör ve izlediklerini işaretle.</p></div>${icon("right")}</a>
      ${cw.length ? `<section class="row">
        <div class="row-head"><h2 class="row-title">İzlemeye devam et</h2>
          <a class="row-more" href="#/listem">Listem ${icon("right")}</a></div>
        <div class="row-wrap"><button class="row-btn left">${icon("left")}</button>
        <div class="scroller">${cw.map(({ a, ep, p }) => mediaCard({
    localId: a.id, title: a.title, poster: (a.meta || {}).poster,
    badge: "Bölüm " + ep.n, sub: fmtLeft(p.pos, p.dur) || "devam ediyor",
    progress: p.dur ? pct(p.pos, p.dur) : 0, score: (a.meta || {}).score,
  })).join("")}</div>
        <button class="row-btn right">${icon("right")}</button></div></section>` : ""}
      ${rowHtml("Bu sezon", (seas.results || []).map(catCard), "#/kesfet?sort=POPULARITY_DESC&season=" + season)}
      ${rowHtml("Trend", (trend.results || []).map(catCard), "#/kesfet?sort=TRENDING_DESC")}
      ${libCards.length ? rowHtml("Kütüphanem", libCards, "#/listem") : ""}
      ${forYou && (forYou.results || []).length ? rowHtml(topGenre + " sevdin mi?", forYou.results.map(catCard), "#/kesfet?genre=" + encodeURIComponent(topGenre)) : ""}
      ${rowHtml("En yüksek puanlı", (top.results || []).filter(r => r.score).map(catCard), "#/kesfet?sort=SCORE_DESC")}
      ${rowHtml("Popüler", (pop.results || []).map(catCard), "#/kesfet?sort=POPULARITY_DESC")}
    </div>`;
  wireRows();
  wireHero(heroList);
  if (anyFetching() && !S.homePoll) {
    S.homePoll = poll(async () => {
      try { await loadLib(); } catch (e) { return; }
      updateQueueMini();
      if ((parseHash().parts[0] || "home") !== "home") return;
      if (!anyFetching()) {
        stopPolls();
        await renderHome();
      }
    }, 5000);
  }
}
function heroMarkup(m, list) {
  return `<div class="hero" id="hero">
    <div class="hero-media">${m.banner ? `<img src="${esc(m.banner)}" alt="" referrerpolicy="no-referrer">` : ""}</div>
    <div class="hero-grad"></div>
    <div class="hero-body">
      <div class="hero-kicker">${icon("fire")} Öne çıkan</div>
      <h1 class="hero-title">${esc(m.title)}</h1>
      <div class="hero-meta">
        ${m.score ? `<span class="pill score">${icon("star")}${(m.score / 10).toFixed(1)}</span>` : ""}
        ${m.year ? `<span class="pill">${m.year}</span>` : ""}
        ${m.format ? `<span class="pill">${esc(m.format)}</span>` : ""}
        ${m.episodes ? `<span class="pill">${m.episodes} bölüm</span>` : ""}
        ${(m.genres || []).slice(0, 3).map(g => `<span class="pill">${esc(g)}</span>`).join("")}
      </div>
      <p class="hero-desc">${esc(m.outline || "")}</p>
      <div class="hero-actions">
        <button class="btn accent lg" id="heroAdd">${icon("plus")} Kütüphaneye ekle</button>
        <a class="btn ghost lg" href="#/d/${m.anilistId}">${icon("film")} Detay</a>
        <div class="hero-dots">${list.map((x, i) => `<button class="hero-dot ${i === 0 ? "on" : ""}" data-i="${i}"></button>`).join("")}</div>
      </div>
    </div>
  </div>`;
}
function wireHero(list) {
  const add = $("#heroAdd");
  if (add && list[0]) add.onclick = () => quickAdd(list[0], add);
  $$(".hero-dot").forEach(d => d.onclick = () => {
    const i = Number(d.dataset.i), m = list[i];
    if (!m) return;
    const hero = $("#hero");
    hero.querySelector(".hero-media").innerHTML = m.banner ? `<img src="${esc(m.banner)}" referrerpolicy="no-referrer" alt="">` : "";
    $(".hero-title", hero).textContent = m.title;
    $(".hero-desc", hero).textContent = m.outline || "";
    $(".hero-meta", hero).innerHTML = [
      m.score ? `<span class="pill score">${icon("star")}${(m.score / 10).toFixed(1)}</span>` : "",
      m.year ? `<span class="pill">${m.year}</span>` : "",
      m.format ? `<span class="pill">${esc(m.format)}</span>` : "",
      m.episodes ? `<span class="pill">${m.episodes} bölüm</span>` : "",
      ...(m.genres || []).slice(0, 3).map(g => `<span class="pill">${esc(g)}</span>`),
    ].join("");
    $$(".hero-dot").forEach(x => x.classList.toggle("on", x === d));
    add.onclick = () => quickAdd(m, add);
  });
  if (S.lib.settings.rows !== false && !S.heroTimer) {
    let i = 0;
    S.heroTimer = setInterval(() => {
      if (!document.contains($("#hero"))) return;
      i = (i + 1) % Math.min(list.length, 5);
      const d = $$(".hero-dot")[i];
      if (d) d.click();
    }, 9000);
  }
}
async function quickAdd(media, btn) {
  if (btn) { btn.disabled = true; btn.innerHTML = icon("loader") + " Ekleniyor…"; }
  try {
    const r = await addToLibrary(media);
    await loadLib();
    toast(r.existed ? "Kütüphanede zaten var" : "Kütüphaneye eklendi, bölümler çekiliyor", "ok");
    nav("a/" + r.animeId);
  } catch (e) {
    toast(e.message, "err");
    if (btn) { btn.disabled = false; btn.innerHTML = icon("plus") + " Kütüphaneye ekle"; }
  }
}
function slugify(t) {
  return String(t || "").toLowerCase()
    .replace(/ç/g, "c").replace(/ğ/g, "g").replace(/ı/g, "i")
    .replace(/ö/g, "o").replace(/ş/g, "s").replace(/ü/g, "u")
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "anime";
}

/* ----------------------------------------------------------------- keşfet */
const GENRES = ["Action", "Adventure", "Comedy", "Drama", "Ecchi", "Fantasy",
  "Horror", "Mahou Shoujo", "Mecha", "Music", "Mystery", "Psychological",
  "Romance", "Sci-Fi", "Slice of Life", "Sports", "Supernatural", "Thriller"];
const FORMATS = [["TV", "TV"], ["MOVIE", "Film"], ["OVA", "OVA"], ["ONA", "ONA"], ["SPECIAL", "Special"]];
const SORTS = [["TRENDING_DESC", "Trend"], ["POPULARITY_DESC", "Popüler"],
["SCORE_DESC", "Puan"], ["START_DATE_DESC", "Yeni"], ["FAVOURITES_DESC", "Favori"]];
const YEARS = (() => { const y = new Date().getFullYear() + 1; return Array.from({ length: 26 }, (_, i) => y - i); })();

async function renderDiscover(q) {
  const state = {
    q: q.get("q") || "",
    genre: q.get("genre") || "",
    year: q.get("year") || "",
    format: q.get("format") || "",
    sort: q.get("sort") || "TRENDING_DESC",
    page: Number(q.get("page") || 1),
  };
  const results = [];
  V().innerHTML = `<div class="page">
    <div class="page-head">
      <h1 class="page-title">Keşfet</h1>
      <p class="page-sub">AniList veritabanında ${(results.length ? results.length : "tüm")} animeler — tıkla, kütüphanene ekle.</p>
    </div>
    <div class="filters">
      <div class="chips" id="genreChips">
        <button class="chip ${!state.genre ? "active" : ""}" data-g="">Tümü</button>
        ${GENRES.map(g => `<button class="chip ${state.genre === g ? "active" : ""}" data-g="${g}">${g}</button>`).join("")}
      </div>
      <div class="filter-row">
        <label class="select"><span>Yıl</span><select id="fYear"><option value="">Hepsi</option>
          ${YEARS.map(y => `<option value="${y}" ${String(state.year) === String(y) ? "selected" : ""}>${y}</option>`).join("")}
        </select></label>
        <label class="select"><span>Format</span><select id="fFormat"><option value="">Hepsi</option>
          ${FORMATS.map(([v, l]) => `<option value="${v}" ${state.format === v ? "selected" : ""}>${l}</option>`).join("")}
        </select></label>
        <label class="select"><span>Sırala</span><select id="fSort">
          ${SORTS.map(([v, l]) => `<option value="${v}" ${state.sort === v ? "selected" : ""}>${l}</option>`).join("")}
        </select></label>
        ${state.q ? `<span class="query-tag">“${esc(state.q)}” <a href="#/kesfet">${icon("x")}</a></span>` : ""}
      </div>
    </div>
    <div class="grid" id="dgrid"></div>
    <div class="load-more-wrap"><button class="btn ghost" id="moreBtn" hidden>Daha fazla</button></div>
  </div>`;
  const grid = $("#dgrid");
  const moreBtn = $("#moreBtn");
  const sync = () => {
    const p = new URLSearchParams();
    if (state.q) p.set("q", state.q);
    if (state.genre) p.set("genre", state.genre);
    if (state.year) p.set("year", state.year);
    if (state.format) p.set("format", state.format);
    if (state.sort) p.set("sort", state.sort);
    history.replaceState(null, "", "#/kesfet" + (p.toString() ? "?" + p : ""));
  };
  async function load(append) {
    if (!append) { grid.innerHTML = Array.from({ length: 12 }).map(() => '<div class="sk-card tall"></div>').join(""); }
    moreBtn.disabled = true;
    const p = new URLSearchParams();
    p.set("page", state.page);
    p.set("per", 30);
    p.set("sort", state.sort);
    if (state.q) p.set("q", state.q);
    if (state.genre) p.set("genre", state.genre);
    if (state.year) p.set("year", state.year);
    if (state.format) p.set("format", state.format);
    try {
      const r = await api("/api/browse?" + p.toString());
      const list = r.results || [];
      if (!append) grid.innerHTML = "";
      grid.insertAdjacentHTML("beforeend", list.map(catCard).join(""));
      results.push(...list);
      const info = r.pageInfo || {};
      moreBtn.hidden = !info.hasNextPage;
      $(".page-sub").textContent = info.total
        ? info.total + " anime bulundu" + (state.genre ? " · " + state.genre : "")
        : "Sonuç yok";
    } catch (e) {
      if (!append) grid.innerHTML = `<div class="empty"><div class="big">⚠️</div><h2>Arama başarısız</h2><p>${esc(e.message)}</p></div>`;
    }
    moreBtn.disabled = false;
  }
  $("#genreChips").onclick = (ev) => {
    const b = ev.target.closest(".chip"); if (!b) return;
    state.genre = b.dataset.g; state.page = 1; sync();
    $$("#genreChips .chip").forEach(c => c.classList.toggle("active", c === b));
    load(false);
  };
  $("#fYear").onchange = e => { state.year = e.target.value; state.page = 1; sync(); load(false); };
  $("#fFormat").onchange = e => { state.format = e.target.value; state.page = 1; sync(); load(false); };
  $("#fSort").onchange = e => { state.sort = e.target.value; state.page = 1; sync(); load(false); };
  moreBtn.onclick = () => { state.page += 1; load(true); };
  await load(false);
}

/* ------------------------------------------------------------------ detay */
async function renderDetail(localId, anilistId) {
  V().innerHTML = `<div class="skeleton-hero"></div><div class="sk-detail"></div>`;
  const q = localId ? "?id=" + encodeURIComponent(localId) : "?anilistId=" + encodeURIComponent(anilistId);
  const r = await api("/api/anime" + q);
  const loc = r.local, det = r.detail || {};
  const m = loc ? Object.assign({}, loc.meta || {}, det) : det;
  const title = (loc && loc.title) || m.title || "?";
  const poster = m.poster, banner = m.banner;
  const l = loc ? listOf(loc.id) : {};
  const nxt = loc ? nextEpisode(loc) : null;
  const score = m.score ? (m.score / 10).toFixed(1) : null;
  document.title = "Kino — " + title;
  const statusMap = { watching: "İzleniyor", planned: "Planlandı", completed: "Tamamlandı", onhold: "Beklemede", dropped: "Bırakıldı" };
  V().innerHTML = `<div class="detail">
    <div class="detail-hero">
      ${banner ? `<img class="dh-img" src="${esc(banner)}" alt="" referrerpolicy="no-referrer">`
      : poster ? `<img class="dh-img blur" src="${esc(poster)}" alt="" referrerpolicy="no-referrer">` : ""}
      <div class="dh-grad"></div>
      <div class="dh-inner">
        <div class="detail-poster">${poster ? `<img src="${esc(poster)}" referrerpolicy="no-referrer" alt="">` : `<div class="fallback">${esc(title[0])}</div>`}</div>
        <div class="detail-meta">
          <div class="detail-kicker">${esc((m.format || "") + (m.season ? " · " + m.season : ""))}</div>
          <h1>${esc(title)}</h1>
          ${m.native ? `<div class="detail-native">${esc(m.native)}</div>` : ""}
          <div class="pills">
            ${score ? `<span class="pill score">${icon("star")}${score}</span>` : ""}
            ${m.year ? `<span class="pill">${m.year}</span>` : ""}
            ${m.status ? `<span class="pill">${esc(m.status === "RELEASING" ? "Devam ediyor" : m.status === "FINISHED" ? "Tamamlandı" : m.status)}</span>` : ""}
            ${m.episodes ? `<span class="pill">${m.episodes} bölüm</span>` : ""}
            ${m.duration ? `<span class="pill">${m.duration} dk</span>` : ""}
            ${m.studio ? `<span class="pill">${esc(m.studio)}</span>` : ""}
            ${l.rating ? `<span class="pill mine">${icon("star")}${l.rating}/10</span>` : ""}
          </div>
          <p class="detail-desc">${esc(m.outline || "")}</p>
          <div class="detail-actions">
            <button class="btn ghost lg" id="trackDetail">${icon("bookmark")} ${loc && trackedLocal(loc) ? "Takipten çıkar" : "Takip et"}</button>
            ${loc ? `<a class="btn accent lg" href="${nxt ? "#/p/" + loc.id + "/" + nxt.n : "#/a/" + loc.id}">${icon("play")} ${nxt && progOf(loc.id, nxt.n) ? "Devam et" : "İzle"}</a>`
      : `<button class="btn accent lg" id="addBtn">${icon("plus")} Ekle ve 10 bölüm çek</button>`}
            ${loc ? `<div class="menu-wrap">
              <button class="btn ghost lg" id="listBtn">${icon("bookmark")} ${statusMap[l.status] || "Listeme ekle"} ${icon("down")}</button>
              <div class="menu" id="listMenu">
                ${Object.entries(statusMap).map(([k, v]) => `<button data-st="${k}" class="${l.status === k ? "on" : ""}">${icon("check")}${v}</button>`).join("")}
                <button data-st="" class="${!l.status ? "on" : ""}">${icon("x")}Listeden çıkar</button>
              </div>
            </div>` : ""}
            ${loc ? `<button class="btn ghost lg ${l.favorite ? "fav" : ""}" id="favBtn">${icon("heart")} ${l.favorite ? "Favori" : "Favorile"}</button>` : ""}
            ${loc ? `<label class="rating">${icon("star")}<select id="rateSel">
                <option value="0">Puan</option>
                ${Array.from({ length: 10 }, (_, i) => i + 1).map(n => `<option value="${n}" ${l.rating === n ? "selected" : ""}>${n}/10</option>`).join("")}
              </select></label>` : ""}
            ${loc ? `<button class="btn ghost icon-only" id="moreBtn2" title="Diğer">${icon("layers")}</button>` : ""}
          </div>
        </div>
      </div>
    </div>
    <div class="detail-tabs">
      <button class="tab ${S.detailTab === "eps" ? "active" : ""}" data-tab="eps">Bölümler</button>
      <button class="tab ${S.detailTab === "info" ? "active" : ""}" data-tab="info">Detaylar</button>
      ${(det.recommendations || []).length ? `<button class="tab ${S.detailTab === "rel" ? "active" : ""}" data-tab="rel">Benzerler</button>` : ""}
    </div>
    <div class="tab-body" id="tabBody"></div>
  </div>`;

  const body = $("#tabBody");
  const drawTab = (tab) => {
    S.detailTab = tab;
    $$(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === tab));
    if (tab === "eps") body.innerHTML = episodesTab(loc);
    else if (tab === "info") body.innerHTML = infoTab(m, loc);
    else body.innerHTML = relTab(det.recommendations || []);
    wireTab();
  };
  $$(".tab").forEach(t => t.onclick = () => drawTab(t.dataset.tab));
  drawTab(["eps", "info", "rel"].includes(S.detailTab) ? S.detailTab : "eps");
  if (!loc) drawTab("info");
  $("#trackDetail").onclick = async (e) => {
    const btn = e.currentTarget; btn.disabled = true;
    try {
      if (loc) await api("/api/list", { animeId: loc.id, tracking: !trackedLocal(loc) });
      else await api("/api/add", { media: det, fetchEpisodes: false });
      await loadLib(); toast("Takip kaydedildi", "ok");
      if (document.contains(btn)) route();
    } catch (e) { toast(e.message, "err"); btn.disabled = false; }
  };
  if (m.nextAiring && m.nextAiring.airingAt) {
    $(".detail-desc").insertAdjacentHTML("afterend", `<p class="airing-note">${icon("clock")} Bölüm ${Number(m.nextAiring.episode)} · ${esc(trDate(m.nextAiring.airingAt))} ${trClock(m.nextAiring.airingAt)} · ${esc(airingCountdown(m.nextAiring.airingAt))} (Türkiye)</p>`);
  }

  function wireTab() {
    if (!loc) return;
    const panel = $("#fetchPanel");
    if (panel) {
      const f = loc.fetch || {};
      if (isFetching(loc) && !S.detailPoll) {
        const tick = async () => {
          try { await loadLib(); } catch (e) { return; }
          const fresh = animeById(loc.id);
          if (!fresh) { stopPolls(); return; }
          const still = isFetching(fresh);
          if (!still) toast("Bölüm çekimi bitti", "ok");
          if (S.detailPoll) { clearInterval(S.detailPoll); S.detailPoll = null; }
          await renderDetail(loc.id);
          if (!still) stopPolls();
        };
        S.detailPoll = setInterval(tick, 2500);
        S.timers.push(S.detailPoll);
      }
      const cancel = $("#cancelFetch");
      if (cancel) cancel.onclick = async () => {
        await api("/api/queue/cancel", { animeId: loc.id });
        toast("Çekim iptal edildi"); await loadLib(); renderDetail(loc.id);
      };
      const retry = $("#retryFetch");
      if (retry) retry.onclick = () => startFetch(loc, 10);
    }
    const nextBtn = $("#fetchNext");
    if (nextBtn) nextBtn.onclick = () => startFetch(loc, 10);
    const refreshAll = $("#refreshLinks");
    if (refreshAll) refreshAll.onclick = () => refreshLinks(loc);
    $$(".ep-card").forEach(c => {
      const n = Number(c.dataset.ep);
      c.onclick = () => nav("p/" + loc.id + "/" + n);
      const rb = $(".ep-refresh", c);
      if (rb) rb.onclick = async (ev) => {
        ev.stopPropagation();
        try { await api("/api/refresh", { animeId: loc.id, ep: n }); toast("Bölüm " + n + " yenileniyor", "ok"); }
        catch (e) { toast(e.message, "err"); }
      };
    });
  }

  /* actions */
  if (!loc) {
    $("#addBtn").onclick = (e) => quickAdd(det, e.currentTarget);
  } else {
    $("#listBtn").onclick = (e) => {
      e.stopPropagation();
      $("#listMenu").classList.toggle("open");
    };
    $$("#listMenu button").forEach(b => b.onclick = async (e) => {
      e.stopPropagation();
      $("#listMenu").classList.remove("open");
      await api("/api/list", { animeId: loc.id, status: b.dataset.st });
      await loadLib(); renderDetail(loc.id);
      toast("Liste güncellendi", "ok");
    });
    $("#favBtn").onclick = async () => {
      await api("/api/list", { animeId: loc.id, favorite: !l.favorite });
      await loadLib(); renderDetail(loc.id);
      toast(!l.favorite ? "Favorilere eklendi" : "Favoriden çıkarıldı", "ok");
    };
    const rate = $("#rateSel");
    if (rate) rate.onchange = async () => {
      await api("/api/list", { animeId: loc.id, rating: Number(rate.value) });
      await loadLib(); toast("Puan kaydedildi", "ok");
    };
    const more = $("#moreBtn2");
    if (more) more.onclick = () => openAnimeMenu(loc);
  }
  document.onclick = (e) => {
    if (!e.target.closest(".menu-wrap")) $$(".menu.open").forEach(m => m.classList.remove("open"));
  };
}

function episodesTab(loc) {
  if (!loc) {
    return `<div class="empty"><div class="big">${icon("download")}</div><h2>Henüz kütüphanede değil</h2>
      <p>“Ekle ve 10 bölüm çek” ile ilk 10 bölümün m3u8 linkleri arka planda hazırlanır.</p></div>`;
  }
  const f = loc.fetch || {};
  const doneCount = loc.episodes.filter(e => (progOf(loc.id, e.n) || {}).done).length;
  const panel = (f.status && f.status !== "idle") ? `<div class="fetch-panel ${f.status === "error" ? "err" : f.status === "done" ? "done" : "live"}" id="fetchPanel">
      <div class="fp-row">
        ${isFetching(loc) ? `<span class="qp-spin"></span>` : `<span class="fp-ico">${f.status === "error" ? "!" : "✓"}</span>`}
        <div class="fp-t"><b>${f.status === "queued" ? "Çekim sırada" : f.status === "running" ? "Bölümler çekiliyor" : f.status === "done" ? "Son çekim tamam" : "Çekim hatası"}</b>
          <small>${esc(f.message || "")}</small></div>
        ${f.status === "running" ? `<span class="fp-cnt">${f.got || 0}/${f.requested || 10}</span>` : ""}
        ${isFetching(loc) ? `<button class="btn ghost sm" id="cancelFetch">İptal</button>` : ""}
        ${f.status === "error" ? `<button class="btn ghost sm" id="retryFetch">Tekrar dene</button>` : ""}
      </div>
      ${f.status === "running" ? `<div class="fp-bar"><i style="width:${pct(f.got || 0, f.requested || 10)}%"></i></div>` : ""}
      ${loc.sourcePage ? `<div class="fp-src">kaynak: <a href="${esc(loc.sourcePage)}" target="_blank" rel="noopener">${esc(loc.sourcePage.replace(/^https?:\/\/(www\.)?/, ""))}</a></div>` : ""}
    </div>` : "";
  if (!loc.episodes.length) {
    return `${panel}<div class="empty"><div class="big">⏳</div><h2>Bölümler hazırlanıyor</h2>
      <p>Skill çalışıyor; bölümler geldikçe burada görünecek.</p></div>`;
  }
  return `${panel}
    <div class="eps-head">
      <div class="eps-count">${loc.episodes.length} bölüm · ${doneCount} izlendi</div>
      <div class="eps-actions">
        <button class="btn ghost sm" id="fetchNext">${icon("download")} Sonraki 10 bölümü çek</button>
        <button class="btn ghost sm" id="refreshLinks">${icon("refresh")} Linkleri yenile</button>
      </div>
    </div>
    <div class="ep-grid">
      ${loc.episodes.map(ep => {
    const p = progOf(loc.id, ep.n);
    const st = epStatus(loc.id, ep.n);
    return `<div class="ep-card ${st}" data-ep="${ep.n}" title="Bölüm ${ep.n}">
          <div class="ep-num">${st === "done" ? icon("check") : ep.n}</div>
          <div class="ep-info"><b>Bölüm ${ep.n}</b><small>${st === "done" ? "izlendi" : st === "watching" ? fmtLeft(p.pos, p.dur) : p && p.dur ? fmtTime(p.dur) : "hazır"}</small></div>
          <button class="ep-refresh" title="Linki yenile">${icon("refresh")}</button>
          ${p && p.dur ? `<div class="ep-bar"><i style="width:${pct(p.pos, p.dur)}%"></i></div>` : ""}
        </div>`;
  }).join("")}
    </div>`;
}

function infoTab(m, loc) {
  const rows = [
    ["Tür", (m.genres || []).join(", ")],
    ["Stüdyo", m.studio],
    ["Format", m.format],
    ["Bölüm", m.episodes],
    ["Süre", m.duration ? m.duration + " dk" : ""],
    ["Başlangıç", m.startDate ? [m.startDate.year, m.startDate.month, m.startDate.day].filter(Boolean).join(".") : ""],
    ["Bitiş", m.endDate ? [m.endDate.year, m.endDate.month, m.endDate.day].filter(Boolean).join(".") : ""],
    ["Popülerlik", m.popularity],
    ["AniList", m.anilistId ? "#" + m.anilistId : ""],
  ].filter(r => r[1]);
  return `<div class="info-grid">
    <div class="info-card">
      <h3>Ayrıntılar</h3>
      <dl class="dl">${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
    </div>
    <div class="info-card">
      <h3>Etiketler</h3>
      <div class="pills wrap">${(m.tags || []).map(t => `<span class="pill">${esc(t.name)}</span>`).join("") || "<span class='muted'>—</span>"}</div>
      ${(m.links || []).length ? `<h3 style="margin-top:20px">Bağlantılar</h3>
        <div class="link-list">${m.links.slice(0, 8).map(l => `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.site)} ${icon("external")}</a>`).join("")}</div>` : ""}
    </div>
    ${loc ? `<div class="info-card"><h3>Kütüphane</h3>
      <dl class="dl">
        <dt>Durum</dt><dd>${loc.fetch && loc.fetch.status ? esc(loc.fetch.status) : "—"}</dd>
        <dt>Bölüm</dt><dd>${loc.episodes.length}</dd>
        <dt>Kaynak</dt><dd>${loc.sourcePage ? `<a href="${esc(loc.sourcePage)}" target="_blank" rel="noopener">tranimeizle</a>` : "—"}</dd>
        <dt>Eklenme</dt><dd>${loc.created ? fmtAgo(loc.created) : "—"}</dd>
      </dl></div>` : ""}
  </div>`;
}

function relTab(recs) {
  if (!recs.length) return `<div class="empty">Benzer anime bulunamadı.</div>`;
  return `<div class="grid">${recs.map(catCard).join("")}</div>`;
}

async function startFetch(loc, count) {
  try {
    const r = await api("/api/anime/fetch", { animeId: loc.id, count: count || Number(S.lib.settings.batch) || 10 });
    if (r.queued) toast("Çekim kuyruğa alındı", "ok");
    await loadLib();
    renderDetail(loc.id);
  } catch (e) { toast(e.message, "err"); }
}
async function refreshLinks(loc) {
  if (!loc.episodes.length) return;
  if (!confirm(loc.episodes.length + " bölümün linki yeniden çekilsin mi? Bu işlem uzun sürebilir.")) return;
  try {
    await api("/api/refresh", { animeId: loc.id, all: true });
    await loadLib();
    toast("Tüm linkler kuyruğa alındı", "ok");
    renderDetail(loc.id);
  } catch (e) { toast(e.message, "err"); }
}
function openAnimeMenu(loc) {
  const back = document.createElement("div");
  back.className = "modal-back";
  back.innerHTML = `<div class="modal narrow">
    <header><h2>${esc(loc.title)}</h2><button data-close>${icon("x")}</button></header>
    <div class="mbody menu-list">
      <button id="mFetchNext">${icon("download")} Sonraki 10 bölümü çek</button>
      <button id="mRefresh">${icon("refresh")} Tüm linkleri yenile</button>
      <a href="${loc.sourcePage ? esc(loc.sourcePage) : "#"}" target="_blank" rel="noopener">${icon("external")} Kaynak sayfayı aç</a>
      <button id="mMeta">${icon("refresh")} Poster/bilgileri yenile</button>
      <button class="danger" id="mDelete">${icon("trash")} Kütüphaneden sil</button>
    </div></div>`;
  document.getElementById("modal-root").appendChild(back);
  const close = () => back.remove();
  back.onclick = (e) => { if (e.target === back) close(); };
  $("[data-close]", back).onclick = close;
  $("#mFetchNext", back).onclick = () => { close(); startFetch(loc, 10); };
  $("#mRefresh", back).onclick = () => { close(); refreshLinks(loc); };
  $("#mMeta", back).onclick = async () => {
    close();
    try { await api("/api/lookup", { animeId: loc.id }); await loadLib(); toast("Bilgiler güncellendi", "ok"); renderDetail(loc.id); }
    catch (e) { toast(e.message, "err"); }
  };
  $("#mDelete", back).onclick = async () => {
    if (!confirm('"' + loc.title + '" ve tüm ilerleme silinsin mi?')) return;
    await api("/api/anime/delete", { animeId: loc.id });
    close(); await loadLib(); nav(""); toast("Silindi", "ok");
  };
}

/* ----------------------------------------------------------------- player */
function whenHls() {
  return new Promise(res => {
    if (window.Hls) return res(window.Hls);
    let done = false;
    const fin = () => { if (!done) { done = true; res(window.Hls); } };
    (window.__hlsCbs = window.__hlsCbs || []).push(fin);
    setTimeout(fin, 8000);
  });
}
function playerMsg(text, ms = 2200) {
  const el = $("#pMsg");
  if (!el) return;
  el.textContent = text;
  el.classList.add("show");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove("show"), ms);
}
async function renderPlayer(id, n) {
  await loadLib();
  const a = animeById(id);
  if (!a) {
    V().innerHTML = `<div class="empty"><div class="big">🔍</div><h2>Anime bulunamadı</h2><a class="btn" href="#/">Ana sayfa</a></div>`;
    return;
  }
  const idx = a.episodes.findIndex(e => e.n === n);
  const ep = a.episodes[idx];
  if (!ep) {
    const none = !a.episodes.length;
    const f = a.fetch || {};
    V().innerHTML = `<div class="empty"><div class="big">${none ? "⬇️" : "🎬"}</div>
      <h2>${none ? "Bölümler henüz çekilmedi" : "Bölüm " + esc(String(n)) + " yok"}</h2>
      <p>${none ? (f.status === "error" ? "Son deneme: " + esc(f.message || "hata") : "Bu anime için m3u8 linkleri kuyruğa alınmadı.") : "Bu bölüm henüz çekilmedi."}</p>
      <div class="p-nav" style="justify-content:center">
        ${none ? `<button class="btn accent" id="pFetchFirst">${icon("download")} İlk ${Number((S.lib.settings || {}).batch) || 10} bölümü çek</button>` : ""}
        <a class="btn ghost" href="#/a/${a.id}">${icon("film")} Detaya git</a>
        <a class="btn ghost" href="#/kesfet">${icon("compass")} Keşfet</a>
      </div></div>`;
    const fb = $("#pFetchFirst");
    if (fb) fb.onclick = async () => {
      fb.disabled = true; fb.textContent = "Kuyruğa alınıyor…";
      try {
        await api("/api/anime/fetch", { animeId: a.id });
        toast("Bölümler çekiliyor, detay sayfasından izleyebilirsin", "ok");
        nav("a/" + a.id);
      } catch (e) { toast(e.message, "err"); fb.disabled = false; }
    };
    return;
  }
  const prev = idx > 0 ? a.episodes[idx - 1] : null;
  const next = idx >= 0 && idx + 1 < a.episodes.length ? a.episodes[idx + 1] : null;
  const p = progOf(a.id, ep.n) || {};
  const st = S.lib.settings || {};
  document.title = "Kino — " + a.title + " · Bölüm " + ep.n;
  V().innerHTML = `<div class="player-page">
    <div class="p-top">
      <a class="icon-btn" href="#/a/${a.id}" title="Geri">${icon("left")}</a>
      <div class="p-title">
        <b>${esc(a.title)}</b>
        <small>Bölüm ${ep.n}${a.episodes.length ? " · " + a.episodes.length + " bölüm" : ""}</small>
      </div>
      <div class="p-tools">
        <button class="btn ghost sm" id="pRamMode" title="Bu oynatımda RAM hazırlamayı aç veya kapat">RAM ${st.ramPlayback === true ? "açık" : "kapalı"}</button>
        <label class="p-sel" title="Kalite"><select id="pQuality"><option value="-1">Oto</option></select></label>
        <label class="p-sel" title="Hız"><select id="pSpeed">
          ${[0.75, 1, 1.25, 1.5, 2].map(s => `<option value="${s}" ${s === 1 ? "selected" : ""}>${s}x</option>`).join("")}
        </select></label>
        <button class="icon-btn" id="pPip" title="PiP">${icon("pip")}</button>
        <button class="icon-btn" id="pNextBtn" title="Sonraki bölüm" ${next ? "" : "disabled"}>${icon("right")}</button>
      </div>
    </div>
    <div class="p-stage" id="pStage">
      <video id="video" playsinline controls preload="metadata"></video>
      <div class="p-loading" id="pLoading"><span class="qp-spin"></span> yükleniyor…</div>
      <div class="p-msg" id="pMsg"></div>
      <div class="p-next" id="pNextOverlay" hidden></div>
      <div class="p-err" id="pErr" hidden></div>
      <div class="ram-prepare" id="pRamPrepare" hidden></div>
    </div>
    <div class="ram-status" id="pRamStatus" aria-live="polite"></div>
    <div class="p-below">
      <div class="p-info">
        <h1>${esc(a.title)}</h1>
        <div class="p-sub">
          <span class="pill">Bölüm ${ep.n}</span>
          ${(a.meta || {}).year ? `<span class="pill">${(a.meta || {}).year}</span>` : ""}
          ${(a.meta || {}).score ? `<span class="pill score">${icon("star")}${((a.meta || {}).score / 10).toFixed(1)}</span>` : ""}
          ${p.pos && !p.done ? `<span class="pill mine">${icon("clock")}${fmtTime(p.pos)} kaldığın yer</span>` : ""}
        </div>
      </div>
      <div class="p-nav">
        ${prev ? `<a class="btn ghost" href="#/p/${a.id}/${prev.n}">${icon("left")} Bölüm ${prev.n}</a>` : ""}
        <a class="btn ghost" href="#/a/${a.id}">${icon("film")} Bölümler</a>
        ${next ? `<a class="btn accent" href="#/p/${a.id}/${next.n}">Bölüm ${next.n} ${icon("right")}</a>` : ""}
      </div>
    </div>
  </div>`;

  const video = $("#video");
  const stage = $("#pStage");
  const loading = $("#pLoading");
  const errBox = $("#pErr");
  let hls = null;
  let lastSave = 0;
  let nextTimer = null;
  let loadSerial = 0;
  const ram = new KinoRamPlayer(a.id, ep.n, st.ramPlayback === true);

  S.player = { id: a.id, ep: ep.n, video, save: null,
    stop: () => { if (nextTimer) { clearInterval(nextTimer); nextTimer = null; }
      ram.stop();
      if (hls) { try { hls.destroy(); } catch (e) { } hls = null; } } };

  const showError = (msg) => {
    loading.hidden = true;
    errBox.hidden = false;
    errBox.innerHTML = `<div class="perr-card">
      <div class="big">⚠️</div>
      <h2>Oynatma sorunu</h2>
      <p>${esc(msg)}</p>
      <div class="perr-actions">
        <button class="btn accent" id="pRetry">${icon("refresh")} Tekrar dene</button>
        <button class="btn ghost" id="pRelink">${icon("download")} Linki yenile</button>
        <a class="btn ghost" href="#/a/${a.id}">${icon("left")} Bölümler</a>
      </div>
      <small class="muted">Kaynak: ${esc(((ep.url || "").match(/^https?:\/\/([^/]+)/) || [])[1] || "bilinmiyor")}</small>
    </div>`;
    $("#pRetry").onclick = () => load();
    $("#pRelink").onclick = async () => {
      try {
        await api("/api/refresh", { animeId: a.id, ep: ep.n });
        playerMsg("Link yenileniyor…");
        let tries = 0;
        const iv = setInterval(async () => {
          tries++;
          if (!document.contains(video)) { clearInterval(iv); return; }
          try { await loadLib(); } catch (e) { }
          const fresh = animeById(a.id);
          const fe = fresh && fresh.episodes.find(x => x.n === ep.n);
          if (fe && fe.url && fe.url !== ep.url) { clearInterval(iv); ep.url = fe.url; load(); }
          else if (tries > 60) { clearInterval(iv); showError("Link yenilenemedi. Kuyruğa bak."); }
        }, 3000);
      } catch (e) { toast(e.message, "err"); }
    };
  };

  const save = async (done = false) => {
    const dur = video.duration || 0;
    if (!dur || !isFinite(dur)) return;
    const pos = done ? dur : video.currentTime;
    try {
      await api("/api/progress", { animeId: a.id, ep: ep.n, pos, dur, done });
      const key = a.id + ":" + ep.n;
      S.lib.progress[key] = { pos, dur, done, updated: Math.floor(Date.now() / 1000) };
    } catch (e) { }
  };

  const scheduleNext = () => {
    if (nextTimer) { clearInterval(nextTimer); nextTimer = null; }
    const overlay = $("#pNextOverlay");
    if (!overlay) return;
    if (!next) {
      overlay.hidden = false;
      const freshNow = animeById(a.id);
      const fetching = freshNow ? isFetching(freshNow) : isFetching(a);
      overlay.innerHTML = `<div class="pnext-card">
        <h3>Son bölümdesin</h3>
        <p>${fetching ? "Sonraki bölümler çekiliyor…" : "Kütüphanede başka bölüm yok."}</p>
        <div class="pnext-actions">
          ${fetching ? `<span class="qp-spin"></span>` : `<button class="btn accent" id="pFetchMore">${icon("download")} Sonraki 10 bölümü çek</button>`}
          <a class="btn ghost" href="#/a/${a.id}">Bölümler</a>
        </div>
      </div>`;
      const fb = $("#pFetchMore");
      if (fb) fb.onclick = async () => {
        fb.disabled = true; fb.innerHTML = "Kuyruğa alınıyor…";
        try { await api("/api/anime/fetch", { animeId: a.id, count: 10 }); await loadLib(); scheduleNext(); }
        catch (e) { toast(e.message, "err"); }
      };
      if (fetching) poll(async () => {
        await loadLib();
        const fresh = animeById(a.id);
        if (!fresh) { stopPolls(); return; }
        if (fresh.episodes.length > a.episodes.length) { stopPolls(); location.reload(); return; }
        if (!isFetching(fresh)) { stopPolls(); scheduleNext(); }
      }, 4000);
      return;
    }
    const enabled = st.autoplayNext !== false;
    const countdown = Math.max(3, Number(st.autoplayCountdown) || 8);
    let left = countdown;
    overlay.hidden = false;
    const draw = () => {
      overlay.innerHTML = `<div class="pnext-card">
        <div class="pnext-kicker">Sıradaki</div>
        <h3>Bölüm ${next.n}</h3>
        <p>${enabled ? left + " saniye içinde başlıyor" : "Otomatik geçiş kapalı"}</p>
        <div class="pnext-actions">
          <a class="btn accent" href="#/p/${a.id}/${next.n}">${icon("play")} Şimdi</a>
          <a class="btn ghost" href="#/a/${a.id}">Bölümler</a>
        </div>
        <div class="pnext-bar"><i style="width:${(countdown - left) / countdown * 100}%"></i></div>
      </div>`;
    };
    draw();
    if (!enabled) return;
    nextTimer = setInterval(() => {
      left -= 1;
      if (left <= 0) {
        clearInterval(nextTimer);
        nav("p/" + a.id + "/" + next.n);
      } else draw();
    }, 1000);
  };

  const bind = () => {
    video.onerror = () => showError("Video yüklenemedi. Link ölmüş olabilir.");
    video.onloadedmetadata = () => {
      loading.hidden = true;
      const saved = progOf(a.id, ep.n);
      if (saved && !saved.done && saved.pos > 15 && saved.pos < (saved.dur || video.duration) - 20) {
        video.currentTime = saved.pos;
        playerMsg("Kaldığın yerden devam: " + fmtTime(saved.pos), 3200);
      }
    };
    video.onplay = () => { loading.hidden = true; };
    video.onwaiting = () => { if (!video.paused) loading.hidden = false; };
    video.onplaying = () => { loading.hidden = true; };
    video.ontimeupdate = () => {
      ram.tick(video);
      const now = Date.now();
      if (now - lastSave > 5000) { lastSave = now; save(false); }
      if (video.duration && video.currentTime > video.duration - 0.6) { save(true); }
    };
    video.onended = () => { save(true); scheduleNext(); };
    video.onpause = () => save(false);
    $("#pSpeed").onchange = (e) => { video.playbackRate = Number(e.target.value); };
    $("#pPip").onclick = async () => {
      try {
        if (document.pictureInPictureElement) await document.exitPictureInPicture();
        else await video.requestPictureInPicture();
      } catch (e) { playerMsg("PiP desteklenmiyor"); }
    };
    $("#pNextBtn").onclick = () => next && nav("p/" + a.id + "/" + next.n);
    $("#pQuality").onchange = (e) => {
      if (!hls) return;
      const v = Number(e.target.value);
      hls.currentLevel = v;
      playerMsg(v < 0 ? "Otomatik kalite" : "Kalite: " + ((hls.levels[v] || {}).height || "?") + "p");
    };
    stage.ondblclick = () => {
      if (document.fullscreenElement) document.exitFullscreen();
      else stage.requestFullscreen && stage.requestFullscreen();
    };
    const onUnload = () => save(false);
    const onVis = () => { if (document.hidden) save(false); };
    window.addEventListener("beforeunload", onUnload);
    document.addEventListener("visibilitychange", onVis);
    S.player.onUnload = onUnload; S.player.onVis = onVis;
  };

  const load = async () => {
    const serial = ++loadSerial;
    errBox.hidden = true;
    loading.hidden = false;
    loading.innerHTML = '<span class="qp-spin"></span> yükleniyor…';
    if (hls) { try { hls.destroy(); } catch (e) { } hls = null; }
    video.removeAttribute("src");
    video.load();
    const Hls = await whenHls();
    if (!document.contains(video)) return;  // sirada sayfa degismis; eski elemana hls acma
    const url = ep.url;
    if (!url) return showError("Bu bölümün linki yok.");
    const ref = a.sourcePage || "https://www.tranimeizle.live/";
    const streamSrc = "/px?u=" + encodeURIComponent(url) + "&ref=" + encodeURIComponent(ref);
    loading.hidden = true;
    const cachedSrc = await ram.prepare();
    if (!document.contains(video) || serial !== loadSerial) return;
    const src = cachedSrc || streamSrc;
    loading.hidden = false;
    $("#pRamMode").textContent = ram.enabled ? "RAM açık" : "RAM kapalı";
    if (Hls && Hls.isSupported()) {
      hls = new Hls({ maxBufferLength: 30, capLevelToPlayerSize: true });
      hls.loadSource(src);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, (_, data) => {
        const sel = $("#pQuality");
        const levels = (data.levels || []).map((l, i) => ({ h: l.height, i })).filter(x => x.h);
        levels.sort((x, y) => y.h - x.h);
        sel.innerHTML = '<option value="-1">Oto</option>' +
          levels.map(l => `<option value="${l.i}">${l.h}p</option>`).join("");
        sel.disabled = !!cachedSrc;
        if (cachedSrc) sel.innerHTML = `<option>${ram.entry?.height ? ram.entry.height + "p" : "Kaynak"} · RAM</option>`;
        video.play().catch(() => { });
      });
      let retries = 0;
      hls.on(Hls.Events.ERROR, (_, data) => {
        if (!data.fatal) return;
        retries += 1;
        if (data.type === Hls.ErrorTypes.NETWORK_ERROR && retries <= 4) {
          playerMsg("Ağ hatası, tekrar deneniyor… (" + retries + "/4)");
          setTimeout(() => hls && hls.startLoad(), 1200 * retries);
        } else if (data.type === Hls.ErrorTypes.MEDIA_ERROR && retries <= 3) {
          playerMsg("Medya hatası, kurtarılıyor…");
          hls.recoverMediaError();
        } else {
          showError("Kaynak oynatılamadı (" + (data.details || "bilinmeyen") + ")");
        }
      });
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = src;
      video.addEventListener("loadedmetadata", () => video.play().catch(() => { }), { once: true });
    } else {
      showError("Tarayıcı HLS desteklemiyor.");
    }
  };

  S.player.save = save;
  $("#pRamMode").onclick = async () => {
    await save(false);
    if (ram.enabled) { await ram.useStream(); load(); }
    else { ram.enabled = true; load(); }
  };
  bind();
  load();
  /* 9. bölüm kuralı: sonraki 10'u tetikle */
  if (next) {
    api("/api/ep/open", { animeId: a.id, ep: ep.n }).catch(() => { });
  }
  document.addEventListener("keydown", S.player.keys = (e) => {
    if (!S.player) return;
    const tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "select" || tag === "textarea") return;
    if (e.code === "Space") { e.preventDefault(); video.paused ? video.play() : video.pause(); }
    else if (e.code === "ArrowRight") { video.currentTime += 5; playerMsg("+5 sn"); }
    else if (e.code === "ArrowLeft") { video.currentTime -= 5; playerMsg("-5 sn"); }
    else if (e.key === "f") { stage.requestFullscreen ? (document.fullscreenElement ? document.exitFullscreen() : stage.requestFullscreen()) : null; }
    else if (e.key === "m") { video.muted = !video.muted; playerMsg(video.muted ? "Sessiz" : "Ses açık"); }
    else if (e.key === "n" && next) nav("p/" + a.id + "/" + next.n);
  });
}

/* ------------------------------------------------------------------ listem */
const LIST_TABS = [["all", "Tümü"], ["watching", "İzleniyor"], ["planned", "Planlandı"],
["completed", "Tamamlandı"], ["onhold", "Beklemede"], ["dropped", "Bırakıldı"], ["fav", "Favoriler"]];
async function renderList() {
  const active = new URLSearchParams((location.hash.split("?")[1] || "")).get("st") || "all";
  const entries = S.lib.animes.map(a => ({ a, l: listOf(a.id) }));
  const counts = { all: entries.length };
  LIST_TABS.forEach(([k]) => {
    counts[k] = k === "fav" ? entries.filter(x => x.l.favorite).length
      : entries.filter(x => x.l.status === k).length;
  });
  V().innerHTML = `<div class="page">
    <div class="page-head"><h1 class="page-title">Listem</h1>
      <p class="page-sub">${entries.length} anime kütüphanende — durum, favori ve puanların burada.</p></div>
    <div class="list-tabs">
      ${LIST_TABS.map(([k, label]) => `<a class="ltab ${active === k ? "active" : ""}" href="#/listem?st=${k}">${label}<span>${counts[k] || 0}</span></a>`).join("")}
    </div>
    <div class="grid" id="listGrid"></div>
  </div>`;
  const items = entries.filter(({ l }) => active === "fav" ? l.favorite
    : active === "all" ? true : l.status === active);
  const grid = $("#listGrid");
  if (!items.length) {
    grid.innerHTML = `<div class="empty span-all"><div class="big">${icon("bookmark")}</div>
      <h2>Burada henüz bir şey yok</h2><p>Keşfet'ten anime ekle, listeler burada birikir.</p>
      <a class="btn accent" href="#/kesfet">${icon("compass")} Keşfet</a></div>`;
    return;
  }
  grid.innerHTML = items.sort((x, y) => (y.l.updated || y.a.created || 0) - (x.l.updated || x.a.created || 0))
    .map(({ a, l }) => libCard(a, {
      sub: [l.status && LIST_TABS.find(t => t[0] === l.status) ? LIST_TABS.find(t => t[0] === l.status)[1] : "", l.rating ? "★ " + l.rating : ""].filter(Boolean).join(" · ") || ((a.meta || {}).year || ""),
      prog: (() => { const e = nextEpisode(a); const p = e && progOf(a.id, e.n); return p && p.dur ? pct(p.pos, p.dur) : 0; })(),
    })).join("");
}

/* -------------------------------------------------------------- istatistik */
async function renderStats() {
  V().innerHTML = `<div class="page"><div class="page-head"><h1 class="page-title">İstatistik</h1>
    <p class="page-sub">İzleme alışkanlıkların.</p></div><div class="stat-cards">${Array.from({ length: 4 }).map(() => '<div class="sk-card sm"></div>').join("")}</div></div>`;
  const { stats } = await api("/api/stats");
  const hours = (stats.seconds / 3600);
  const pad = (n) => String(n).padStart(2, "0");
  const dayKeys = [];
  for (let i = 13; i >= 0; i--) {
    const d = new Date(Date.now() - i * 86400000);
    dayKeys.push(d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()));
  }
  const maxDay = Math.max(1, ...dayKeys.map(k => stats.days[k] || 0));
  const maxG = Math.max(1, ...(stats.topGenres || []).map(g => g.count));
  const recent = (S.lib.history || []).slice(-12).reverse();
  V().innerHTML = `<div class="page">
    <div class="page-head"><h1 class="page-title">İstatistik</h1>
      <p class="page-sub">${stats.animes} anime · ${stats.onList} listede · ${stats.favorites} favori</p></div>
    <div class="stat-cards">
      <div class="stat-card"><span>Toplam izleme</span><b>${hours >= 1 ? hours.toFixed(1) + " sa" : Math.round(stats.seconds / 60) + " dk"}</b><small>${stats.seconds} saniye</small></div>
      <div class="stat-card"><span>Biten bölüm</span><b>${stats.episodesDone}</b><small>tamamlandı</small></div>
      <div class="stat-card"><span>Kütüphane</span><b>${stats.animes}</b><small>kütüphanede</small></div>
      <div class="stat-card"><span>Seri</span><b>${stats.streak} gün</b><small>üst üste izleme</small></div>
    </div>
    <div class="stat-grid">
      <div class="chart-card">
        <h3>Son 14 gün</h3>
        <div class="chart">
          ${dayKeys.map(k => `<div class="chart-col" title="${k}: ${stats.days[k] || 0} bölüm">
            <div class="chart-bar-wrap"><i style="height:${(stats.days[k] || 0) / maxDay * 100}%"></i></div>
            <span>${k.slice(8)}</span></div>`).join("")}
        </div>
      </div>
      <div class="chart-card">
        <h3>Türler</h3>
        ${(stats.topGenres || []).length ? stats.topGenres.map(g => `<div class="genre-row">
          <span>${esc(g.genre)}</span><div class="genre-bar"><i style="width:${g.count / maxG * 100}%"></i></div><b>${g.count}</b>
        </div>`).join("") : '<p class="muted">Henüz veri yok.</p>'}
      </div>
      <div class="chart-card wide">
        <h3>Son izlenenler</h3>
        ${recent.length ? `<div class="recent-list">${recent.map(h => {
    const a = animeById(h.animeId);
    if (!a) return "";
    return `<a class="recent-item" href="#/p/${a.id}/${h.ep}">
              <div class="recent-poster">${(a.meta || {}).poster ? `<img src="${esc((a.meta || {}).poster)}" referrerpolicy="no-referrer" alt="">` : ""}</div>
              <div><b>${esc(a.title)}</b><small>Bölüm ${h.ep} · ${fmtAgo(h.at)}</small></div>
              <span class="icon-btn sm">${icon("play")}</span></a>`;
  }).join("")}</div>` : '<p class="muted">Henüz izleme geçmişi yok.</p>'}
      </div>
    </div>
  </div>`;
}

/* ------------------------------------------------------------------ kuyruk */
async function renderQueue() {
  V().innerHTML = `<div class="page"><div class="page-head"><h1 class="page-title">Kuyruk</h1>
    <p class="page-sub">Bölüm çekimleri tek worker ile sırayla çalışır.</p></div>
    <div class="queue" id="queueWrap"></div></div>`;
  let selected = null;
  const draw = async () => {
    let q;
    try { q = (await api("/api/queue")).queue; } catch (e) { return; }
    const wrap = $("#queueWrap");
    if (!wrap) return;
    const recent = S.lib.animes
      .filter(a => a.fetch && (a.fetch.status === "done" || a.fetch.status === "error"))
      .sort((x, y) => (y.fetch.finished || 0) - (x.fetch.finished || 0))
      .slice(0, 5);
    if (!selected || (!q.items.find(i => i.animeId === selected) && !recent.find(a => a.id === selected))) {
      const running = q.items.find(i => i.status === "running");
      selected = (running && running.animeId) || (q.items[0] && q.items[0].animeId)
        || (recent[0] && recent[0].id) || null;
    }
    wrap.innerHTML = `
      <div class="q-top">
        <div class="q-stat"><b>${q.items.filter(i => i.status === "running").length}</b><span>çalışıyor</span></div>
        <div class="q-stat"><b>${q.items.filter(i => i.status === "queued").length}</b><span>sırada</span></div>
        <div class="q-stat"><b>1</b><span>worker</span></div>
        <div class="q-stat"><b>${S.lib.animes.length}</b><span>kütüphane</span></div>
        <button class="btn ghost sm" id="qRefresh">${icon("refresh")} Yenile</button>
      </div>
      <div class="q-body">
        <div class="q-list">
          ${q.items.map(it => `
            <div class="q-item ${it.status} ${selected === it.animeId ? "sel" : ""}" data-id="${it.animeId}">
              <div class="q-item-top">
                ${it.status === "running" ? '<span class="qp-spin"></span>' : `<span class="q-wait">${icon("clock")}</span>`}
                <div class="q-item-t"><b>${esc(it.title)}</b><small>${esc(it.message || "")}</small></div>
                <span class="q-cnt">${it.got || 0}/${it.requested || 10}</span>
              </div>
              <div class="q-bar"><i style="width:${pct(it.got || 0, it.requested || 10)}%"></i></div>
              <div class="q-actions">
                <a class="btn ghost sm" href="#/a/${it.animeId}">Detay</a>
                <button class="btn danger sm" data-cancel="${it.animeId}">İptal</button>
              </div>
            </div>`).join("")}
          ${recent.length ? `<div class="q-sec">Son işler</div>` + recent.map(a => `
            <div class="q-item done ${a.fetch.status === "error" ? "err" : ""} ${selected === a.id ? "sel" : ""}" data-id="${a.id}">
              <div class="q-item-top">
                <span class="q-wait">${a.fetch.status === "error" ? icon("x") : icon("check")}</span>
                <div class="q-item-t"><b>${esc(a.title)}</b><small>${esc(a.fetch.message || "")} · ${fmtAgo(a.fetch.finished)}</small></div>
                <span class="q-cnt">${a.episodes.length} bölüm</span>
              </div>
            </div>`).join("") : ""}
          ${!q.items.length && !recent.length ? `<div class="empty"><div class="big">${icon("check")}</div><h2>Kuyruk boş</h2><p>Çekim yok — her şey hazır.</p><a class="btn accent" href="#/kesfet">Anime ekle</a></div>` : ""}
        </div>
        <div class="q-log-card">
          <div class="q-log-head"><b>Canlı log</b><span>${selected ? esc((animeById(selected) || {}).title || selected) : "—"}</span></div>
          <pre class="q-log" id="qLog">${selected ? "yükleniyor…" : "log yok"}</pre>
        </div>
      </div>`;
    $("#qRefresh").onclick = () => draw();
    $$(".q-item").forEach(el => el.onclick = (e) => {
      if (e.target.closest("[data-cancel]") || e.target.tagName === "A") return;
      selected = el.dataset.id; draw();
    });
    $$("[data-cancel]").forEach(b => b.onclick = async (e) => {
      e.stopPropagation();
      await api("/api/queue/cancel", { animeId: b.dataset.cancel });
      toast("İptal edildi"); await loadLib(); draw();
    });
    if (selected) {
      try {
        const r = await api("/api/log?animeId=" + encodeURIComponent(selected));
        const log = $("#qLog");
        if (log) {
          log.textContent = (r.lines || []).slice(-120).join("\n") || "log yok";
          log.scrollTop = log.scrollHeight;
        }
      } catch (e) { }
    }
  };
  await draw();
  poll(draw, 2200);
}

/* ------------------------------------------------------------------ ayarlar */
async function renderSettings() {
  const st = S.lib.settings || {};
  const themes = [["violet", "Mor"], ["emerald", "Yeşil"], ["rose", "Gül"], ["amber", "Amber"], ["cyan", "Camgöbeği"]];
  V().innerHTML = `<div class="page narrow-page">
    <div class="page-head"><h1 class="page-title">Ayarlar</h1>
      <p class="page-sub">Player, kütüphane ve görünüm tercihleri.</p></div>
    <div class="settings">
      <section class="set-card">
        <h3>Player</h3>
        <div class="set-row">
          <div><b>Otomatik sonraki bölüm</b><small>Bölüm bitince sıradakine geç</small></div>
          <label class="switch"><input type="checkbox" id="sAuto" ${st.autoplayNext !== false ? "checked" : ""}><i></i></label>
        </div>
        <div class="set-row">
          <div><b>Geri sayım</b><small>Otomatik geçiş öncesi bekleme</small></div>
          <select id="sCount">${[3, 5, 8, 10, 15].map(n => `<option value="${n}" ${Number(st.autoplayCountdown) === n ? "selected" : ""}>${n} sn</option>`).join("")}</select>
        </div>
        <div class="set-row">
          <div><b>Varsayılan çekim adedi</b><small>Yeni animede ilk parti bölüm</small></div>
          <select id="sBatch">${[5, 10, 15, 20].map(n => `<option value="${n}" ${Number(st.batch) === n ? "selected" : ""}>${n} bölüm</option>`).join("")}</select>
        </div>
      </section>
      <section class="set-card">
        <h3>Görünüm</h3>
        <div class="set-row">
          <div><b>Tema rengi</b><small>Arayüz vurgusu</small></div>
          <div class="theme-dots">${themes.map(([k, l]) => `<button class="theme-dot ${k}" data-theme="${k}" title="${l}"></button>`).join("")}</div>
        </div>
        <div class="set-row">
          <div><b>Ana sayfa satırları</b><small>Hero otomatik dönsün</small></div>
          <label class="switch"><input type="checkbox" id="sRows" ${st.rows !== false ? "checked" : ""}><i></i></label>
        </div>
        <div class="set-row">
          <div><b>Hareketi azalt</b><small>Animasyonları kapat</small></div>
          <label class="switch"><input type="checkbox" id="sMotion" ${st.reduceMotion ? "checked" : ""}><i></i></label>
        </div>
      </section>
      <section class="set-card">
        <h3>Veri</h3>
        <div class="set-row">
          <div><b>Kütüphaneyi indir</b><small>data.json yedeği</small></div>
          <a class="btn ghost sm" href="/api/library" download="kino-data.json">${icon("download")} İndir</a>
        </div>
        <div class="set-row">
          <div><b>İzleme geçmişini temizle</b><small>İstatistikler sıfırlanır, ilerleme kalır</small></div>
          <button class="btn danger sm" id="sClearHist">${icon("trash")} Temizle</button>
        </div>
        <div class="set-row">
          <div><b>Sürüm</b><small>Kino v2 · AniList + tranimeizle</small></div>
          <span class="muted">localhost:8484</span>
        </div>
      </section>
    </div>
  </div>`;
  const set = async (patch, msg) => {
    try {
      const r = await api("/api/settings", patch);
      S.lib.settings = r.settings;
      applySettings();
      if (msg) toast(msg, "ok");
    } catch (e) { toast(e.message, "err"); }
  };
  $("#sAuto").onchange = e => set({ autoplayNext: e.target.checked }, "Kaydedildi");
  $("#sCount").onchange = e => set({ autoplayCountdown: Number(e.target.value) }, "Kaydedildi");
  $("#sBatch").onchange = e => set({ batch: Number(e.target.value) }, "Kaydedildi");
  $("#sRows").onchange = e => set({ rows: e.target.checked }, "Kaydedildi");
  $("#sMotion").onchange = e => set({ reduceMotion: e.target.checked }, "Kaydedildi");
  $$(".theme-dot").forEach(b => b.onclick = () => set({ theme: b.dataset.theme }, "Tema: " + b.title));
  $("#sClearHist").onclick = async () => {
    if (!confirm("İzleme geçmişi silinsin mi? İlerleme ve kütüphane korunur.")) return;
    try {
      await api("/api/history/clear", {});
      S.lib.history = [];
      toast("Geçmiş temizlendi", "ok");
    } catch (e) { toast(e.message, "err"); }
  };
  renderRamSettings();
}

/* ----------------------------------------------------------- komut paleti */
const PAGES = [
  { label: "Ana Sayfa", href: "#/", icon: "home", hint: "g" },
  { label: "Güncel & Takip", href: "#/guncel", icon: "clock", hint: "yeni bölümler" },
  { label: "Keşfet", href: "#/kesfet", icon: "compass", hint: "" },
  { label: "Takvim", href: "#/takvim", icon: "calendar", hint: "" },
  { label: "Listem", href: "#/listem", icon: "bookmark", hint: "" },
  { label: "İstatistik", href: "#/istatistik", icon: "chart", hint: "" },
  { label: "Kuyruk", href: "#/kuyruk", icon: "download", hint: "" },
  { label: "Ayarlar", href: "#/ayarlar", icon: "settings", hint: "" },
];
function openPalette() {
  const p = $("#palette");
  p.hidden = false;
  S.palette.open = true;
  $("#paletteInput").value = "";
  paletteDraw("");
  setTimeout(() => $("#paletteInput").focus(), 30);
}
function closePalette() {
  const p = $("#palette");
  if (!p) return;
  p.hidden = true;
  S.palette.open = false;
  clearTimeout(S.palette.timer);
}
async function paletteDraw(q) {
  const list = $("#paletteList");
  const query = q.trim();
  let items = PAGES.filter(x => !query || x.label.toLowerCase().includes(query.toLowerCase()))
    .map(x => ({ ...x, type: "Sayfa" }));
  const locals = S.lib.animes.filter(a => !query || a.title.toLowerCase().includes(query.toLowerCase()))
    .slice(0, 6).map(a => ({ label: a.title, href: "#/a/" + a.id, icon: "film", hint: "kütüphane", type: "Kütüphane" }));
  items = items.concat(locals);
  if (query.length >= 2) {
    clearTimeout(S.palette.timer);
    S.palette.timer = setTimeout(async () => {
      try {
        const r = await api("/api/search?q=" + encodeURIComponent(query));
        const remote = (r.results || []).slice(0, 6).map(m => ({
          label: m.title, href: "#/d/" + m.anilistId, icon: "compass",
          hint: [m.year, m.format].filter(Boolean).join(" · "), type: "AniList",
        }));
        S.palette.items = items.concat(remote);
        renderPaletteList();
      } catch (e) { }
    }, 260);
  }
  S.palette.items = items;
  S.palette.sel = 0;
  renderPaletteList();
}
function renderPaletteList() {
  const list = $("#paletteList");
  const items = S.palette.items || [];
  if (!items.length) { list.innerHTML = `<div class="palette-empty">sonuç yok</div>`; return; }
  list.innerHTML = items.map((it, i) => `<a class="palette-item ${i === S.palette.sel ? "sel" : ""}" href="${it.href}" data-i="${i}">
      ${icon(it.icon || "search")}
      <span class="pi-label">${esc(it.label)}</span>
      <span class="pi-hint">${esc(it.hint || "")}</span>
      <span class="pi-type">${esc(it.type || "")}</span>
    </a>`).join("");
  $$(".palette-item").forEach(el => {
    el.onmouseenter = () => { S.palette.sel = Number(el.dataset.i); renderPaletteList(); };
    el.onclick = () => closePalette();
  });
}
function paletteKey(e) {
  if (!S.palette.open) return;
  const items = S.palette.items || [];
  if (e.key === "ArrowDown") {
    e.preventDefault();
    S.palette.sel = (S.palette.sel + 1) % Math.max(1, items.length);
    renderPaletteList();
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    S.palette.sel = (S.palette.sel - 1 + items.length) % Math.max(1, items.length);
    renderPaletteList();
  } else if (e.key === "Enter") {
    const it = items[S.palette.sel];
    if (it) { closePalette(); location.hash = it.href; }
  } else if (e.key === "Escape") {
    closePalette();
  }
}

/* -------------------------------------------------------------------- boot */
function boot() {
  paintIcons();
  renderNav("home");
  updateQueueMini();
  $("#globalSearch").onsubmit = (e) => {
    e.preventDefault();
    const q = $("#searchInput").value.trim();
    nav("kesfet" + (q ? "?q=" + encodeURIComponent(q) : ""));
    $("#searchInput").blur();
  };
  $("#menuBtn").onclick = () => document.body.classList.toggle("sidebar-open");
  $("#brandBtn").onclick = () => nav("");
  $("#cmdBtn").onclick = openPalette;
  $("#palette").onclick = (e) => { if (e.target.id === "palette") closePalette(); };
  $("#paletteInput").oninput = (e) => paletteDraw(e.target.value);
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      S.palette.open ? closePalette() : openPalette();
      return;
    }
    paletteKey(e);
  });
  window.addEventListener("hashchange", route);
  document.addEventListener("click", (e) => {
    if (document.body.classList.contains("sidebar-open") && !e.target.closest("#sidebar") && !e.target.closest("#menuBtn"))
      document.body.classList.remove("sidebar-open");
  });

  loadLib().then(() => {
    applySettings();
    route();
    setInterval(async () => {
      if (!anyFetching()) return;
      try { await loadLib(); updateQueueMini(); } catch (e) { }
    }, 5000);
  }).catch((e) => {
    V().innerHTML = `<div class="empty"><div class="big">⚠️</div><h2>Sunucuya ulaşılamadı</h2><p>${esc(e.message)}</p></div>`;
  });
}
boot();
