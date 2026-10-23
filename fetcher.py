"""tranimeizle.live bolum cekici: anime adindan calisan m3u8 linklerini bulur.

Kino (server.py) bunu alt surec olarak calistirir; elle de calisir:
    ANIME="horimiya" N=10 python fetcher.py
Ciktidaki `EPn: OK -> ... | url` satirlari ve son `KINO_RESULT:{...}` satiri
makine tarafindan okunur. Tarayici gerekirse otomatik acilir (browser.py).
"""
import os, sys, json, re, time, urllib.parse
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser import ensure_browser
from cdp import (cdp, js, goto_url, wait, wait_for_load, list_tabs, current_tab,
                 new_tab, switch_tab, activate_tab, click_at_xy)

BASE = "https://www.tranimeizle.live"
ROOT = Path(__file__).resolve().parent
STATE = Path(os.environ.get("KINO_STATE") or ROOT / "state")
COOKIE_FILE = str(os.environ.get("TRANIMEIZLE_COOKIES") or STATE / "tranimeizle-cookies.json")
# eski kurulumdaki cookie yeri; ilk calismada tasinir
OLD_COOKIE_FILE = os.path.expanduser("~/Desktop/animeskill/.tranimeizle.cookies.json")
VAR = str(STATE / "fetch")
PROG_FILE = os.path.join(VAR, "progress.json")


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_json(path, obj, **kw):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, **kw)
    os.replace(tmp, path)


ANIME = os.environ.get("ANIME", "").strip()
N = int(os.environ.get("N", "10"))
RESET = os.environ.get("RESET", "") == "1"
START = os.environ.get("START", "").strip()   # 0 tabanli baslangic indeksi (opsiyonel)
PAGE = os.environ.get("PAGE", "").strip()     # sabit anime sayfasi (opsiyonel)

# Kaynak oncelik sirasi: once AitrVip, yoksa/olmazsa Sibnet, sonra digerleri
PRIORITY = ["AitrVip", "Sibnet"]
AD_DOMAINS = ("youtube.com", "googletagmanager", "doubleclick", "googleads",
              "wargamings", "cloudflareinsights", "one-google-bar", "newtab")


def log(*a):
    print(*a, flush=True)


def emit(obj):
    """Makine okur tek satir sonuc (kino gibi cagiranlar icin)."""
    log("KINO_RESULT:" + json.dumps(obj, ensure_ascii=False))


def load_cookie():
    path = COOKIE_FILE if os.path.exists(COOKIE_FILE) else OLD_COOKIE_FILE
    if os.path.exists(path):
        try:
            val = _read_json(path).get(".AitrWeb.Session")
        except Exception:
            val = None
        if val:
            cdp("Network.setCookie", name=".AitrWeb.Session", value=val,
                domain=".tranimeizle.live", path="/", secure=True,
                httpOnly=True, sameSite="Lax")


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def ensure_tab():
    tab = None
    for t in list_tabs():
        if "tranimeizle" in t.get("url", ""):
            tab = t["targetId"]
            break
    if tab:
        switch_tab(tab)
    else:
        new_tab(BASE)
        tab = current_tab()["targetId"]
    activate_tab(tab)   # arka planda video yuklenmez
    return tab


def check_captcha():
    try:
        if js("!!document.querySelector('.captcha-modal__icons')"):
            return True
        if "Bot Kontrol" in (js("document.title") or ""):
            return True
    except Exception:
        pass
    return False


# "Farkli olani sec" captcha'si: 5 ikonun 4'u piksel piksel ayni, biri farkli.
# Ikonlari canvas'a cizip her birinin digerlerine toplam uzakligini hesaplar;
# en uzak olan farkli ikondur (AI/vision gerekmez).
CAPTCHA_SOLVER = r"""(function(){
  var cells=Array.from(document.querySelectorAll('.captcha-modal__icons .captcha-image'));
  return Promise.all(cells.map(function(c){
    var m=/url\(["']?(.*?)["']?\)/.exec(getComputedStyle(c).backgroundImage||'');
    return new Promise(function(ok,bad){var im=new Image();im.onload=function(){ok(im)};im.onerror=bad;im.src=m[1];});
  })).then(function(ims){
    var W=24,H=20,cv=document.createElement('canvas');cv.width=W;cv.height=H;
    var ctx=cv.getContext('2d',{willReadFrequently:true});
    var vecs=ims.map(function(im){
      ctx.fillStyle='#fff';ctx.fillRect(0,0,W,H);ctx.drawImage(im,0,0,W,H);
      var d=ctx.getImageData(0,0,W,H).data,v=[];
      for(var i=0;i<d.length;i+=4){var a=d[i+3]/255;v.push(255-((d[i]+d[i+1]+d[i+2])/3*a+255*(1-a)));}
      return v;});
    var n=vecs.length,sc=[];
    for(var i=0;i<n;i++){var s=0;for(var j=0;j<n;j++){if(i==j)continue;var t=0;
      for(var k=0;k<vecs[i].length;k++)t+=Math.abs(vecs[i][k]-vecs[j][k]);s+=t;}sc.push(s);}
    var best=sc.indexOf(Math.max.apply(null,sc));
    var srt=sc.slice().sort(function(a,b){return b-a});
    var b=cells[best].getBoundingClientRect();
    return JSON.stringify({pick:best,margin:srt[1]?srt[0]/srt[1]:0,
      x:b.x+b.width/2,y:b.y+b.height/2});
  }).catch(function(e){return JSON.stringify({error:String(e)});});
})()"""


