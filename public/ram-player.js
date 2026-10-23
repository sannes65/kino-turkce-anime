/* Volatile server RAM playback; ordinary streaming stays available. */
class KinoRamPlayer {
  constructor(animeId, ep, enabled) {
    this.animeId = animeId; this.ep = ep; this.enabled = enabled;
    this.dead = false; this.seq = 0; this.entry = null; this.next = null;
    this.nextStarting = false; this.nextStarted = false; this.timers = new Set();
    this.bar = $("#pRamStatus"); this.overlay = $("#pRamPrepare");
  }
  mb(bytes) { return (Number(bytes || 0) / 1048576).toFixed(1) + " MB"; }
  stopWait(value = null) {
    this.seq++;
    this.timers.forEach(clearInterval); this.timers.clear();
    if (this.resolve) { this.resolve(value); this.resolve = null; }
    this.overlay.hidden = true;
  }
  stop() {
    this.dead = true; this.stopWait();
    if (this.entry && ["resolving", "downloading"].includes(this.entry.state)) api("/api/ram/cancel", {id:this.entry.id}).catch(() => {});
  }
  async useStream() {
    this.enabled = false;
    for (const entry of [this.entry, this.next]) if (entry) api("/api/ram/cancel", {id:entry.id}).catch(() => {});
    this.stopWait();
    this.drawBar();
  }
  drawBar(status) {
    if (this.dead || !document.contains(this.bar)) return;
    const e = this.entry;
    if (!this.enabled) {
      this.bar.innerHTML = `${icon("play")} <span>Akış modu · RAM hazırlama bu oynatım için kapalı</span>`;
      return;
    }
    let next = this.nextMessage || "Son 7 dakikada sıradaki bölüm hazırlanacak.";
    if (e?.state === "expired") next = "RAM kaydı artık mevcut değil. Tekrar hazırla veya RAM düğmesinden akış moduna geç.";
    if (this.next) {
      if (this.next.state === "ready") next = "Sıradaki bölüm RAM’de hazır.";
      else if (this.next.state === "error") next = "Sıradaki bölüm hazırlanamadı. <button id='ramNextRetry'>Tekrar dene</button>";
      else next = `Sıradaki bölüm hazırlanıyor: %${this.next.percent} · ${this.next.done}/${this.next.total || "?"} parça`;
    }
    this.bar.innerHTML = `${icon("layers")} <div><b>${e?.state === "ready" ? "RAM’den oynatılıyor" : "RAM modu"}${e?.height ? " · " + e.height + "p" : ""}${e?.bytes ? " · " + this.mb(e.bytes) : ""}</b><small>${next}</small></div>${status ? `<span class="ram-memory">Önbellek: ${this.mb(status.usedBytes)} / ${this.mb(status.limitBytes)}</span>` : ""}`;
    const retry = $("#ramNextRetry", this.bar);
    if (retry) retry.onclick = () => { this.nextStarted = false; this.tick($("#video")); };
  }
  drawPrepare(entry, status) {
    if (this.dead) return;
    const error = entry.state === "error";
    const over = entry.elapsed >= 30;
    this.overlay.hidden = false;
    this.overlay.innerHTML = `<div class="ram-prepare-card"><div class="ram-kicker">KINO / RAM MODU</div><h2>${error ? "Bölüm hazırlanamadı" : "Bölüm RAM’e hazırlanıyor"}</h2>
      <p>${error ? esc(entry.error) : entry.state === "resolving" ? "Video bağlantısı ve kalite kontrol ediliyor…" : `%${entry.percent} · ${entry.done}/${entry.total} parça · ${this.mb(entry.bytes)}`}</p>
      <div class="ram-progress" role="progressbar" aria-label="RAM hazırlama" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${entry.percent || 0}"><i style="width:${entry.percent || 0}%"></i></div>
      <small>${error ? "Kütüphanen ve izleme ilerlemen korunuyor." : over ? "30 saniye geçti; indirme sürüyor. Tamamını bekleyebilir veya akışla başlayabilirsin." : "Hedef yaklaşık 30 saniye. Hazır olur olmaz başlayacak; süre bağlantıya göre değişir."}</small>
      ${entry.eta && !error ? `<small>Tahmini kalan: ${entry.eta < 60 ? entry.eta + " sn" : Math.ceil(entry.eta / 60) + " dk"}</small>` : ""}
      <div class="ram-prepare-actions">${error ? '<button class="btn accent" id="ramRetry">Tekrar hazırla</button>' : ""}<button class="btn ghost" id="ramStream">${icon("play")} Akışla izle</button></div>
      <small>Yalnızca bellekte tutulur · Önbellek sınırı ${status ? this.mb(status.limitBytes) : "1024 MB"}</small></div>`;
    $("#ramStream", this.overlay).onclick = () => this.useStream();
    const retry = $("#ramRetry", this.overlay);
    if (retry) retry.onclick = () => { retry.disabled = true; this.request(true).catch(e => { if (!this.dead) this.drawPrepare({...entry,error:e.message}, status); }); };
  }
  async request(retry = false) {
    const seq = this.seq;
    const r = await api("/api/ram/prepare", {animeId:this.animeId,ep:this.ep,retry});
    if (this.dead || seq !== this.seq) return;
    this.entry = r.entry;
  }
  async prepare() {
    this.stopWait();
    this.next = null; this.nextStarted = false; this.nextMessage = null;
    if (!this.enabled || this.dead) { this.drawBar(); return null; }
    const seq = this.seq;
    this.entry = {state:"resolving",elapsed:0,percent:0};
    this.drawPrepare(this.entry);
    return new Promise(resolve => {
      this.resolve = resolve;
      let busy = false, failures = 0;
      const check = async () => {
        if (busy || this.dead || seq !== this.seq || !this.entry?.id) return;
        busy = true;
        try {
          const status = await api("/api/ram/status?id=" + this.entry.id);
          if (this.dead || seq !== this.seq) return;
          failures = 0;
          this.entry = status.entry || {...this.entry,state:"error",error:"RAM kaydı silinmiş. Bölümü yeniden hazırlayabilirsin."};
          if (this.entry.state === "ready") {
            const src = this.entry.playlist;
            this.stopWait(src); this.drawBar(status); this.monitor();
          } else this.drawPrepare(this.entry, status);
        } catch (e) {
          if (++failures >= 3 && !this.dead && seq === this.seq) this.drawPrepare({...this.entry,state:"error",error:"Sunucuya ulaşılamadı. Tekrar deneyebilirsin."});
        } finally { busy = false; }
      };
      // Set up the wait before the request, so leaving the route always settles it.
      const timer = setInterval(check, 750); this.timers.add(timer);
      this.request().then(check).catch(e => {
        if (!this.dead && seq === this.seq) {
          this.entry = {...this.entry,state:"error",error:e.message}; this.drawPrepare(this.entry);
        }
      });
    });
  }
  monitor() {
    let busy = false;
    const timer = setInterval(async () => {
      if (busy || this.dead || !this.enabled || !this.entry?.id) return;
      busy = true;
      try {
        const status = await api("/api/ram/status?id=" + this.entry.id);
        if (this.dead) return;
        if (!status.entry) this.entry = {...this.entry,state:"expired"};
        const next = status.entries.find(e => e.role === "next");
        if (this.next && !next) { this.nextStarted = false; this.next = null; }
        else if (next) this.next = next;
        this.drawBar(status);
      } catch (e) { /* Playback from a completed cache does not need status polling to succeed. */ }
      finally { busy = false; }
    }, 2500);
    this.timers.add(timer);
  }
  async tick(video) {
    if (this.dead || !this.enabled || this.entry?.state !== "ready" || this.nextStarted || this.nextStarting || !video || !Number.isFinite(video.duration) || video.duration <= 0 || video.duration - video.currentTime > 420 || video.ended) return;
    this.nextStarting = true; this.nextStarted = true;
    try {
      const r = await api("/api/ram/prepare", {animeId:this.animeId,ep:this.ep,prefetch:true,retry:true});
      if (!this.dead) { this.next = r.entry; this.drawBar(); }
    } catch (e) {
      if (!this.dead) {
        // A missing next episode is normal on the final episode.
        this.nextMessage = "Sıradaki bölüm hazırlanamadı: " + esc(e.message);
        this.drawBar();
      }
    } finally { this.nextStarting = false; }
  }
}

