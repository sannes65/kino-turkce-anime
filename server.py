#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kino - yerel m3u8 (HLS) icin Jellyfin-benzeri mini kutuphane + player.
Sadece Python standart kutuphanesi kullanir; npm/pip gerektirmez.

Calistir: python3 server.py  ->  http://localhost:8484
"""
import json
import os
import queue
import re
import ipaddress
import socket
import subprocess
import threading
import time
import html as htmlmod
import io
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime, timedelta, timezone
import sys

from ram_cache import RamCache, Cancelled, byte_range
from browser import CDP_URL, ensure_browser, local_dir

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
DATA_FILE = Path(os.environ.get("KINO_DATA") or ROOT / "data.json")
PORT = int(os.environ.get("KINO_PORT", "8484"))
HOST = os.environ.get("KINO_HOST", "0.0.0.0")
PID_FILE = local_dir() / ("server-%d.pid" % PORT)   # makineye ozel; Drive'a yazilmaz

# ---- bolum cekme (fetcher.py, tranimeizle) ayarlari
FETCHER = Path(os.environ.get("KINO_FETCHER") or ROOT / "fetcher.py")
STATE_DIR = Path(os.environ.get("KINO_STATE") or ROOT / "state")
LOGDIR = ROOT / "logs"
BATCH = int(os.environ.get("KINO_BATCH", "10"))       # her seferde kac bolum
JOB_TIMEOUT = int(os.environ.get("KINO_JOB_TIMEOUT", "1800"))

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

LOCK = threading.RLock()
DB = None

DEFAULT_SETTINGS = {
    "autoplayNext": True, "autoplayCountdown": 8, "theme": "violet",
    "rows": True, "batch": BATCH, "reduceMotion": False, "language": "tr",
    "ramPlayback": False, "ramQuality": 720,
}

DEFAULT_DB = {"animes": [], "progress": {}, "lists": {}, "history": [],
              "settings": {}}


def load_db():
    global DB
    if DATA_FILE.exists():
        try:
            with DATA_FILE.open("r", encoding="utf-8") as f:
                DB = json.load(f)
        except Exception:
            DB = json.loads(json.dumps(DEFAULT_DB))
    else:
        DB = json.loads(json.dumps(DEFAULT_DB))
    DB.setdefault("animes", [])
    DB.setdefault("progress", {})
    DB.setdefault("lists", {})
    DB.setdefault("history", [])
    DB.setdefault("settings", {})
    for k, v in DEFAULT_SETTINGS.items():
        DB["settings"].setdefault(k, v)


def save_db():
    with LOCK:
        tmp = "%s.%s.tmp" % (DATA_FILE, threading.get_ident())
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(DB, f, ensure_ascii=False, indent=2)
        os.replace(tmp, DATA_FILE)


# ----------------------------- yardimcilar ------------------------------

def slugify(title):
    s = title.lower()
    s = re.sub(r"ç", "c", s)
    s = re.sub(r"ğ|ğ", "g", s)
    s = re.sub(r"ı|i", "i", s)
    s = re.sub(r"ö", "o", s)
    s = re.sub(r"ş", "s", s)
    s = re.sub(r"ü", "u", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "anime"


def px_url(u):
    return "/px?u=" + urllib.parse.quote(u, safe="")


def rewrite_playlist(text, base):
    """m3u8 icerisindeki tum URI'leri lokal proxy uzerinden gecir.
    AitrVip gibi kaynaklari segment hotlink korumasindan gecirmek icin
    playlist hostunun kokunu Referer olarak otomatik ekle."""
    bp = urllib.parse.urlsplit(base)
    auto_ref = bp.scheme + "://" + bp.netloc + "/"

    def px_auto(u):
        return "/px?u=" + urllib.parse.quote(u, safe="") + \
            "&ref=" + urllib.parse.quote(auto_ref, safe="")

    out = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            if 'URI="' in s:
                def repl(m):
                    u = m.group(1)
                    if u.startswith("data:") or u.startswith("/px"):
                        return m.group(0)
                    return 'URI="%s"' % px_auto(urllib.parse.urljoin(base, u))
                s = re.sub(r'URI="([^"]+)"', repl, s)
            out.append(s)
        elif s:
            if re.match(r"^https?://", s, re.I):
                absolute = s
            else:
                absolute = urllib.parse.urljoin(base, s)
            out.append(px_auto(absolute))
        else:
            out.append("")
    return "\n".join(out) + "\n"


def guess_content_type(url, upstream):
    if upstream and ("video" in upstream or "mpegurl" in upstream):
        return upstream
    ext = os.path.splitext(urllib.parse.urlsplit(url).path)[1].lower()
    table = {
        ".ts": "video/mp2t", ".m2ts": "video/mp2t", ".m4s": "video/mp4",
        ".mp4": "video/mp4", ".m4v": "video/mp4", ".webm": "video/webm",
        ".mkv": "video/x-matroska", ".aac": "audio/aac", ".m4a": "audio/mp4",
        ".mp3": "audio/mpeg", ".vtt": "text/vtt", ".srt": "text/plain",
        ".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
    }
    if ext in table:
        return table[ext]
    return "application/octet-stream"


def fetch_upstream(url, extra_headers=None, timeout=30):
    headers = {"User-Agent": UA, "Accept": "*/*"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req, timeout=timeout)
    return resp


PX_HOST_OK = {}


def px_allowed(u):
    """/px'in localhost ve yerel ag adreslerine gitmesini engelle (SSRF)."""
    host = (urllib.parse.urlsplit(u).hostname or "").strip().lower()
    if not host:
        return False
    if host not in PX_HOST_OK:
        ok = True
        try:
            infos = socket.getaddrinfo(host, None)
        except Exception:
            infos = []          # cozumlenemeyen host: upstream zaten 502 verir
        for info in infos:
            try:
                ip = ipaddress.ip_address(info[4][0])
            except ValueError:
                continue
            if (ip.is_loopback or ip.is_private or ip.is_link_local
                    or ip.is_multicast or ip.is_reserved
                    or ip.is_unspecified):
                ok = False
                break
        PX_HOST_OK[host] = ok
        if len(PX_HOST_OK) > 300:
            PX_HOST_OK.clear()
    return PX_HOST_OK[host]


class RamRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not px_allowed(newurl):
            raise ValueError("RAM kaynağının yönlendirmesine erişilemiyor")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def ram_download(url, ref, limit, cancel):
    if urllib.parse.urlsplit(url).scheme not in ("http", "https") or not px_allowed(url):
        raise ValueError("Bu video kaynağına RAM modunda erişilemiyor")
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*", "Referer": ref})
    for attempt in range(2):
        if cancel.is_set():
            raise Cancelled()
        try:
            with urllib.request.build_opener(RamRedirect()).open(request, timeout=20) as resp:
                final = resp.geturl()
                if not px_allowed(final):
                    raise ValueError("Bu video kaynağına RAM modunda erişilemiyor")
                length = resp.headers.get("Content-Length")
                if length and int(length) > limit:
                    raise ValueError("Kaynak tek parçada çok büyük veri gönderiyor. Akışla izleyebilirsin.")
                with io.BytesIO() as buf:
                    while True:
                        if cancel.is_set():
                            raise Cancelled()
                        part = resp.read(min(65536, limit - buf.tell() + 1))
                        if not part:
                            break
                        buf.write(part)
                        if buf.tell() > limit:
                            raise ValueError("Video parçası RAM sınırını aşıyor. Akışla izleyebilirsin.")
                    if length and buf.tell() != int(length):
                        raise OSError("Incomplete resource")
                    body = buf.getvalue()
                return body, final, guess_content_type(final, resp.headers.get("Content-Type", ""))
        except (urllib.error.URLError, OSError):
            if attempt or cancel.wait(.5):
                raise


RAM = RamCache(ram_download, limit=max(128, min(4096, int(os.environ.get("KINO_RAM_MB", "1024")))) * 1024 * 1024)


ANILIST_URL = "https://graphql.anilist.co"
ANILIST_Q = """
query($s:String){
  Page(perPage:8){
    media(type:ANIME,search:$s,sort:SEARCH_MATCH){
      id format status seasonYear episodes averageScore
      title{romaji english native}
      genres
      description(asHtml:false)
      coverImage{extraLarge large color}
      bannerImage
    }
  }
}
"""