def save_cookie():
    cookies = cdp("Network.getCookies", urls=[BASE + "/"])["cookies"]
    sess = next((c["value"] for c in cookies if c["name"] == ".AitrWeb.Session"), None)
    if not sess:
        return False
    os.makedirs(os.path.dirname(COOKIE_FILE), exist_ok=True)
    _write_json(COOKIE_FILE, {".AitrWeb.Session": sess})
    return True


def pass_captcha(tries=4):
    """Captcha varsa coz, gecince oturum cookie'sini kaydet. Gecildiyse True."""
    for attempt in range(tries):
        if not check_captcha():
            return True
        r = {}
        for _ in range(10):   # ikon arka planlari gec yuklenebilir
            wait(1)
            try:
                r = json.loads(js(CAPTCHA_SOLVER) or "{}")
            except Exception as e:
                r = {"error": str(e)}
            if not r.get("error"):
                break
        if r.get("error") or r.get("margin", 0) < 1.5:
            log("CAPTCHA: cozulemedi (%s), yeniden yukleniyor %d/%d"
                % (r.get("error") or "belirsiz, margin=%.2f" % r.get("margin", 0), attempt + 1, tries))
            try:
                js("location.reload()")
            except Exception:
                pass
            wait(3)
            continue
        # Ilk tiklama bazen sayfaya ulasmiyor; ayni (dogru) ikona fare
        # hareketiyle birlikte birkac kez tikla, yonlendirmeyi bekle.
        for _click in range(3):
            wait(1.5)
            for ct in ("mouseMoved", "mousePressed", "mouseReleased"):
                cdp("Input.dispatchMouseEvent", type=ct, x=r["x"], y=r["y"],
                    button="left", clickCount=1)
            for _ in range(6):
                wait(1)
                if not check_captcha():
                    break
            if not check_captcha():
                break
        try:
            wait_for_load()
        except Exception:
            pass
        if not check_captcha():
            log("CAPTCHA: otomatik gecildi (ikon %d)" % (r["pick"] + 1))
            if save_cookie():
                log("CAPTCHA: oturum cookie'si kaydedildi")
            wait(1)
            return True
        log("CAPTCHA: secim kabul edilmedi, tekrar %d/%d" % (attempt + 1, tries))
    return not check_captcha()


def clear_ads():
    try:
        js("(function(){document.querySelectorAll('ins,[id^=up-a-]').forEach(e=>e.remove());return 1;})()")
    except Exception:
        pass


def search(query):
    """Arama sayfasi bazen bot/interstitial ("Baglanti kontrol ediliyor") dondurur;
    o yuzden bos sonucta birkac kez yeniden dene."""
    res = []
    for attempt in range(3):
        goto_url(BASE + "/arama/" + urllib.parse.quote(query))
        wait_for_load()
        wait(2.0 + attempt * 1.5)
        if check_captcha() and not pass_captcha():
            raise RuntimeError("CAPTCHA: otomatik cozulemedi")
        res = json.loads(js("""JSON.stringify(Array.from(new Set(Array.from(document.querySelectorAll('a[href^="/anime/"]')).map(a=>a.getAttribute('href')))))"""))
        if res:
            return res
        try:
            host = js("location.hostname")
        except Exception:
            host = ""
        log("Arama sonucu bos (%s), tekrar deneniyor %d/3" % (host or "?", attempt + 1))
        wait(2.5)
    return res