function renderRamSettings() {
  const root = $(".settings");
  if (!root) return;
  const st = S.lib.settings || {};
  root.insertAdjacentHTML("afterbegin", `<section class="set-card"><h3>RAM’den oynatma</h3><div class="set-row"><div><b>Bölümü önce RAM’e hazırla</b><small>İsteğe bağlıdır, varsayılan kapalıdır. Açıkken bölüm RAM’e hazırlanır; son 7 dakikada sıradaki bölüm indirilir.</small></div><label class="switch"><input id="sRam" type="checkbox" ${st.ramPlayback === true ? "checked" : ""} aria-label="RAM’den oynatma"><i></i></label></div><div class="set-row"><div><b>Hazırlama kalitesi</b><small>RAM modu açıkken kullanılır. Sonraki oynatımda geçerli.</small></div><select id="sRamQuality" aria-label="RAM hazırlama kalitesi" ${st.ramPlayback === true ? "" : "disabled"}>${[360,480,720,1080].map(n => `<option value="${n}" ${(st.ramQuality || 720) === n ? "selected" : ""}>${n}p</option>`).join("")}</select></div><p class="page-sub">Kapalıyken bölümler normal akışla açılır. Açıkken önbellek sınırı varsayılan 1 GB'dır. Videolar diske kaydedilmez.</p></section>`);
  const save = async patch => {
    try { const r = await api("/api/settings",patch); S.lib.settings = r.settings; toast("RAM ayarı kaydedildi", "ok"); }
    catch (e) { toast(e.message,"err"); }
  };
  $("#sRam").onchange = async e => {
    const toggle = e.target;
    toggle.disabled = true;
    await save({ramPlayback:toggle.checked});
    toggle.checked = S.lib.settings.ramPlayback === true;
    $("#sRamQuality").disabled = !toggle.checked;
    toggle.disabled = false;
  };
  $("#sRamQuality").onchange = e => save({ramQuality:Number(e.target.value)});
}
