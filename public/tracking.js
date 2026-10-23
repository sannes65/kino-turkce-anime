/* Kino: sezon keşfi, kişisel bölüm takibi ve Türkiye yayın takvimi. */
const TR_ZONE = "Europe/Istanbul";
const SEASON_LABELS = { WINTER: "Kış", SPRING: "İlkbahar", SUMMER: "Yaz", FALL: "Sonbahar" };
function trDate(ts, options = {}) {
  return new Date(ts * 1000).toLocaleDateString("tr-TR", { timeZone: TR_ZONE, day: "numeric", month: "long", ...options });
}
function trClock(ts) {
  return new Date(ts * 1000).toLocaleTimeString("tr-TR", { timeZone: TR_ZONE, hour: "2-digit", minute: "2-digit" });
}
function trDay(ts) { return new Date(ts * 1000).toLocaleDateString("sv-SE", { timeZone: TR_ZONE }); }
function airingCountdown(ts) {
  const sec = Math.max(0, ts - Date.now() / 1000);
  if (!sec) return "Yayın saati geldi";
  if (sec < 60) return "Birazdan";
  if (sec < 3600) return Math.ceil(sec / 60) + " dk kaldı";
  if (sec < 86400) return Math.floor(sec / 3600) + " sa " + Math.floor(sec % 3600 / 60) + " dk kaldı";
  return Math.floor(sec / 86400) + " gün " + Math.floor(sec % 86400 / 3600) + " sa kaldı";
}
function trackedLocal(a) {
  if (!a) return false;
  const l = listOf(a.id);
  return l.tracking ?? !["completed", "dropped", "onhold"].includes(l.status);
}
function localForMedia(m) { return S.lib.animes.find(a => String(a.meta?.anilistId) === String(m.anilistId)); }
function posterImage(m) {
  return m.poster ? `<img src="${esc(m.poster)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : `<span>${esc((m.title || "K")[0])}</span>`;
}
async function followMedia(m, btn) {
  btn.disabled = true;
  try {
    const a = localForMedia(m);
    if (a) await api("/api/list", { animeId: a.id, tracking: !trackedLocal(a) });
    else await api("/api/add", { media: m, fetchEpisodes: false });
    await loadLib();
    const on = trackedLocal(localForMedia(m));
    toast(on ? "Takibe eklendi. Bölüm çekimi başlatılmadı." : "Takipten çıkarıldı", "ok");
    return true;
  } catch (e) { toast(e.message, "err"); return false; }
  finally { btn.disabled = false; }
}
function downloadText(name, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a"); a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function calendarIcs(items) {
  const stamp = ts => new Date(ts * 1000).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
  const text = s => String(s || "").replace(/\\/g, "\\\\").replace(/\r?\n/g, "\\n").replace(/,/g, "\\,").replace(/;/g, "\\;");
  const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Kino//Anime Takvimi//TR", "CALSCALE:GREGORIAN"];
  for (const it of items) lines.push("BEGIN:VEVENT", `UID:kino-${it.media.anilistId}-${it.episode}-${it.airingAt}@local`,
    `DTSTAMP:${stamp(Math.floor(Date.now() / 1000))}`, `DTSTART:${stamp(it.airingAt)}`, `DTEND:${stamp(it.airingAt + 1800)}`,
    `SUMMARY:${text(it.media.title)} — Bölüm ${it.episode}`, "DESCRIPTION:AniList yayın saati. Türkçe altyazı veya Kino oynatma bağlantısının hazır olduğunu göstermez.", "END:VEVENT");
  lines.push("END:VCALENDAR");
  // RFC 5545: uzun satırları UTF-8 karakterini bölmeden katla.
  return lines.map(line => {
    let out = "", col = 0;
    for (const char of line) {
      const len = new TextEncoder().encode(char).length;
      if (col + len > 74) { out += "\r\n "; col = 1; }
      out += char; col += len;
    }
    return out;
  }).join("\r\n") + "\r\n";
}

async function renderCurrent(q) {
  document.title = "Kino — Güncel & Takip";
  const version = S.routeVersion;
  const current = seasonNow();
  const season = SEASON_LABELS[q.get("season")] ? q.get("season") : current.season;
  const year = /^\d{4}$/.test(q.get("year") || "") ? Number(q.get("year")) : current.year;
  const status = ["RELEASING", "NOT_YET_RELEASED", "FINISHED"].includes(q.get("status")) ? q.get("status") : "";
  const sort = ["POPULARITY_DESC", "SCORE_DESC", "TRENDING_DESC"].includes(q.get("sort")) ? q.get("sort") : "POPULARITY_DESC";
  V().innerHTML = `<div class="page current-page">
    <div class="current-heading"><div><div class="detail-kicker">KINO / YAYIN RADARI</div><h1 class="page-title">Güncel & Takip</h1><p class="page-sub">Sezonu keşfet. Yeni bölümleri yakala. Kaldığın yeri bil.</p></div><a class="btn ghost" href="#/takvim">${icon("calendar")} Yayın takvimi</a></div>
    <section aria-labelledby="trackingTitle"><div class="row-head"><h2 id="trackingTitle" class="row-title">Takip ettiklerin</h2><button class="btn ghost" id="trackingRefresh">${icon("refresh")} Yenile</button></div>
      <div id="trackingSummary" class="tracking-summary" aria-live="polite"></div><p class="page-sub" id="trackingFreshness">Yayın bilgileri kontrol ediliyor…</p>
      <div id="trackingCards" class="tracking-grid"><div class="sk-card sm"></div></div></section>
    <section class="season-section" aria-labelledby="seasonTitle"><div class="row-head"><h2 class="row-title" id="seasonTitle">${SEASON_LABELS[season]} ${year}</h2><span class="pill">AniList kataloğu</span></div>
      <div class="filter-row season-filters"><label class="select"><span>Sezon</span><select id="currentSeason">${Object.entries(SEASON_LABELS).map(([k,v]) => `<option value="${k}" ${k === season ? "selected" : ""}>${v}</option>`).join("")}</select></label>
      <label class="select"><span>Yıl</span><select id="currentYear">${Array.from(new Set([year, ...Array.from({length: 8}, (_,i) => current.year + 1 - i)])).sort((a,b) => b-a).map(y => `<option ${y === year ? "selected" : ""}>${y}</option>`).join("")}</select></label>
      <label class="select"><span>Yayın durumu</span><select id="currentStatus"><option value="">Hepsi</option>${[["RELEASING","Yayında"],["NOT_YET_RELEASED","Yakında"],["FINISHED","Tamamlandı"]].map(([v,l]) => `<option value="${v}" ${status === v ? "selected" : ""}>${l}</option>`).join("")}</select></label>
      <label class="select"><span>Sıralama</span><select id="currentSort">${[["POPULARITY_DESC","Popüler"],["SCORE_DESC","Puan"],["TRENDING_DESC","Trend"]].map(([v,l]) => `<option value="${v}" ${sort === v ? "selected" : ""}>${l}</option>`).join("")}</select></label></div>
      <p class="page-sub">Takip et, yalnızca listene kaydeder. Bölüm bağlantılarını detay sayfasından ayrıca çekebilirsin.</p>
      <div class="season-grid" id="seasonGrid"></div><div class="load-more-wrap"><button class="btn ghost" id="seasonMore" hidden>Daha fazla anime</button></div>
    </section></div>`;
  const root = $(".current-page"), fresh = () => S.routeVersion === version && document.contains(root);
  for (const id of ["currentSeason", "currentYear", "currentStatus", "currentSort"]) $("#" + id).onchange = () => {
    nav("guncel?" + new URLSearchParams({ season: $("#currentSeason").value, year: $("#currentYear").value, status: $("#currentStatus").value, sort: $("#currentSort").value }));
  };
  let trackingItems = [], busy = false;
  function drawTracking() {
    if (!fresh()) return;
    const unseen = trackingItems.reduce((n,i) => n + (i.unwatched || 0), 0);
    const today = trDay(Date.now() / 1000);
    const todayCount = trackingItems.filter(i => i.media.nextAiring && trDay(i.media.nextAiring.airingAt) === today).length;
    $("#trackingSummary", root).innerHTML = `<div><b>${trackingItems.length}</b><span>anime takipte</span></div><div><b>${unseen}</b><span>izlenmemiş yayın bölümü</span></div><div><b>${todayCount}</b><span>bugün yayınlanacak</span></div>`;
    $("#trackingCards", root).innerHTML = trackingItems.length ? trackingItems.map(it => {
      const m = it.media, next = m.nextAiring;
      const play = it.nextUnwatched && it.available.includes(it.nextUnwatched);
      return `<article class="tracking-card"><a class="tracking-cover" href="#/a/${esc(it.animeId)}">${posterImage(m)}</a><div class="tracking-body"><a href="#/a/${esc(it.animeId)}" class="tracking-title">${esc(it.title)}</a>
        <span class="pill ${it.unwatched ? "mine" : ""}">${it.aired == null ? "Yayın bilgisi bekleniyor" : it.unwatched ? `${it.unwatched} bölüm seni bekliyor` : "Güncelsin"}</span>
        <p>${it.watched} izlendi${it.aired == null ? "" : ` / ${it.aired} yayınlandı${it.estimated ? " (tahmini)" : ""}`}${!it.live ? " · çevrimdışı bilgi" : ""}</p>
        <div class="tracking-meter" role="progressbar" aria-label="İzlenen bölümler" aria-valuemin="0" aria-valuemax="${it.aired || Math.max(1,it.watched)}" aria-valuenow="${it.watched}"><i style="width:${pct(it.watched,it.aired)}%"></i></div>
        <p class="airing-note">${next ? `Bölüm ${Number(next.episode)} · ${esc(trDate(next.airingAt))} ${trClock(next.airingAt)}<br><b>${esc(airingCountdown(next.airingAt))}</b>` : m.status === "FINISHED" ? "Seri tamamlandı" : "Yeni yayın tarihi henüz açıklanmadı"}</p>
        <div class="tracking-actions">${it.nextUnwatched ? `<button class="btn accent sm" data-mark="${esc(it.animeId)}" data-ep="${it.nextUnwatched}">${icon("check")} ${it.nextUnwatched}. bölümü izledim</button>` : ""}
          ${play ? `<a class="btn ghost sm" href="#/p/${esc(it.animeId)}/${it.nextUnwatched}">${icon("play")} İzle</a>` : `<a class="btn ghost sm" href="#/a/${esc(it.animeId)}">Detaylar</a>`}
          <button class="icon-btn sm" data-unfollow="${esc(it.animeId)}" aria-label="${esc(it.title)} takibini bırak" title="Takipten çıkar">${icon("x")}</button></div>
        ${it.lastWatched ? `<button class="tracking-undo" data-undo="${esc(it.animeId)}" data-ep="${it.lastWatched}">${it.lastWatched}. bölüm işaretini geri al</button>` : ""}
      </div></article>`;
    }).join("") : `<div class="tracking-empty"><h3>Takip listen burada büyüyecek.</h3><p>Aşağıdaki sezon animelerinden birini takip et veya Keşfet'ten ekle.</p><a class="btn ghost" href="#/kesfet">${icon("compass")} Keşfet</a></div>`;
    $$("[data-mark], [data-undo], [data-unfollow]", root).forEach(btn => btn.onclick = async () => {
      btn.disabled = true;
      try {
        if (btn.dataset.unfollow) await api("/api/list", { animeId: btn.dataset.unfollow, tracking: false });
        else await api("/api/tracking/progress", { animeId: btn.dataset.mark || btn.dataset.undo, episode: Number(btn.dataset.ep), done: !!btn.dataset.mark });
        await loadLib(); if (fresh()) { await refreshTracking(); drawSeason(); }
      } catch (e) { toast(e.message, "err"); } finally { btn.disabled = false; }
    });
  }
  async function refreshTracking() {
    if (busy || !fresh()) return;
    busy = true; $("#trackingRefresh", root).disabled = true;
    try {
      const r = await api("/api/tracking");
      if (!fresh()) return;
      trackingItems = r.items;
      $("#trackingFreshness", root).textContent = r.warning || `Kontrol: ${trClock(r.checkedAt)} · AniList verileri 5 dakika önbellekte tutulur · Saatler Türkiye saati.`;
      $("#trackingFreshness", root).classList.toggle("tracking-warning", !!r.warning);
      drawTracking();
    } catch (e) {
      if (fresh()) {
        $("#trackingFreshness", root).textContent = "Takip bilgisi alınamadı: " + e.message;
        if (!trackingItems.length) $("#trackingCards", root).innerHTML = '<div class="tracking-empty">Takip bilgisi yüklenemedi. Yenile düğmesiyle tekrar deneyebilirsin.</div>';
      }
    } finally { busy = false; if (fresh()) $("#trackingRefresh", root).disabled = false; }
  }
  $("#trackingRefresh", root).onclick = refreshTracking;
  let page = 0, media = [], loading = false;
  function drawSeason() {
    if (!fresh()) return;
    $("#seasonGrid", root).innerHTML = media.length ? media.map(m => {
      const a = localForMedia(m), on = a && trackedLocal(a), next = m.nextAiring;
      return `<article class="season-card"><a class="season-cover" href="${a ? "#/a/" + esc(a.id) : "#/d/" + m.anilistId}">${posterImage(m)}${m.score ? `<span class="season-score">★ ${(m.score / 10).toFixed(1)}</span>` : ""}</a>
        <a class="tracking-title" href="${a ? "#/a/" + esc(a.id) : "#/d/" + m.anilistId}">${esc(m.title)}</a><small>${esc(m.format || "Anime")} · ${m.status === "RELEASING" ? "Yayında" : m.status === "NOT_YET_RELEASED" ? "Yakında" : m.status === "FINISHED" ? "Tamamlandı" : esc(m.status || "Tarih bekleniyor")}</small>
        <p>${next ? `${Number(next.episode)}. bölüm · ${esc(trDate(next.airingAt))} ${trClock(next.airingAt)}` : "Yeni bölüm tarihi açıklanmadı"}</p>
        <button class="btn ${on ? "ghost" : "accent"} sm" data-follow="${m.anilistId}">${icon(on ? "check" : "plus")}${on ? "Takip ediliyor" : "Takip et"}</button></article>`;
    }).join("") : `<div class="tracking-empty"><h3>Bu filtrede anime bulunamadı.</h3><p>Sezonu veya yayın durumunu değiştirebilirsin.</p></div>`;
    $$("[data-follow]", root).forEach(btn => btn.onclick = async () => {
      const m = media.find(x => String(x.anilistId) === btn.dataset.follow);
      if (await followMedia(m, btn)) { if (fresh()) { drawSeason(); await refreshTracking(); } }
    });
  }
  async function loadSeason() {
    if (loading || !fresh()) return;
    loading = true;
    const btn = $("#seasonMore", root); btn.disabled = true;
    if (!page) $("#seasonGrid", root).innerHTML = Array.from({length:6}, () => '<div class="sk-card tall"></div>').join("");
    try {
      const r = await api("/api/browse?" + new URLSearchParams({ season, year, status, sort, per: 24, page: page + 1 }));
      if (!fresh()) return;
      page++; media.push(...r.results); drawSeason(); btn.hidden = !r.pageInfo.hasNextPage;
      btn.textContent = "Daha fazla anime";
    } catch (e) {
      if (fresh()) {
        if (!page) $("#seasonGrid", root).innerHTML = `<p class="tracking-warning">Sezon bilgisi alınamadı: ${esc(e.message)}</p>`;
        btn.hidden = false; btn.textContent = "Tekrar dene";
      }
    } finally { loading = false; btn.disabled = false; }
  }
  $("#seasonMore", root).onclick = loadSeason;
  await Promise.all([refreshTracking(), loadSeason()]);
  if (fresh()) {
    poll(() => { if (!document.hidden) drawTracking(); }, 60000);
    poll(async () => {
      if (!document.hidden && fresh()) {
        try { await loadLib(); if (fresh()) { await refreshTracking(); drawSeason(); } }
        catch (e) { if (fresh()) $("#trackingFreshness", root).textContent = "Otomatik yenileme başarısız. Yenile düğmesiyle tekrar deneyebilirsin."; }
      }
    }, 300000);
  }
}