def pick_anime(cands, query):
    q = norm(query)
    syn = {"season": "sezon", "movie": "film", "special": "ozel",
           "dub": "dublaj", "watch": "izle", "the": ""}
    qt = {syn.get(t, t) for t in re.findall(r"[a-z0-9]+", (query or "").lower())}
    qt.discard("")
    bad_words = ("sezon", "season", "movie", "film", "ova", "ona",
                 "special", "dub", "dublaj", "recap")
    scored = []
    for h in cands:
        slug = h.strip("/").split("/")[-1]
        s = norm(slug)
        base = re.sub(r"(izle|watch)+$", "", s)
        st = {syn.get(t, t) for t in re.findall(r"[a-z0-9]+", slug.replace("-", " "))}
        st.discard("")
        score = 0.0
        if s == q or base == q:
            score += 200
        if s == q + "izle" or base == q + "izle":
            score += 150
        if q and q in s:
            score += 60
        if qt:
            score += 40.0 * len(qt & st) / len(qt)
            score -= 12 * len([t for t in qt if t.isdigit() and t not in st])
        for bad in bad_words:
            if bad in st and bad not in qt:
                score -= 45
        extra_nums = [t for t in st - qt if t.isdigit()]
        score -= 12 * len(extra_nums)
        score -= abs(len(s) - len(q)) * 0.15
        scored.append((score, h, slug))
    scored.sort(reverse=True)
    return scored


def get_episodes():
    return json.loads(js("""JSON.stringify(Array.from(document.querySelectorAll('.animeDetail-items a')).map(a=>[a.innerText.replace(/\\s+/g,' ').trim(), a.getAttribute('href')]))"""))


def get_sources():
    return json.loads(js("""JSON.stringify(Array.from(document.querySelectorAll('.sourceBtn')).map(e=>[e.innerText.split('\\n')[0].trim(), e.getAttribute('data-id'), e.getAttribute('data-eid')]))"""))


def order_sources(srcs):
    idx = {}
    for i, (name, _sid, _eid) in enumerate(srcs):
        idx.setdefault(name, []).append(i)
    order = []
    for name in PRIORITY:
        order.extend(idx.get(name, []))
    for i in range(len(srcs)):
        if i not in order:
            order.append(i)
    return order


def get_fansubs():
    try:
        return json.loads(js("""JSON.stringify(Array.from(document.querySelectorAll('.fansubSelector')).map(e=>e.innerText.replace(/\\s+/g,' ').trim()))"""))
    except Exception:
        return []


def active_fansub():
    try:
        flags = json.loads(js("""JSON.stringify(Array.from(document.querySelectorAll('.fansubSelector')).map(e=>e.classList.contains('active')))"""))
        return flags.index(True) if True in flags else 0
    except Exception:
        return 0


def select_fansub(i):
    """Fansub degistir; kaynak listesi gercekten degisene kadar bekle."""
    try:
        before = js("(document.getElementById('sourceList')||{}).innerText||''")
    except Exception:
        before = ""
    try:
        js("document.querySelectorAll('.fansubSelector')[%d].click()" % i)
    except Exception:
        return False
    for _ in range(10):
        wait(1)
        try:
            now = js("(document.getElementById('sourceList')||{}).innerText||''")
        except Exception:
            now = ""
        if now and now != before:
            return True
    return False


def try_all_sources(limit=20):
    """Aktif fansub'un kaynaklarini sirayla dene. Ilk calisani dondur."""
    srcs = get_sources()
    if not srcs:
        return None
    try:
        eid = srcs[0][2]
        js(f"localStorage.setItem('preVideo_{eid}', new Date().toISOString())")
    except Exception:
        pass
    for n, si in enumerate(order_sources(srcs)):
        if n >= limit:
            break
        name = srcs[si][0]
        ok, embed, stream, detail = test_source(si, "")
        if ok:
            return {"source": name, "embed": embed, "m3u8": stream}
    return None


def clean_targets():
    out = []
    for t in cdp("Target.getTargets")["targetInfos"]:
        if t["type"] == "iframe" and not any(d in t.get("url", "") for d in AD_DOMAINS):
            out.append(t)
    return out


def vid_info(tid):
    try:
        return json.loads(js("(function(){var v=document.querySelector('video');if(!v)return 'null';return JSON.stringify([Math.round(v.duration||0),v.readyState,v.paused]);})()", target_id=tid))
    except Exception:
        return None