def anilist_lookup(query):
    """AniList'te anime araması; basitlestirilmis meta dondurur ya da None."""
    body = json.dumps({"query": ANILIST_Q, "variables": {"s": query}}).encode()
    req = urllib.request.Request(
        ANILIST_URL, data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "User-Agent": UA},
        method="POST")
    with urllib.request.urlopen(req, timeout=12) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    media = payload.get("data", {}).get("Page", {}).get("media", []) or []
    if not media:
        return None
    ql = query.lower()
    best = None
    for m in media:
        titles = [t for t in (m.get("title") or {}).values() if t]
        if any(t.lower() == ql for t in titles):
            best = m
            break
    if best is None:
        tv = [m for m in media if m.get("format") in ("TV", "ONA", "OVA", "MOVIE")]
        best = (tv or media)[0]
    t = best.get("title") or {}
    desc = best.get("description") or ""
    desc = re.sub(r"<[^>]+>", " ", desc)
    desc = htmlmod.unescape(desc)
    desc = re.sub(r"\s+", " ", desc).strip()
    if len(desc) > 380:
        desc = desc[:377].rstrip() + "…"
    return {
        "anilistId": best.get("id"),
        "displayTitle": t.get("english") or t.get("romaji"),
        "poster": (best.get("coverImage") or {}).get("extraLarge"),
        "banner": best.get("bannerImage"),
        "outline": desc,
        "year": best.get("seasonYear"),
        "score": best.get("averageScore"),
        "genres": best.get("genres") or [],
        "episodes": best.get("episodes"),
        "fetchedAt": int(time.time()),
    }


ANILIST_SEARCH_Q = """
query($s:String,$p:Int,$sort:[MediaSort]){
  Page(perPage:$p){
    media(type:ANIME,search:$s,sort:$sort,isAdult:false){
      id format status seasonYear episodes averageScore popularity
      title{romaji english native}
      genres
      description(asHtml:false)
      coverImage{extraLarge large color}
      bannerImage
    }
  }
}
"""

SEARCH_CACHE = {}


def _clean_desc(desc, limit=300):
    desc = re.sub(r"<[^>]+>", " ", desc or "")
    desc = htmlmod.unescape(desc)
    desc = re.sub(r"\s+", " ", desc).strip()
    if len(desc) > limit:
        desc = desc[:limit - 3].rstrip() + "…"
    return desc


def media_to_dict(m):
    """AniList media -> kino arama sonucu / meta."""
    t = m.get("title") or {}
    return {
        "anilistId": m.get("id"),
        "title": t.get("english") or t.get("romaji") or t.get("native"),
        "romaji": t.get("romaji"),
        "english": t.get("english"),
        "native": t.get("native"),
        "year": m.get("seasonYear"),
        "format": m.get("format"),
        "status": m.get("status"),
        "episodes": m.get("episodes"),
        "score": m.get("averageScore"),
        "popularity": m.get("popularity"),
        "genres": (m.get("genres") or [])[:6],
        "poster": (m.get("coverImage") or {}).get("extraLarge")
        or (m.get("coverImage") or {}).get("large"),
        "banner": m.get("bannerImage"),
        "outline": _clean_desc(m.get("description")),
        "nextAiring": m.get("nextAiringEpisode"),
        "latestAired": next(iter((m.get("airingSchedule") or {}).get("nodes") or []), None),
    }


def anilist_search(query, limit=24):
    """AniList veritabaninda arama. Sorgu bossa populer animeler."""
    q = (query or "").strip()
    cache_key = (q.lower(), limit)
    hit = SEARCH_CACHE.get(cache_key)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    variables = {"p": limit,
                 "sort": ["SEARCH_MATCH"] if q else ["POPULARITY_DESC"]}
    if q:
        variables["s"] = q
    body = json.dumps({"query": ANILIST_SEARCH_Q, "variables": variables}).encode()
    req = urllib.request.Request(
        ANILIST_URL, data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "User-Agent": UA},
        method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    media = payload.get("data", {}).get("Page", {}).get("media", []) or []
    out = [media_to_dict(m) for m in media if m.get("title")]
    SEARCH_CACHE[cache_key] = (time.time(), out)
    return out


ANILIST_BROWSE_Q = """
query($page:Int,$perPage:Int,$sort:[MediaSort],$season:MediaSeason,$year:Int,
      $format:MediaFormat,$genre:String,$status:MediaStatus,$search:String){
  Page(page:$page, perPage:$perPage){
    pageInfo{total currentPage lastPage hasNextPage}
    media(type:ANIME, isAdult:false, search:$search, sort:$sort, season:$season,
          seasonYear:$year, format:$format, genre:$genre, status:$status){
      id format status seasonYear episodes averageScore popularity
      title{romaji english native}
      genres
      description(asHtml:false)
      coverImage{extraLarge large color}
      bannerImage
      nextAiringEpisode{episode airingAt}
    }
  }
}
"""

ANILIST_DETAIL_Q = """
query($id:Int){
  Media(id:$id, type:ANIME){
    id idMal
    title{romaji english native}
    description(asHtml:false)
    format status season seasonYear episodes duration averageScore popularity favourites
    genres
    tags{name rank}
    studios(isMain:true){nodes{name}}
    coverImage{extraLarge large color}
    bannerImage
    trailer{id site}
    nextAiringEpisode{episode airingAt timeUntilAiring}
    startDate{year month day}
    endDate{year month day}
    relations{edges{relationType node{id type format averageScore coverImage{large}
      title{romaji english}}}}
    recommendations(perPage:12, sort:RATING_DESC){nodes{mediaRecommendation{
      id format averageScore coverImage{large} title{romaji english}}}}
    externalLinks{site url}
  }
}
"""

ANILIST_SCHEDULE_Q = """
query($from:Int,$to:Int,$page:Int){
  Page(page:$page, perPage:50){
    pageInfo{hasNextPage currentPage}
    airingSchedules(airingAt_greater:$from, airingAt_lesser:$to, sort:TIME){
      airingAt episode
      media{id type isAdult format averageScore episodes title{romaji english} coverImage{large}}
    }
  }
}
"""

API_CACHE = {}          # key -> (ts, value)

ANILIST_TRACKING_Q = """
query($ids:[Int],$page:Int,$now:Int){
  Page(page:$page,perPage:50){
    pageInfo{hasNextPage}
    media(id_in:$ids,type:ANIME){
      id status episodes seasonYear format averageScore
      title{romaji english} coverImage{large}
      nextAiringEpisode{episode airingAt}
    }
  }
}
"""


def anilist_query(query, variables, ttl=300):
    key = json.dumps({"q": query.strip(), "v": variables}, sort_keys=True)
    hit = API_CACHE.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        ANILIST_URL, data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "User-Agent": UA},
        method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("errors"):
        raise RuntimeError("; ".join(e.get("message", "AniList hatası") for e in payload["errors"]))
    data = payload.get("data") or {}
    API_CACHE[key] = (time.time(), data)
    if len(API_CACHE) > 400:
        for k in sorted(API_CACHE, key=lambda k: API_CACHE[k][0])[:200]:
            API_CACHE.pop(k, None)
    return data


def anilist_browse(page=1, per=30, sort="POPULARITY_DESC", season=None,
                   year=None, fmt=None, genre=None, status=None, search=None):
    variables = {"page": max(1, int(page)), "perPage": min(50, int(per)),
                 "sort": [sort]}
    if season:
        variables["season"] = season
    if year:
        variables["year"] = int(year)
    if fmt:
        variables["format"] = fmt
    if status:
        variables["status"] = status
    if genre:
        variables["genre"] = genre
    if search:
        variables["search"] = search
    data = anilist_query(ANILIST_BROWSE_Q, variables)
    page_data = data.get("Page") or {}
    media = page_data.get("media") or []
    return {"results": [media_to_dict(m) for m in media if m.get("title")],
            "pageInfo": page_data.get("pageInfo") or {}}