async function renderSchedule(q) {
  document.title = "Kino — Yayın takvimi";
  const version = S.routeVersion;
  const offset = Math.max(0, Math.min(7, Math.floor((Number(q.get("offset")) || 0) / 7))) * 7;
  let mine = q.get("mine") === "1", selectedDay = "", items = [];
  V().innerHTML = `<div class="page schedule-page"><div class="current-heading"><div><div class="detail-kicker">KINO / HAFTALIK AKIŞ</div><h1 class="page-title">Yayın takvimi</h1><p class="page-sub">Türkiye saati (UTC+3). Yayın saati, altyazı veya oynatma bağlantısının hazır olduğunu göstermez.</p></div><a class="btn ghost" href="#/guncel">${icon("bookmark")} Takip listem</a></div>
    <div class="calendar-toolbar"><div class="tracking-actions"><button class="btn ghost" id="weekPrev" ${offset === 0 ? "disabled" : ""}>${icon("left")} Önceki</button><button class="btn ghost" id="weekToday">Bu hafta</button><button class="btn ghost" id="weekNext" ${offset >= 49 ? "disabled" : ""}>Sonraki ${icon("right")}</button></div><label class="calendar-toggle"><input type="checkbox" id="calendarMine" ${mine ? "checked" : ""}> Sadece takip ettiklerim</label><button class="btn ghost" id="calendarExport" disabled>${icon("download")} Takvime aktar (.ics)</button></div>
    <p id="calendarCount" class="page-sub" aria-live="polite">Yayınlar yükleniyor…</p><div id="calendarDays" class="calendar-days"></div><div id="calendarItems" class="sched"></div></div>`;
  const root = $(".schedule-page"), fresh = () => version === S.routeVersion && document.contains(root);
  const go = off => nav("takvim?" + new URLSearchParams({ offset: off, mine: mine ? "1" : "0" }));
  $("#weekPrev", root).onclick = () => go(offset - 7);
  $("#weekNext", root).onclick = () => go(offset + 7);
  $("#weekToday", root).onclick = () => go(0);
  const filtered = () => items.filter(it => !mine || (localForMedia(it.media) && trackedLocal(localForMedia(it.media))));
  function draw() {
    if (!fresh()) return;
    const all = filtered();
    const shown = all.filter(it => !selectedDay || trDay(it.airingAt) === selectedDay);
    $("#calendarCount", root).textContent = `${all.length} yayın · ${trDate(Date.now()/1000 + offset*86400)} – ${trDate(Date.now()/1000 + (offset+6)*86400)}${selectedDay ? ` · seçili günde ${shown.length} yayın` : ""}`;
    $("#calendarExport", root).disabled = !shown.length;
    const days = Array.from({length:7}, (_,i) => Date.now()/1000 + (offset+i)*86400);
    $("#calendarDays", root).innerHTML = `<button class="chip ${!selectedDay ? "active" : ""}" data-day="">Tüm hafta <small>${all.length}</small></button>` + days.map(ts => {
      const day = trDay(ts), count = all.filter(it => trDay(it.airingAt) === day).length;
      return `<button class="chip ${selectedDay === day ? "active" : ""}" data-day="${day}">${trDate(ts, {weekday:"short",month:"short"})} <small>${count}</small></button>`;
    }).join("");
    $$("[data-day]", root).forEach(btn => btn.onclick = () => { selectedDay = btn.dataset.day; draw(); });
    const groups = {};
    shown.forEach(it => (groups[trDay(it.airingAt)] ||= []).push(it));
    $("#calendarItems", root).innerHTML = shown.length ? Object.entries(groups).map(([day, entries]) => `<section class="sched-day"><h2 class="sched-date">${trDate(entries[0].airingAt, {weekday:"long"})}${day === trDay(Date.now()/1000) ? ' <span class="today">bugün</span>' : ""}</h2><div class="sched-list">${entries.map(it => {
      const a = localForMedia(it.media), on = a && trackedLocal(a), past = it.airingAt <= Date.now()/1000;
      return `<a class="sched-item ${on ? "mine" : ""}" href="${a ? "#/a/" + esc(a.id) : "#/d/" + it.media.anilistId}"><span class="sched-time">${trClock(it.airingAt)}</span><div class="sched-poster">${posterImage(it.media)}</div><div class="sched-txt"><b>${esc(it.media.title)}</b><small>Bölüm ${Number(it.episode)} · ${past ? "Yayın saati geçti" : esc(airingCountdown(it.airingAt))}</small></div>${on ? '<span class="pill mine">Takipte</span>' : ""}</a>`;
    }).join("")}</div></section>`).join("") : `<div class="tracking-empty"><h3>${mine ? "Takip listende bu aralıkta yayın yok." : "Bu aralıkta yayın bulunamadı."}</h3><p>${mine ? "Tüm animeleri gösterebilir veya Güncel & Takip'ten yeni anime ekleyebilirsin." : "Başka bir gün veya hafta seçebilirsin."}</p></div>`;
  }
  $("#calendarMine", root).onchange = e => {
    mine = e.target.checked;
    history.replaceState(null, "", "#/takvim?" + new URLSearchParams({offset, mine: mine ? "1" : "0"})); draw();
  };
  $("#calendarExport", root).onclick = () => downloadText("kino-yayin-takvimi.ics", calendarIcs(filtered().filter(it => !selectedDay || trDay(it.airingAt) === selectedDay)), "text/calendar;charset=utf-8");
  async function load() {
    try {
      const r = await api(`/api/schedule?days=7&offset=${offset}`);
      if (!fresh()) return;
      items = r.items; draw();
    } catch (e) {
      if (fresh()) {
        $("#calendarCount", root).textContent = "Yayın bilgisi yüklenemedi.";
        $("#calendarItems", root).innerHTML = `<div class="tracking-empty"><h3>AniList'e ulaşılamadı</h3><p>${esc(e.message)}</p><button class="btn ghost" id="calendarRetry">Tekrar dene</button></div>`;
        $("#calendarRetry", root).onclick = load;
      }
    }
  }
  await load();
  if (fresh()) poll(() => { if (!document.hidden) draw(); }, 60000);
}