def extract_stream(tid):
    """Oynatici iframe'inden m3u8 (veya mp4) stream URL'sini cikar."""
    # 1) JW Player API
    try:
        r = js("""(function(){try{
            if(typeof jwplayer!=='function')return null;
            var it=jwplayer().getPlaylistItem()||{};
            var f=it.file||(it.sources&&it.sources[0]&&it.sources[0].file)||'';
            if(!f)return null;
            return JSON.stringify({u:(f.indexOf('http')===0?f:location.origin+f),dur:jwplayer().getDuration()||0});
        }catch(e){return null;}})()""", target_id=tid)
        if r:
            d = json.loads(r)
            if d.get("u"):
                return d["u"], float(d.get("dur") or 0)
    except Exception:
        pass
    # 2) performance entries (m3u8 oncelikli, sonra mp4)
    try:
        r = js("""(function(){
            var rs=performance.getEntriesByType('resource').map(e=>e.name);
            function last(re){var m=rs.filter(n=>re.test(n));return m.length?m[m.length-1]:'';}
            return last(/\\.m3u8($|\\?)/i)||last(/\\.mp4($|\\?)/i)||'';
        })()""", target_id=tid)
        if r:
            return r, None
    except Exception:
        pass
    return "", None


def doc_fail(tid):
    try:
        t = js("(document.body&&document.body.innerText||'').slice(0,120)", target_id=tid) or ""
        return any(k in t for k in ("Not Found", "403 Forbidden", "Request forbidden", "404", "Video not found", "bulunamad"))
    except Exception:
        return False


def probe(url, tid):
    """Stream linki gercekten sunuluyor mu? (ayni origin baglaminda fetch)"""
    try:
        if ".m3u8" in url:
            return js("""(function(){return fetch(%r,{credentials:'include'}).then(function(r){return r.text().then(function(t){return r.status+'|'+t.slice(0,16);});});})()""" % url, target_id=tid)
        return js("""(function(){return fetch(%r,{credentials:'include',headers:{'Range':'bytes=0-0'}}).then(function(r){return String(r.status);});})()""" % url, target_id=tid)
    except Exception:
        return "ERR"


def test_source(idx, embed_host):
    js(f"document.querySelectorAll('.sourceBtn')[{idx}].click()")
    embed = ""
    tid = None
    stream, dur = "", None
    for _ in range(9):
        wait(1)
        embed = js("(function(){var f=document.querySelector('#videoPlayer iframe');return f?f.src:'';})()") or ""
        if embed:
            cands = [t for t in clean_targets() if embed_host and embed_host in t.get("url", "")]
            if not cands:
                cands = clean_targets()
            for t in cands:
                s, d = extract_stream(t["targetId"])
                if s:
                    tid, stream, dur = t["targetId"], s, d
                    break
            if stream:
                break
            if cands and doc_fail(cands[0]["targetId"]):
                break
    if not embed:
        return False, "", "", "iframe yuklenmedi"
    if not stream:
        host = embed.split("/")[2] if embed.count("/") >= 2 else "?"
        return False, embed, "", f"stream yok ({host})"
    pr = probe(stream, tid) if tid else "ERR"
    if ".m3u8" in stream:
        ok = pr.startswith("200|") and "#EXTM3U" in pr
    else:
        ok = pr in ("200", "206")
    if not ok:
        di = vid_info(tid) if tid else None
        if (di and di[0] and di[0] > 1) or (dur and dur > 1):
            ok = True
    return ok, embed, stream, f"probe={pr}"