def anilist_detail(mid):
    data = anilist_query(ANILIST_DETAIL_Q, {"id": int(mid)}, ttl=900)
    m = data.get("Media")
    if not m:
        return None
    base = media_to_dict(m)
    base.update({
        "id": m.get("id"),
        "idMal": m.get("idMal"),
        "favourites": m.get("favourites"),
        "duration": m.get("duration"),
        "season": m.get("season"),
        "studio": ", ".join(n.get("name") for n in
                            ((m.get("studios") or {}).get("nodes") or [])),
        "tags": [{"name": t["name"], "rank": t.get("rank", 0)}
                 for t in (m.get("tags") or [])[:14]],
        "trailer": (m.get("trailer") or {}).get("id") if m.get("trailer") else None,
        "nextAiring": m.get("nextAiringEpisode"),
        "startDate": m.get("startDate"),
        "endDate": m.get("endDate"),
        "relations": [{
            "relation": e.get("relationType"),
            "id": (e.get("node") or {}).get("id"),
            "format": (e.get("node") or {}).get("format"),
            "score": (e.get("node") or {}).get("averageScore"),
            "poster": ((e.get("node") or {}).get("coverImage") or {}).get("large"),
            "title": ((e.get("node") or {}).get("title") or {}).get("english")
            or ((e.get("node") or {}).get("title") or {}).get("romaji"),
        } for e in ((m.get("relations") or {}).get("edges") or [])
            if (e.get("node") or {}).get("type") == "ANIME"][:12],
        "recommendations": [media_to_dict(n["mediaRecommendation"])
                            for n in ((m.get("recommendations") or {}).get("nodes") or [])
                            if n.get("mediaRecommendation")],
        "links": [{"site": l.get("site"), "url": l.get("url")}
                  for l in (m.get("externalLinks") or [])],
    })
    return base


def anilist_schedule(days=7, offset_days=0):
    # Türkiye gün sınırı; işletim sisteminin saat diliminden bağımsız.
    tr = timezone(timedelta(hours=3))
    today = datetime.fromtimestamp(time.time(), tr).replace(hour=0, minute=0, second=0, microsecond=0)
    start = int(today.timestamp()) + offset_days * 86400
    end = start + days * 86400
    out, page = [], 1
    while page <= 40:
        data = anilist_query(ANILIST_SCHEDULE_Q,
                             {"from": start - 1, "to": end, "page": page}, ttl=600)
        p = data.get("Page") or {}
        out.extend([{
            "airingAt": s.get("airingAt"),
            "episode": s.get("episode"),
            "media": media_to_dict(s.get("media") or {}),
        } for s in (p.get("airingSchedules") or [])
            if s.get("media") and s["media"].get("type") == "ANIME"
            and not s["media"].get("isAdult") and s.get("airingAt")])
        if not (p.get("pageInfo") or {}).get("hasNextPage"):
            break
        page += 1
    if page > 40:
        raise RuntimeError("Yayın takvimi çok büyük; daha kısa bir tarih aralığı seçin")
    out.sort(key=lambda x: x["airingAt"])
    return out