def run(res):
    if not ANIME:
        res["error"] = "ANIME env yok"
        return
    os.makedirs(VAR, exist_ok=True)
    load_cookie()
    ensure_tab()
    clear_ads()

    cands = search(ANIME) if not PAGE else None
    if PAGE:
        chosen = PAGE if PAGE.startswith("http") else BASE + PAGE
        chosen = chosen.replace(BASE, "")
        scored = [(0, chosen, chosen.strip("/").split("/")[-1])]
        log("SABIT SAYFA:", BASE + chosen)
    else:
        if not cands:
            res["error"] = "tranimeizle'de sonuc yok"
            log("Sonuc yok:", ANIME)
            return
        scored = pick_anime(cands, ANIME)
    chosen = scored[0][1]
    slug = chosen.strip("/").split("/")[-1]
    if len(scored) > 1:
        log("Adaylar:", ", ".join(h for _, h, _ in scored[:6]))
    log("SECILEN:", BASE + chosen)
    res["slug"] = slug
    res["page"] = BASE + chosen

    goto_url(BASE + chosen)
    wait_for_load()
    wait(1.5)
    if check_captcha() and not pass_captcha():
        res["error"] = "CAPTCHA: otomatik cozulemedi"
        log("CAPTCHA cikti ve otomatik cozulemedi.")
        return
    clear_ads()
    eps = get_episodes()
    total = len(eps)
    res["total"] = total
    if total == 0:
        res["error"] = "bolum listesi bos"
        log("Bolum bulunamadi:", ANIME)
        return

    prog = {}
    if os.path.exists(PROG_FILE):
        try:
            prog = _read_json(PROG_FILE)
        except Exception:
            prog = {}
    start = 0 if RESET else int(prog.get(slug, 0))
    if START:
        try:
            start = max(0, int(START))
        except ValueError:
            pass
    if start >= total:
        res["error"] = f"tum bolumler bitti ({total} bolum)"
        log(f"TUM BOLUMLER BITTI: {slug} ({total} bolum). RESET=1 ile bastan.")
        return
    batch = list(range(start, min(start + N, total)))
    log(f"Anime: {slug} | toplam {total} bolum | bu sefer: {[i+1 for i in batch]}")

    results = res["results"]
    consec_fail = 0
    for i in batch:
        text, href = eps[i]
        epnum = i + 1
        m = re.search(r"(\d+)\.\s*B[oö]l", text)
        if m:
            epnum = int(m.group(1))
        goto_url(BASE + href)
        wait_for_load()
        wait(1.2)
        clear_ads()
        page_url = BASE + href
        if check_captcha() and not pass_captcha():
            log(f"EP{epnum}: CAPTCHA - durduruldu")
            results.append({"ep": epnum, "page": page_url, "source": None, "m3u8": None, "status": "captcha"})
            break
        srcs = get_sources()
        if not srcs:
            log(f"EP{epnum}: kaynak yok")
            results.append({"ep": epnum, "page": page_url, "source": None, "m3u8": None, "status": "no-sources"})
            consec_fail += 1
            if consec_fail >= 2:
                log("Ardisik 2 bolumde kaynak yok (henuz yayinda olmayabilir) - parti kesildi.")
                break
            continue
        fansubs = get_fansubs()
        cur = active_fansub()
        picked = try_all_sources()
        used_fansub = fansubs[cur] if cur < len(fansubs) else None
        if not picked and len(fansubs) > 1:
            for fi in [k for k in range(len(fansubs)) if k != cur]:
                log(f"EP{epnum}: kaynaklar kirik, fansub degisiyor -> {fansubs[fi]}")
                if not select_fansub(fi):
                    log(f"EP{epnum}: fansub secilemedi ({fansubs[fi]})")
                    continue
                picked = try_all_sources()
                if picked:
                    used_fansub = fansubs[fi]
                    break
        if picked:
            log(f"EP{epnum}: OK -> {used_fansub or '-'} / {picked['source']} | {picked['m3u8']}")
            results.append({"ep": epnum, "page": page_url, "source": picked["source"],
                            "fansub": used_fansub, "embed": picked["embed"],
                            "m3u8": picked["m3u8"], "status": "ok"})
            prog[slug] = max(int(prog.get(slug, 0) or 0), i + 1)
            consec_fail = 0
        else:
            log(f"EP{epnum}: CALISAN KAYNAK BULUNAMADI (tum fansub'lar denendi)")
            results.append({"ep": epnum, "page": page_url, "source": None, "m3u8": None, "status": "fail"})
            consec_fail += 1
            if consec_fail >= 2:
                log("Ardisik 2 bolumde calisan kaynak yok (henuz yayinda olmayabilir) - parti kesildi.")
                _write_json(PROG_FILE, prog)
                break
        _write_json(PROG_FILE, prog)

    outf = os.path.join(VAR, slug + ".json")
    hist = []
    if os.path.exists(outf):
        try:
            hist = _read_json(outf)
        except Exception:
            hist = []
    if isinstance(hist, dict):
        hist = hist.get("runs", [])
    hist.append({"anime": ANIME, "slug": slug, "generated": time.strftime("%Y-%m-%d %H:%M:%S"), "results": results})
    _write_json(outf, hist, ensure_ascii=False, indent=1)

    log("---- OZET ----")
    for r in results:
        log(f"{r['ep']:>4}. bolum | {r['source'] or '-':9} | {r['m3u8'] or '-'}")
    log("Sonraki cagri bu anime icin", prog.get(slug, 0), "/", total)
    res["next"] = prog.get(slug, 0)
    res["ok"] = any(r.get("m3u8") for r in results)


def main():
    res = {"ok": False, "anime": ANIME, "slug": None, "page": None,
           "total": 0, "results": [], "error": None, "next": None}
    try:
        ok, msg = ensure_browser()
        if not ok:
            raise RuntimeError(msg)
        run(res)
    except Exception as e:
        res["ok"] = False
        res["error"] = res.get("error") or f"{type(e).__name__}: {e}"
        log("HATA:", res["error"])
    if not res["ok"] and not res["error"]:
        res["error"] = "calisan kaynak bulunamadi"
    emit(res)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()