def build_tracking():
    with LOCK:
        db = json.loads(json.dumps(DB))
    animes = [a for a in db["animes"] if is_tracked(a, db["lists"].get(a["id"], {}))]
    ids = list(dict.fromkeys(int(a["meta"]["anilistId"]) for a in animes
                            if str((a.get("meta") or {}).get("anilistId", "")).isdigit()))
    remote, warning = {}, None
    try:
        # Küçük gruplar: bir anime kaybolduğunda diğerlerini kaybetme.
        for i in range(0, len(ids), 50):
            group = ids[i:i + 50]
            aliases = "\n".join(
                "a%d:Page(perPage:1){airingSchedules(mediaId:%d,airingAt_lesser:$now,sort:TIME_DESC){episode airingAt}}" % (mid, mid)
                for mid in group)
            query = ANILIST_TRACKING_Q.rsplit("}", 1)[0] + aliases + "\n}"
            # Dakika sınırı önbellek anahtarını kararlı tutar.
            data = anilist_query(query, {"ids": group, "page": 1, "now": int(time.time()) // 300 * 300})
            for m in (data.get("Page") or {}).get("media") or []:
                converted = media_to_dict(m)
                latest = (data.get("a%d" % m["id"]) or {}).get("airingSchedules") or []
                if latest:
                    converted["latestAired"] = latest[0]
                remote[str(m["id"])] = converted
    except Exception:
        warning = "AniList'e ulaşılamadı. Yayın bilgileri güncel olmayabilir; izleme kayıtların korunuyor."
    items = []
    for a in animes:
        meta = a.get("meta") or {}
        live = remote.get(str(meta.get("anilistId")))
        m = {**meta, **(live or {})}
        nxt, latest = m.get("nextAiring") or {}, m.get("latestAired") or {}
        aired = latest.get("episode")
        estimated = False
        if aired is None and live:
            if nxt.get("episode"):
                aired, estimated = max(0, nxt["episode"] - 1), True
            elif m.get("status") == "FINISHED":
                aired = m.get("episodes")
        done = sorted(int(k.rsplit(":", 1)[1]) for k, p in db["progress"].items()
                      if k.startswith(a["id"] + ":") and k.rsplit(":", 1)[1].isdigit() and p.get("done"))
        watched = len([n for n in done if aired is None or 1 <= n <= aired])
        next_unwatched = next((n for n in range(1, (aired or 0) + 1) if n not in done), None)
        items.append({"animeId": a["id"], "title": a["title"], "media": m,
                      "live": live is not None, "aired": aired, "estimated": estimated,
                      "watched": watched, "unwatched": max(0, aired - watched) if aired is not None else None,
                      "nextUnwatched": next_unwatched, "lastWatched": done[-1] if done else None,
                      "available": [e["n"] for e in a.get("episodes", [])]})
    items.sort(key=lambda x: (not bool(x["unwatched"]), (x["media"].get("nextAiring") or {}).get("airingAt", 10**12)))
    return {"ok": True, "items": items, "warning": warning, "checkedAt": int(time.time()), "cacheSeconds": 300}


def is_tracked(anime, entry):
    return entry.get("tracking", entry.get("status") not in ("completed", "dropped", "onhold"))


# ----------------------------- istatistik ------------------------------

def build_stats():
    with LOCK:
        progs = dict(DB["progress"])
        animes = {a["id"]: a for a in DB["animes"]}
        hist = list(DB["history"])
        lists = dict(DB["lists"])
    seconds = 0
    eps_done = 0
    per_genre = {}
    watched_ids = set()
    for key, p in progs.items():
        aid = key.rsplit(":", 1)[0]
        try:
            pos = float(p.get("pos") or 0)
            dur = float(p.get("dur") or 0)
        except Exception:
            continue
        if pos > 30:
            seconds += min(pos, dur) if dur else pos
            watched_ids.add(aid)
        if p.get("done"):
            eps_done += 1
    for aid in watched_ids:
        a = animes.get(aid) or {}
        for g in ((a.get("meta") or {}).get("genres") or []):
            per_genre[g] = per_genre.get(g, 0) + 1
    days = {}
    for h in hist[-2000:]:
        day = time.strftime("%Y-%m-%d", time.localtime(h.get("at", 0)))
        days[day] = days.get(day, 0) + 1
    loc_now = time.localtime()
    local_midnight = time.mktime(loc_now) - (loc_now.tm_hour * 3600
                                            + loc_now.tm_min * 60 + loc_now.tm_sec)
    anchor = local_midnight + 43200   # bugunun yerel öğlesi; UTC/local karismasin
    streak = 0
    for i in range(0, 400):
        d = time.strftime("%Y-%m-%d", time.localtime(anchor - i * 86400))
        if days.get(d):
            streak += 1
        elif i > 0:
            break
    top = sorted(per_genre.items(), key=lambda x: -x[1])[:8]
    return {
        "seconds": int(seconds),
        "episodesDone": eps_done,
        "animes": len(animes),
        "onList": len([1 for v in lists.values() if v.get("status")]),
        "favorites": len([1 for v in lists.values() if v.get("favorite")]),
        "streak": streak,
        "days": days,
        "topGenres": [{"genre": g, "count": c} for g, c in top],
        "updated": int(time.time()),
    }


# ----------------------------- bolum cekme kuyrugu -----------------------------

JOB_Q = queue.Queue()


def find_anime(aid):
    return next((a for a in DB["animes"] if a["id"] == aid), None)


def set_fetch(aid, **kw):
    """anime['fetch'] durumunu guncelle (UI bunu okur)."""
    with LOCK:
        a = find_anime(aid)
        if not a:
            return
        f = a.setdefault("fetch", {})
        f.update(kw)
        f["updated"] = int(time.time())
        save_db()


def merge_episodes(aid, items):
    """[(n, url)] listesini animeye ekle; ayni numarada link guncellenir."""
    with LOCK:
        a = find_anime(aid)
        if not a:
            return 0
        existing = {e["n"]: e for e in a["episodes"]}
        added = 0
        for n, url in items:
            if n in existing:
                existing[n]["url"] = url
            else:
                existing[n] = {"n": n, "url": url, "title": None}
                added += 1
        a["episodes"] = sorted(existing.values(), key=lambda x: x["n"])
        save_db()
        return added


def ensure_chrome():
    """Chromium tabanli tarayiciyi CDP ile ac; zaten aciksa dokunma. (ok, mesaj)"""
    return ensure_browser()


def enqueue_fetch(aid, count=None, start=None, titles=None, reason=""):
    """Anime icin bolum cekme isi kuyruga at (zaten siradaysa atla)."""
    with LOCK:
        a = find_anime(aid)
        if not a:
            return False
        if (a.get("fetch") or {}).get("status") in ("queued", "running"):
            return False
        count = int(count or (a.get("autoFetch") or {}).get("batch") or BATCH)
        set_fetch(aid, status="queued", message="Sırada…", requested=count,
                  got=0, started=None, error=None, reason=reason)
        job = {"animeId": aid, "count": count, "start": start,
               "titles": titles or a.get("searchTitles") or [a.get("title")]}
    JOB_Q.put(job)
    return True


def maybe_autofetch(a, ep):
    """Kullanici esige (ilk partide 9. bolum) geldiyse sonraki 10'u cek."""
    if not a:
        return False
    af = a.get("autoFetch") or {}
    if not af.get("enabled", False):
        return False
    eps = a.get("episodes") or []
    if not eps:
        return False
    maxep = max(e["n"] for e in eps)
    next_at = af.get("nextAt") or (maxep - 1)
    total = (a.get("meta") or {}).get("episodes") or 0
    if total and maxep >= total:
        return False
    # Yayinda olan (10'dan az bolumlu) animelerde ayni kontrolu surekli
    # tekrarlamayi engelle: son kontrol ayni maxep icin 15 dk icindeyse atla.
    now = int(time.time())
    checked = int(af.get("checkedAt") or 0)
    if checked and now - checked < 900 and maxep <= int(af.get("checkedMax") or 0):
        return False
    try:
        ep = int(ep)
    except Exception:
        return False
    if ep < next_at:
        return False
    return enqueue_fetch(a["id"], BATCH, maxep, reason="ep%d" % ep)


CURRENT = {"animeId": None, "proc": None, "started": None}
CANCELLED = set()


def queue_snapshot():
    with LOCK:
        items = []
        for a in DB["animes"]:
            f = a.get("fetch") or {}
            if f.get("status") in ("queued", "running"):
                items.append({
                    "animeId": a["id"], "title": a["title"],
                    "status": f.get("status"), "got": f.get("got", 0),
                    "requested": f.get("requested", BATCH),
                    "message": f.get("message"),
                    "started": f.get("started"),
                    "updated": f.get("updated"),
                })
    items.sort(key=lambda x: (x["status"] != "running", x.get("started") or 0))
    return {"items": items, "queued": JOB_Q.qsize(),
            "current": CURRENT.get("animeId"), "workers": 1}


def log_tail(aid, n=80):
    if not re.match(r"^[\w\-]+$", str(aid)):
        return []
    p = LOGDIR / ("%s.log" % aid)
    if not p.exists():
        return []
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    return lines[-n:]


def cancel_job(aid):
    CANCELLED.add(aid)
    proc = CURRENT.get("proc")
    if CURRENT.get("animeId") == aid and proc and proc.poll() is None:
        try:
            proc.kill()
        except Exception:
            pass
        return True
    with LOCK:
        a = find_anime(aid)
        if a and (a.get("fetch") or {}).get("status") == "queued":
            a["fetch"].update(status="error", message="İptal edildi",
                              updated=int(time.time()))
            save_db()
            return True
    return False


def run_skill(title, start, count, aid, page=""):
    """Skill'i calistir; cikan bolumleri canli canli DB'ye yaz."""
    LOGDIR.mkdir(exist_ok=True)
    logf = LOGDIR / ("%s.log" % aid)
    env = os.environ.copy()
    env.update({
        "ANIME": title, "N": str(count), "START": str(start),
        "PAGE": page or "", "KINO_STATE": str(STATE_DIR),
        "KINO_CDP_URL": CDP_URL, "PYTHONIOENCODING": "utf-8",
    })
    popen_kw = {}
    if sys.platform == "win32":
        popen_kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    res = {"ok": False, "results": [], "total": 0, "slug": None, "error": None}
    got = 0
    with logf.open("a", encoding="utf-8") as lf:
        lf.write("\n=== %s | ANIME=%r START=%s N=%s ===\n"
                 % (time.strftime("%Y-%m-%d %H:%M:%S"), title, start, count))
        lf.flush()
        proc = subprocess.Popen(
            [sys.executable, "-X", "utf8", str(FETCHER)], env=env, cwd=str(ROOT),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1, **popen_kw)
        killer = threading.Timer(JOB_TIMEOUT, proc.kill)
        killer.start()
        CURRENT.update({"animeId": aid, "proc": proc, "started": time.time()})
        try:
            for line in proc.stdout:
                line = line.rstrip("\n")
                lf.write(line + "\n")
                lf.flush()
                if aid in CANCELLED:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                if line.startswith("KINO_RESULT:"):
                    try:
                        res.update(json.loads(line[len("KINO_RESULT:"):]))
                    except Exception:
                        pass
                    continue
                m = re.match(r"^EP(\d+): OK -> (.+?) \| (\S+)", line)
                if m:
                    n, url = int(m.group(1)), m.group(3)
                    merge_episodes(aid, [(n, url)])
                    got += 1
                    set_fetch(aid, got=got, message="Bölüm %d hazır" % n)
            proc.wait()
        finally:
            killer.cancel()
            CURRENT.update({"animeId": None, "proc": None, "started": None})
    if not res.get("results"):
        res["results"] = []
    return res


def run_job(job):
    aid = job["animeId"]
    if aid in CANCELLED:  # siradayken iptal edilmis is yeniden calismasin
        CANCELLED.discard(aid)
        set_fetch(aid, status="error", message="İptal edildi",
                  finished=int(time.time()))
        return
    a = find_anime(aid)
    if not a:
        return
    start = job.get("start")
    if start is None:
        start = len(a.get("episodes") or [])
    count = int(job.get("count") or BATCH)
    titles = [t for t in (job.get("titles") or []) if t] or [a.get("title")]
    set_fetch(aid, status="running", message="Chrome kontrol ediliyor…",
              requested=count, got=0, started=int(time.time()), start=start)
    ok, why = ensure_chrome()
    if not ok:
        set_fetch(aid, status="error", message=why, error=why,
                  finished=int(time.time()))
        return
    if aid in CANCELLED:  # Chrome beklenirken iptal edildi; status "running"de kalmasin
        CANCELLED.discard(aid)
        set_fetch(aid, status="error", message="İptal edildi",
                  finished=int(time.time()))
        return
    last = None
    page = (a.get("sourcePage") or "").strip()
    for t in (titles if not page else titles[:1]):
        set_fetch(aid, message=("Sayfa: %s" % page) if page
                  else ("tranimeizle'de aranıyor: %s" % t))
        last = run_skill(t, start, count, aid, page)
        ok = [r for r in (last.get("results") or []) if r.get("m3u8")]
        if ok:
            break
        if "CAPTCHA" in str(last.get("error") or "").upper():
            break

    res = last or {}
    cancelled = aid in CANCELLED
    CANCELLED.discard(aid)
    if res.get("page"):
        with LOCK:
            a2 = find_anime(aid)
            if a2 and not a2.get("sourcePage"):
                a2["sourcePage"] = res["page"]
                save_db()
    items = []
    for r in (res.get("results") or []):
        if not r.get("m3u8"):
            continue
        try:
            items.append((int(r["ep"]), r["m3u8"]))
        except (KeyError, TypeError, ValueError):
            pass
    added = merge_episodes(aid, items)
    with LOCK:
        a = find_anime(aid)
        if not a:
            return
        eps = a.get("episodes") or []
        maxep = max([e["n"] for e in eps], default=0)
        total = (a.get("meta") or {}).get("episodes") or 0
        af = a.setdefault("autoFetch", {"enabled": True, "batch": BATCH})
        af["batch"] = BATCH
        err = str(res.get("error") or "")
        reached_end = ("tum bolumler bitti" in err.lower()) or (bool(total) and maxep >= total)
        if items:
            af["nextAt"] = maxep - 1
            af["enabled"] = (not total) or maxep < total
            af["checkedAt"] = int(time.time())
            af["checkedMax"] = maxep
            msg = "%d bölüm eklendi (toplam %d)" % (len(items), len(eps))
            if cancelled:
                msg += " (iptal edildi)"
            if af["enabled"]:
                msg += " · %d. bölümde sonraki 10 çekilir" % (maxep - 1)
            st = "done"
        elif reached_end:
            # Yeni bolum cikmamis (ozellikle yayindaki animeler): hata degil.
            # autoFetch acik kalir; yeni bolum gelince tekrar denenir.
            af["enabled"] = (not total) or maxep < total
            af["checkedAt"] = int(time.time())
            af["checkedMax"] = maxep
            msg = "Yeni bölüm yok (toplam %d). Yeni bölüm çıkınca tekrar denenir." % maxep
            st = "done"
        else:
            # CAPTCHA/gecici kaynak hatasi autoFetch'i kalici kapatmasin.
            af["checkedAt"] = int(time.time())
            af["checkedMax"] = maxep
            msg = "İptal edildi" if cancelled else (err or "çalışan kaynak bulunamadı")
            st = "error"
        a.pop("refreshedAt", None)
        save_db()
    set_fetch(aid, status=st, message=msg, got=len(items),
              total_eps=len(eps), finished=int(time.time()),
              error=msg if st == "error" else None)


def job_worker():
    while True:
        job = JOB_Q.get()
        try:
            run_job(job)
        except Exception as e:  # noqa
            msg = "%s: %s" % (type(e).__name__, e)
            set_fetch(job.get("animeId"), status="error", message=msg, error=msg)
        finally:
            JOB_Q.task_done()


# ----------------------------- import parser ------------------------------

def _first_num(prefix):
    p = (prefix or "").lower()
    pats = [
        r"(\d{1,4})\s*[\)\]\.\:\-–]\s*b",
        r"b[öo]l[üu]m\s*[\(\[\{]?(\d{1,4})",
        r"(?:ep|episode|b[öo]l[üu]m)\s*\.?\s*(\d{1,4})\b",
        r"^\s*[\[\(\{]?\s*(\d{1,4})\b",
        r"(\d{1,4})\s*[\)\]\.\:\-–]?\s*$",
    ]
    for pat in pats:
        m = re.search(pat, p)
        if m:
            return int(m.group(1))
    m = re.search(r"\d{1,4}", p)
    return int(m.group(0)) if m else None


def parse_import(text):
    """Import metnini (JSON veya serbest yapi) çözumler.
    Dondurur: (anime_tahmin, [{n, url, title}], numaralandi_mi)
    """
    raw = (text or "").strip()
    if not raw:
        return None, [], False
    items = []
    anime_guess = None
    numbered = False
    if raw[0] in "[{":
        try:
            j = json.loads(raw)
            if isinstance(j, dict):
                anime_guess = j.get("anime") or j.get("title")
                items = j.get("episodes") or j.get("items") or []
                if isinstance(items, dict):
                    items = [{"n": k, "url": v} for k, v in items.items()]
            elif isinstance(j, list):
                items = j
            out = []
            for it in items:
                if isinstance(it, str):
                    out.append({"n": None, "url": it, "title": None})
                    continue
                if isinstance(it, dict):
                    url = it.get("url") or it.get("link") or it.get("src") \
                        or it.get("m3u8") or it.get("hls")
                    n = it.get("n", it.get("ep", it.get("episode",
                        it.get("num", it.get("bolum", it.get("bölüm"))))))
                    try:
                        n = int(n)
                    except Exception:
                        n = None
                    titled = it.get("title") or it.get("name")
                    if url:
                        out.append({"n": n, "url": url, "title": titled})
            items = out
            numbered = any(i["n"] is not None for i in items)
        except Exception:
            items = []
    if not items:
        # serbest metin: satir satir link + bol numarasi
        for line in raw.splitlines():
            line = line.strip()
            urls = re.findall(r"https?://[^\s\"'<>)]+", line)
            if not urls:
                continue
            url = next((u for u in urls if ".m3u8" in u), urls[0])
            url = url.rstrip('.,;"\'')
            at = line.find(url)
            prefix = line[:at] if at > 0 else ""
            n = _first_num(prefix)
            titled = None
            if n is None and at > 0:
                m = re.match(r"^[\[\;\{\s]*([^\-\:\n]+?)\s*$", prefix)
                if m and len(m.group(1)) < 60:
                    titled = m.group(1).strip()
            items.append({"n": n, "url": url, "title": titled})
        numbered = any(i["n"] is not None for i in items)
        if anime_guess is None:
            m = re.search(r"(?:^|\n)\s*(?:anime|anim done?|series)?\s*[\:\-]\s*"
                          r"([^\n\r]{2,60})", raw)
            if m and ".m3u8" not in m.group(1):
                anime_guess = m.group(1).strip()
    # numaralandirma
    if not numbered:
        nxt = 1
        for it in items:
            it["n"] = nxt
            nxt += 1
    else:
        prev = 0
        for it in items:
            if it["n"] is None:
                it["n"] = prev + 1
            prev = max(prev, it["n"])
    seen = {}
    for it in items:
        seen[it["n"]] = it
    items = sorted(seen.values(), key=lambda x: x["n"])
    return anime_guess, items, numbered


def merge_import(title, parsed_items):
    """Ayni addaki anime'ye ekleme; ayni ep numarasinin url'sini guncelle."""
    with LOCK:
        key = slugify(title)
        anime = next((a for a in DB["animes"] if a["id"] == key), None)
        if anime is None:
            anime = {"id": key, "title": title, "created": int(time.time()),
                     "episodes": [], "meta": {}}
            DB["animes"].append(anime)
        existing = {e["n"]: e for e in anime["episodes"]}
        added = 0
        for it in parsed_items:
            if it["n"] in existing:
                existing[it["n"]]["url"] = it["url"]
                if it.get("title"):
                    existing[it["n"]]["title"] = it["title"]
            else:
                existing[it["n"]] = {"n": it["n"], "url": it["url"],
                                     "title": it.get("title")}
                added += 1
        anime["episodes"] = sorted(existing.values(), key=lambda x: x["n"])
        anime.pop("refreshedAt", None)
        save_db()
        return anime, added


# ----------------------------- HTTP sunucu ------------------------------

MIME = {
    ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml",
    ".png": "image/png", ".ico": "image/x-icon", ".json": "application/json",
    ".woff2": "font/woff2",
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "Kino/1.0"

    def log_message(self, fmt, *args):  # sessize al (proxy shell ekmesin)
        pass

    # ---- yardimci cevaplar
    def send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_file(self, rel):
        p = (PUBLIC / rel).resolve()
        if not p.is_relative_to(PUBLIC) or not p.is_file():
            self.send_error(404)
            return
        ctype = MIME.get(p.suffix.lower(), "application/octet-stream")
        body = p.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if self.command == "HEAD":
            return
        self.wfile.write(body)

    def read_body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self.close_connection = True  # govde uzunlugu bozuk; hat akisi bitti
            return b""
        if length > 20_000_000:
            self.close_connection = True  # govde okunmadi; baglantiyi kapat
            return b""
        if length <= 0:
            return b""
        return self.rfile.read(length)

    # ---- GET
    def do_GET(self):
        try:
            self.route_get()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # noqa
            try:
                self.send_json({"ok": False, "error": str(e)}, 500)
            except Exception:
                pass

    def route_get(self):
        parsed = urllib.parse.urlsplit(self.path)
        path = urllib.parse.unquote(parsed.path)
        if path == "/":
            self.send_file("index.html")
        elif path == "/api/library":
            with LOCK:
                lib = json.loads(json.dumps(DB))
            self.send_json(lib)
        elif path == "/api/search":
            q = urllib.parse.parse_qs(parsed.query)
            query = (q.get("q") or [""])[0].strip()
            if any(k in q for k in ("genres", "year", "format", "sort", "page", "status")):
                try:
                    res = anilist_browse(
                        page=(q.get("page") or ["1"])[0],
                        sort=(q.get("sort") or ["POPULARITY_DESC"])[0],
                        year=(q.get("year") or [None])[0] or None,
                        fmt=(q.get("format") or [None])[0] or None,
                        genre=(q.get("genres") or [None])[0] or None,
                        status=(q.get("status") or [None])[0] or None,
                        search=query or None)
                    self.send_json({"ok": True, "query": query, **res})
                except Exception as e:  # noqa
                    self.send_json({"ok": False, "error": "AniList: %s" % e}, 502)
                return
            try:
                self.send_json({"ok": True, "query": query,
                                "results": anilist_search(query)})
            except Exception as e:  # noqa
                self.send_json({"ok": False, "error": "AniList: %s" % e}, 502)
        elif path == "/api/browse":
            q = urllib.parse.parse_qs(parsed.query)
            try:
                res = anilist_browse(
                    page=(q.get("page") or ["1"])[0],
                    per=(q.get("per") or ["30"])[0],
                    sort=(q.get("sort") or ["POPULARITY_DESC"])[0],
                    season=(q.get("season") or [None])[0] or None,
                    year=(q.get("year") or [None])[0] or None,
                    fmt=(q.get("format") or [None])[0] or None,
                    genre=(q.get("genre") or [None])[0] or None,
                    status=(q.get("status") or [None])[0] or None,
                    search=(q.get("q") or [None])[0] or None)
                self.send_json({"ok": True, **res})
            except Exception as e:  # noqa
                self.send_json({"ok": False, "error": "AniList: %s" % e}, 502)
        elif path == "/api/anime":
            q = urllib.parse.parse_qs(parsed.query)
            aid = (q.get("id") or [""])[0]
            anilist_id = (q.get("anilistId") or [""])[0]
            with LOCK:
                local = find_anime(aid) if aid else None
                if local:
                    local = json.loads(json.dumps(local))
            if not anilist_id and local:
                anilist_id = str((local.get("meta") or {}).get("anilistId") or "")
            detail = None
            if anilist_id:
                try:
                    detail = anilist_detail(anilist_id)
                except Exception:
                    detail = None
            if not local and not detail:
                self.send_json({"ok": False, "error": "bulunamadı"}, 404)
                return
            self.send_json({"ok": True, "local": local, "detail": detail})
        elif path == "/api/schedule":
            q = urllib.parse.parse_qs(parsed.query)
            try:
                days = int((q.get("days") or ["7"])[0])
                off = int((q.get("offset") or ["0"])[0])
                if not 1 <= days <= 14 or not -14 <= off <= 56:
                    raise ValueError()
            except ValueError:
                self.send_json({"ok": False, "error": "days 1–14, offset -14–56 aralığında olmalı"}, 400)
                return
            try:
                self.send_json({"ok": True, "items": anilist_schedule(
                    days=days, offset_days=off)})
            except Exception as e:  # noqa
                self.send_json({"ok": False, "error": "AniList: %s" % e}, 502)
        elif path == "/api/tracking":
            self.send_json(build_tracking())
        elif path == "/api/ram/status":
            q = urllib.parse.parse_qs(parsed.query)
            self.send_json(RAM.status((q.get("id") or [None])[0]))
        elif path.startswith("/ram/"):
            self.serve_ram(path)
        elif path == "/api/stats":
            self.send_json({"ok": True, "stats": build_stats()})
        elif path == "/api/queue":
            self.send_json({"ok": True, "queue": queue_snapshot()})
        elif path == "/api/log":
            q = urllib.parse.parse_qs(parsed.query)
            self.send_json({"ok": True,
                            "lines": log_tail((q.get("animeId") or [""])[0])})
        elif path.startswith("/px"):
            self.proxy_get(parsed)
        elif path in ("/favicon.ico",):
            self.send_error(404)
        else:
            rel = path.lstrip("/")
            self.send_file(rel)

    def do_HEAD(self):
        try:
            self.route_get()
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ---- POST
    def do_POST(self):
        try:
            self.route_post()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # noqa
            try:
                self.send_json({"ok": False, "error": str(e)}, 500)
            except Exception:
                pass

    def route_post(self):
        parsed = urllib.parse.urlsplit(self.path)
        path = urllib.parse.unquote(parsed.path)
        body = self.read_body()
        try:
            data = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            data = {}
        if path == "/api/import":
            self.api_import(data)
        elif path == "/api/add":
            self.api_add(data)
        elif path == "/api/anime/fetch":
            self.api_anime_fetch(data)
        elif path == "/api/ep/open":
            self.api_ep_open(data)
        elif path == "/api/list":
            self.api_list(data)
        elif path == "/api/tracking/progress":
            self.api_tracking_progress(data)
        elif path == "/api/ram/prepare":
            self.api_ram_prepare(data)
        elif path == "/api/ram/cancel":
            RAM.cancel(data.get("id"))
            self.send_json({"ok": True})
        elif path == "/api/settings":
            self.api_settings(data)
        elif path == "/api/history/clear":
            with LOCK:
                DB["history"] = []
                save_db()
            self.send_json({"ok": True})
        elif path == "/api/queue/cancel":
            self.send_json({"ok": True, "cancelled": cancel_job(data.get("animeId"))})
        elif path == "/api/refresh":
            self.api_ep_refresh(data)
        elif path == "/api/progress":
            self.api_progress(data)
        elif path == "/api/lookup":
            self.api_lookup(data)
        elif path == "/api/anime/delete":
            self.api_anime_delete(data)
        elif path == "/api/ep/reset":
            self.api_ep_reset(data)
        elif path == "/api/ping":
            self.send_json({"ok": True, "app": "kino", "t": int(time.time())})
        else:
            self.send_json({"ok": False, "error": "unknown endpoint"}, 404)

    def api_ram_prepare(self, data):
        aid, ep = data.get("animeId"), data.get("ep")
        if type(ep) is not int or ep < 1:
            self.send_json({"ok": False, "error": "Geçerli bölüm gerekli"}, 400)
            return
        with LOCK:
            anime = find_anime(aid)
            if not anime:
                self.send_json({"ok": False, "error": "Anime bulunamadı"}, 404)
                return
            quality = DB["settings"].get("ramQuality", 720)
            quality = quality if quality in (360, 480, 720, 1080) else 720
            episodes = sorted(anime.get("episodes", []), key=lambda e: e["n"])
            role = "next" if data.get("prefetch") is True else "current"
            target = next((e for e in episodes if e["n"] > ep), None) if role == "next" else next((e for e in episodes if e["n"] == ep), None)
            if not target or not target.get("url"):
                self.send_json({"ok": False, "error": "Hazırlanacak bölüm bağlantısı yok"}, 404)
                return
            url, number, ref = target["url"], target["n"], anime.get("sourcePage") or "https://www.tranimeizle.live/"
        try:
            entry = RAM.prepare("%s:%d:%d" % (aid, number, quality), url, ref, quality,
                                role, "%s:%d:%d" % (aid, ep, quality), retry=data.get("retry") is True)
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, 409)
            return
        self.send_json({"ok": True, "entry": entry, "ep": number})

    def serve_ram(self, path):
        parts = path.split("/")
        asset = RAM.asset(parts[2], parts[3]) if len(parts) == 4 else None
        if not asset:
            self.send_json({"ok": False, "error": "RAM kaydı bulunamadı; bölümü yeniden hazırla"}, 404)
            return
        body, mime = asset
        try:
            selected = byte_range(self.headers.get("Range"), len(body))
        except ValueError:
            self.send_response(416)
            self.send_header("Content-Range", "bytes */%d" % len(body))
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        start, end = selected if selected else (0, len(body) - 1)
        self.send_response(206 if selected else 200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("X-Kino-Source", "RAM")
        if selected:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(memoryview(body)[start:end + 1])

    # ---- api kolları
    def api_import(self, data):
        text = (data.get("text") or "").strip()
        title = (data.get("title") or "").strip()
        guess, items, numbered = parse_import(text)
        if not title:
            title = guess or ""
        if not title:
            self.send_json({"ok": False, "error": "Anime adı gerekli"}, 400)
            return
        if not items:
            self.send_json({"ok": False,
                            "error": "Metinde m3u8 linki bulunamadı"}, 400)
            return
        anime, added = merge_import(title, items)
        # meta tazele (ilk sefer ya da auto degilse)
        meta_done = False
        if not anime.get("meta", {}).get("poster"):
            try:
                meta = anilist_lookup(title)
                if meta:
                    with LOCK:
                        anime["meta"] = meta
                        meta_done = True
            except Exception:
                pass
            save_db()
        self.send_json({"ok": True, "animeId": anime["id"], "added": added,
                        "total": len(anime["episodes"]),
                        "metaFetched": meta_done})
        # arka planda CDN yine de tazelensin
        if not meta_done:
            threading.Thread(target=self._bg_meta, args=(anime["id"],),
                             daemon=True).start()

    def _bg_meta(self, anime_id):
        try:
            with LOCK:
                anime = next((a for a in DB["animes"] if a["id"] == anime_id), None)
                t = anime["title"] if anime else None
            if t:
                meta = anilist_lookup(t)
                if meta:
                    with LOCK:
                        anime = next((a for a in DB["animes"] if a["id"] == anime_id), None)
                        if anime:
                            anime["meta"] = meta
                            save_db()
        except Exception:
            pass

    def api_add(self, data):
        media = data.get("media") or data or {}
        title = (media.get("title") or data.get("title") or "").strip()
        if not title:
            self.send_json({"ok": False, "error": "Anime adı gerekli"}, 400)
            return
        aid = slugify(title)
        fetch_episodes = data.get("fetchEpisodes", True) is not False
        mid = media.get("anilistId") or media.get("id")
        with LOCK:
            anime = next((a for a in DB["animes"] if mid and
                          str((a.get("meta") or {}).get("anilistId")) == str(mid)), None) or find_anime(aid)
            if anime:
                aid = anime["id"]
            existed = anime is not None
            batch = int(DB["settings"].get("batch") or BATCH)
        meta = {
            "anilistId": media.get("anilistId") or media.get("id"),
            "displayTitle": title,
            "poster": media.get("poster") or media.get("coverImage"),
            "banner": media.get("banner") or media.get("bannerImage"),
            "outline": media.get("outline") or media.get("description") or "",
            "year": media.get("year") or media.get("seasonYear"),
            "score": media.get("score") or media.get("averageScore"),
            "genres": media.get("genres") or [],
            "episodes": media.get("episodes"),
            "format": media.get("format"),
            "status": media.get("status"),
            "nextAiring": media.get("nextAiring"),
            "latestAired": media.get("latestAired"),
            "fetchedAt": int(time.time()),
        }
        search_titles = [t for t in dict.fromkeys(
            [media.get("english"), media.get("romaji"), title]) if t]
        if not existed:
            new_anime = {"id": aid, "title": title, "created": int(time.time()),
                         "episodes": [], "meta": meta,
                         "searchTitles": search_titles,
                         "autoFetch": {"enabled": fetch_episodes, "batch": batch, "nextAt": None}}
            with LOCK:
                dup = next((a for a in DB["animes"] if mid and
                            str((a.get("meta") or {}).get("anilistId")) == str(mid)), None) or find_anime(aid)
                if dup:
                    existed = True
                    anime = dup
                    aid = dup["id"]
                else:
                    anime = new_anime
                    DB["animes"].append(anime)
                    save_db()
        else:
            with LOCK:
                old = anime.setdefault("meta", {})
                for k, v in meta.items():
                    if v:
                        old[k] = v
                anime["searchTitles"] = search_titles or anime.get("searchTitles")
                af = anime.setdefault("autoFetch", {"enabled": True, "batch": batch})
                if fetch_episodes:
                    af["enabled"] = True
                af["batch"] = batch
                save_db()
        with LOCK:
            entry = DB["lists"].setdefault(aid, {})
            entry["tracking"] = True
            entry["updated"] = int(time.time())
            if not fetch_episodes and not entry.get("status"):
                entry["status"] = "planned"
            save_db()
        queued = enqueue_fetch(aid, batch, None) if fetch_episodes else False
        with LOCK:
            anime = find_anime(aid)
            payload = {"ok": True, "animeId": aid, "existed": existed,
                       "queued": queued,
                       "fetch": json.loads(json.dumps(anime.get("fetch") or {})),
                       "episodes": len(anime.get("episodes") or [])}
        self.send_json(payload)

    def api_anime_fetch(self, data):
        aid = data.get("animeId")
        with LOCK:
            default_count = int(DB["settings"].get("batch") or BATCH)
        count = int(data.get("count") or default_count)
        with LOCK:
            anime = find_anime(aid)
            if not anime:
                self.send_json({"ok": False, "error": "anime yok"}, 404)
                return
            anime.setdefault("autoFetch", {"enabled": True, "batch": BATCH})["enabled"] = True
            save_db()
        queued = enqueue_fetch(aid, count, None, reason="manual")
        self.send_json({"ok": True, "queued": queued})

    def api_ep_open(self, data):
        """Player bir bolumu actiginda: esik bolumse sonraki 10'u tetikle."""
        aid = data.get("animeId")
        ep = data.get("ep")
        with LOCK:
            anime = find_anime(aid)
        if not anime:
            self.send_json({"ok": False, "error": "anime yok"}, 404)
            return
        queued = maybe_autofetch(anime, ep)
        with LOCK:
            anime = find_anime(aid)
            f = json.loads(json.dumps(anime.get("fetch") or {}))
        self.send_json({"ok": True, "queued": queued, "fetch": f})

    def api_list(self, data):
        aid = data.get("animeId")
        with LOCK:
            if not find_anime(aid):
                self.send_json({"ok": False, "error": "anime yok"}, 404)
                return
            entry = DB["lists"].setdefault(aid, {})
            if "status" in data:
                st = data.get("status") or None
                if st:
                    entry["status"] = st
                else:
                    entry.pop("status", None)
            if "favorite" in data:
                entry["favorite"] = bool(data["favorite"])
            if "tracking" in data:
                entry["tracking"] = bool(data["tracking"])
            if "rating" in data:
                try:
                    r = int(data["rating"])
                except Exception:
                    r = 0
                entry["rating"] = max(0, min(10, r)) or None
            entry["updated"] = int(time.time())
            if "tracking" not in entry and not any(entry.get(k) for k in ("status", "favorite", "rating")):
                DB["lists"].pop(aid, None)
                entry = {}
            save_db()
        self.send_json({"ok": True, "entry": entry})

    def api_tracking_progress(self, data):
        aid = data.get("animeId")
        try:
            ep = data["episode"]
            if type(ep) is not int or not 1 <= ep <= 100000 or type(data.get("done")) is not bool:
                raise ValueError()
        except (KeyError, ValueError):
            self.send_json({"ok": False, "error": "Geçerli bölüm ve done (true/false) gerekli"}, 400)
            return
        with LOCK:
            if not find_anime(aid):
                self.send_json({"ok": False, "error": "Anime bulunamadı"}, 404)
                return
            p = DB["progress"].setdefault("%s:%d" % (aid, ep), {"pos": 0, "dur": 0})
            p.update({"done": data["done"], "updated": int(time.time())})
            save_db()
        self.send_json({"ok": True})

    def api_settings(self, data):
        with LOCK:
            changed = {}
            for k, v in (data or {}).items():
                if k not in DEFAULT_SETTINGS:
                    continue
                if k == "batch":
                    try:
                        v = max(1, min(50, int(v)))
                    except (TypeError, ValueError):
                        continue
                if k == "ramPlayback" and type(v) is not bool:
                    continue
                if k == "ramQuality" and (type(v) is not int or v not in (360, 480, 720, 1080)):
                    continue
                DB["settings"][k] = v
                changed[k] = v
            save_db()
            settings = dict(DB["settings"])
        self.send_json({"ok": True, "settings": settings, "changed": changed})

    def api_ep_refresh(self, data):
        """Tek bir bolumun linkini yeniden cek (START=ep-1, N=1)."""
        aid = data.get("animeId")
        refresh_all = bool(data.get("all"))
        if refresh_all:
            with LOCK:
                a = find_anime(aid)
                if not a:
                    self.send_json({"ok": False, "error": "anime yok"}, 404)
                    return
                if (a.get("fetch") or {}).get("status") in ("queued", "running"):
                    self.send_json({"ok": False, "error": "zaten çekim var"}, 409)
                    return
                total = len(a.get("episodes") or [])
                if not total:
                    self.send_json({"ok": False, "error": "hiç bölüm yok"}, 400)
                    return
                set_fetch(aid, status="queued", message="Tüm linkler yenilenecek…",
                          requested=total, got=0,
                          titles=a.get("searchTitles") or [a.get("title")])
                titles = a.get("searchTitles") or [a.get("title")]
            JOB_Q.put({"animeId": aid, "count": total, "start": 0,
                       "titles": titles, "reason": "refresh-all"})
            self.send_json({"ok": True, "queued": True})
            return
        try:
            ep = int(data.get("ep"))
        except Exception:
            self.send_json({"ok": False, "error": "ep gerekli"}, 400)
            return
        with LOCK:
            a = find_anime(aid)
            if not a:
                self.send_json({"ok": False, "error": "anime yok"}, 404)
                return
            if (a.get("fetch") or {}).get("status") in ("queued", "running"):
                self.send_json({"ok": False, "error": "zaten çekim var"}, 409)
                return
            set_fetch(aid, status="queued", message="Bölüm %d yenilenecek…" % ep,
                      requested=1, got=0,
                      titles=a.get("searchTitles") or [a.get("title")])
        JOB_Q.put({"animeId": aid, "count": 1, "start": max(0, ep - 1),
                   "titles": a.get("searchTitles") or [a.get("title")],
                   "reason": "refresh:%d" % ep})
        self.send_json({"ok": True, "queued": True})

    def api_progress(self, data):
        anime_id = data.get("animeId")
        ep = data.get("ep")
        if not anime_id or ep is None:
            self.send_json({"ok": False, "error": "animeId ve ep gerekli"}, 400)
            return
        try:
            pos = round(float(data.get("pos") or 0), 2)
            dur = round(float(data.get("dur") or 0), 2)
        except (TypeError, ValueError):
            self.send_json({"ok": False, "error": "pos/dur sayısal olmalı"}, 400)
            return
        with LOCK:
            DB["progress"]["%s:%s" % (anime_id, ep)] = {
                "pos": pos,
                "dur": dur,
                "done": bool(data.get("done") or False),
                "updated": int(time.time()),
            }
            # izleme gecmisi (istatistik/aktivite icin, seyrek kayit)
            if pos >= 60:
                hist = DB["history"]
                last = hist[-1] if hist else None
                if (not last or last.get("animeId") != anime_id
                        or last.get("ep") != ep
                        or time.time() - last.get("at", 0) > 600):
                    hist.append({"animeId": anime_id, "ep": ep,
                                 "at": int(time.time()), "pos": pos})
                    if len(hist) > 1000:
                        del hist[:-1000]
            save_db()
        self.send_json({"ok": True})
        # 9. bolume gecildiyse sonraki 10'u arka planda cek
        try:
            with LOCK:
                anime = find_anime(anime_id)
            maybe_autofetch(anime, ep)
        except Exception:
            pass

    def api_lookup(self, data):
        anime_id = data.get("animeId")
        query = (data.get("query") or "").strip()
        with LOCK:
            anime = next((a for a in DB["animes"] if a["id"] == anime_id), None)
            if not anime:
                self.send_json({"ok": False, "error": "anime yok"}, 404)
                return
            if not query:
                query = anime["title"]
        try:
            meta = anilist_lookup(query)
        except Exception as e:
            self.send_json({"ok": False, "error": str(e)}, 502)
            return
        if meta:
            with LOCK:
                anime = next((a for a in DB["animes"]
                              if a["id"] == anime_id), None)
                if anime:
                    anime["meta"] = meta
                    save_db()
            self.send_json({"ok": True, "meta": meta})
        else:
            self.send_json({"ok": False, "error": "AniList'te bulunamadı"}, 404)

    def api_anime_delete(self, data):
        anime_id = data.get("animeId")
        if anime_id:
            cancel_job(anime_id)  # aktif cekim varsa durdur; yok kalan proc veri yazmasin
        with LOCK:
            DB["animes"] = [a for a in DB["animes"] if a["id"] != anime_id]
            for k in [k for k in DB["progress"] if k.startswith(anime_id + ":")]:
                DB["progress"].pop(k)
            DB["lists"].pop(anime_id, None)
            DB["history"] = [h for h in DB["history"] if h.get("animeId") != anime_id]
            save_db()
        self.send_json({"ok": True})

    def api_ep_reset(self, data):
        anime_id = data.get("animeId")
        ep = data.get("ep")
        with LOCK:
            DB["progress"].pop("%s:%s" % (anime_id, ep), None)
            save_db()
        self.send_json({"ok": True})

    # ---- HLS proxy
    def proxy_get(self, parsed):
        q = urllib.parse.parse_qs(parsed.query)
        u = (q.get("u") or [""])[0]
        ref = (q.get("ref") or [""])[0]
        if not u or not re.match(r"^https?://", u, re.I):
            self.send_error(400, "bad proxy url")
            return
        if not px_allowed(u):
            self.send_error(403, "proxy hedefe erisemez")
            return
        headers = {}
        rng = self.headers.get("Range")
        if rng:
            headers["Range"] = rng
        if ref:
            headers["Referer"] = ref
        try:
            resp = fetch_upstream(u, headers, timeout=30)
        except urllib.error.HTTPError as he:
            if he.code == 416:
                self.send_response(416)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_error(502, "upstream %s" % he.code)
            return
        except Exception:
            self.send_error(502, "upstream hatasi")
            return
        with resp:
            final = resp.geturl() or u
            if not px_allowed(final):  # yonlendirilen hedef de yerel olamaz
                self.send_error(403, "proxy hedefe erisemez")
                return
            ctype = resp.headers.get("Content-Type", "")
            is_pl = ("mpegurl" in ctype.lower()) or final.split("?")[0].lower().endswith(
                (".m3u8", ".m3u"))
            if is_pl:
                text = resp.read().decode("utf-8", "replace")
                body = rewrite_playlist(text, final).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)
                return
            # binary (segment / key / vtt)
            cl = resp.headers.get("Content-Length")
            self.send_response(resp.status)
            ct = guess_content_type(final, ctype)
            self.send_header("Content-Type", ct)
            for h in ("Content-Range", "Accept-Ranges"):
                if resp.headers.get(h):
                    self.send_header(h, resp.headers[h])
            if cl and not resp.headers.get("Accept-Ranges"):
                self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-store")
            if self.command == "HEAD":
                if cl:
                    self.send_header("Content-Length", cl)
                self.end_headers()
                return
            if cl:
                # bilinen uzunluk: dogrudan aktar
                self.send_header("Content-Length", cl)
                self.end_headers()
                remaining = int(cl)
                try:
                    while remaining > 0:
                        chunk = resp.read(min(65536, remaining))
                        if not chunk:
                            self.close_connection = True  # upstream erken kesti
                            break
                        remaining -= len(chunk)
                        self.wfile.write(chunk)
                except Exception:
                    self.close_connection = True  # aktarim yarisinda kesildi
                    return
            else:
                # uzunluk yok: buffer'la, Content-Length ile gonder
                buf = resp.read()
                self.send_header("Content-Length", str(len(buf)))
                self.end_headers()
                self.wfile.write(buf)


def reset_stale_fetches():
    """Onceki calismadan yarida kalan 'running/queued' isleri hata olarak isaretle."""
    changed = False
    with LOCK:
        for a in DB["animes"]:
            f = a.get("fetch") or {}
            if f.get("status") in ("queued", "running"):
                f.update(status="error", message="Sunucu yeniden başladı, çekim yarıda kaldı",
                         error="Sunucu yeniden başladı, çekim yarıda kaldı",
                         updated=int(time.time()))
                a["fetch"] = f
                changed = True
    if changed:
        save_db()


def main():
    load_db()
    reset_stale_fetches()
    threading.Thread(target=job_worker, daemon=True).start()
    RAM.start_reaper()
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print("Kino calisiyor  ->  http://localhost:%d  (root: %s)" % (PORT, ROOT), flush=True)
    print("Veri: %s | Cekici: %s" % (DATA_FILE, FETCHER), flush=True)
    try:
        PID_FILE.write_text(str(os.getpid()))
    except OSError:
        pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if PID_FILE.read_text().strip() == str(os.getpid()):
                PID_FILE.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()
