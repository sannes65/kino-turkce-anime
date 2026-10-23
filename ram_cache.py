"""Bounded, volatile HLS episode cache. No media is written to disk."""
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlsplit


class Cancelled(Exception):
    pass


def attrs(line):
    return dict(re.findall(r'([A-Z0-9-]+)=((?:"[^"]*")|[^,]*)', line.split(":", 1)[-1]))


def unquote(value):
    return value.strip('"')


class RamCache:
    def __init__(self, download, limit=1024 * 1024 * 1024, ttl=600, workers=3):
        self.download = download
        self.limit = limit
        self.ttl = ttl
        self.workers = workers
        self.lock = threading.RLock()
        self.entries = {}
        self.current = None
        self.used = 0

    def _drop(self, entry):
        entry["cancel"].set()
        self.used -= entry["bytes"]
        entry["bytes"] = 0
        entry["assets"].clear()
        self.entries.pop(entry["id"], None)
        if self.current == entry["id"]:
            self.current = None

    def reap(self):
        with self.lock:
            for entry in list(self.entries.values()):
                if time.monotonic() - entry["touched"] > self.ttl:
                    self._drop(entry)

    def start_reaper(self):
        def run():
            while True:
                time.sleep(30)
                self.reap()
        threading.Thread(target=run, daemon=True, name="kino-ram-reaper").start()

    def prepare(self, key, url, ref, quality=720, role="current", owner=None, retry=False):
        with self.lock:
            self.reap()
            if role == "next":
                active = self.entries.get(self.current)
                if not active or active["key"] != owner:
                    raise ValueError("Oynatılan bölüm değişti")
            entry = next((e for e in self.entries.values() if e["key"] == key and e["url"] == url), None)
            if entry and retry and entry["state"] == "error":
                self._drop(entry)
                entry = None
            if role == "current":
                for old in list(self.entries.values()):
                    if old is not entry:
                        self._drop(old)
            else:
                for old in list(self.entries.values()):
                    if old["id"] != self.current and old is not entry:
                        self._drop(old)
            if entry:
                entry["role"] = role
                entry["touched"] = time.monotonic()
                if role == "current":
                    self.current = entry["id"]
                return self._snapshot(entry)
            eid = uuid.uuid4().hex
            entry = {"id": eid, "key": key, "url": url, "ref": ref, "quality": quality,
                     "role": role, "state": "resolving", "assets": {}, "bytes": 0,
                     "done": 0, "total": 0, "duration": 0, "error": None,
                     "started": time.monotonic(), "touched": time.monotonic(), "cancel": threading.Event()}
            self.entries[eid] = entry
            if role == "current":
                self.current = eid
            threading.Thread(target=self._run, args=(entry,), daemon=True, name="kino-ram-" + role).start()
            return self._snapshot(entry)

    def _check(self, entry):
        if entry["cancel"].is_set():
            raise Cancelled()

    def _put(self, entry, name, body, mime):
        with self.lock:
            self._check(entry)
            if self.used + len(body) > self.limit:
                raise ValueError("RAM önbellek sınırına ulaşıldı. Akışla izleyebilir veya daha düşük kalite seçebilirsin.")
            entry["assets"][name] = (body, mime)
            entry["bytes"] += len(body)
            self.used += len(body)

    @staticmethod
    def _origin(url):
        parsed = urlsplit(url)
        return parsed.scheme + "://" + parsed.netloc + "/"

    def _manifest(self, entry, url, ref, plans, seen, depth=0):
        self._check(entry)
        if depth > 5:
            raise ValueError("Kaynak çok fazla iç içe yayın listesi içeriyor")
        raw, final, _ = self.download(url, ref, 2 * 1024 * 1024, entry["cancel"])
        text = raw.decode("utf-8-sig")
        if not text.lstrip().startswith("#EXTM3U"):
            raise ValueError("Bu kaynak RAM moduna uygun bir HLS yayın listesi sunmuyor")
        lines = [line.strip() for line in text.splitlines()]
        serial = entry.get("manifestSerial", 0)
        entry["manifestSerial"] = serial + 1
        name = "playlist-%d.m3u8" % serial
        variants = []
        for i, line in enumerate(lines):
            if line.startswith("#EXT-X-STREAM-INF:"):
                following = next((x for x in lines[i+1:] if x and not x.startswith("#")), None)
                if following:
                    a = attrs(line)
                    resolution = unquote(a.get("RESOLUTION", "0x0")).split("x")
                    height = int(resolution[-1]) if resolution[-1].isdigit() else 0
                    bandwidth = int(a.get("BANDWIDTH", "0"))
                    variants.append((height, bandwidth, a, urljoin(final, following)))
        if variants:
            below = [v for v in variants if v[0] <= entry["quality"]]
            chosen = max(below, key=lambda v: (v[0], v[1])) if below else min(variants, key=lambda v: (v[0], v[1]))
            height, _, a, chosen_url = chosen
            if entry["role"] == "current" or not entry.get("height"):
                entry["height"] = height
            audio_group = a.get("AUDIO")
            audio_lines = [l for l in lines if l.startswith("#EXT-X-MEDIA:")
                           and attrs(l).get("TYPE") == "AUDIO" and attrs(l).get("GROUP-ID") == audio_group]
            selected_audio = next((l for l in audio_lines if attrs(l).get("DEFAULT") == "YES"), None) or next(iter(audio_lines), None)
            audio = ""
            if selected_audio:
                def audio_uri(match):
                    path = self._manifest(entry, urljoin(final, match.group(1)), self._origin(final), plans, seen, depth + 1)
                    return 'URI="%s"' % path
                audio = re.sub(r'URI="([^"]+)"', audio_uri, selected_audio) + "\n"
            elif audio_group:
                a.pop("AUDIO", None)
            a.pop("SUBTITLES", None)
            path = self._manifest(entry, chosen_url, self._origin(final), plans, seen, depth + 1)
            # Only the selected rendition is exposed, so the player cannot escape the cache.
            result = "#EXTM3U\n#EXT-X-VERSION:7\n" + audio + "#EXT-X-STREAM-INF:" + ",".join(k + "=" + v for k, v in a.items()) + "\n" + path + "\n"
        else:
            if "#EXT-X-ENDLIST" not in lines:
                raise ValueError("Canlı veya tamamlanmamış yayın RAM'e tam bölüm olarak hazırlanamaz")
            duration = 0
            def resource(uri):
                if uri.startswith("data:"):
                    return uri
                absolute = urljoin(final, uri)
                if "{$" in absolute:
                    raise ValueError("Bu yayın listesindeki değişkenli bağlantılar RAM modunda desteklenmiyor")
                key = (absolute, self._origin(final))
                if key not in seen:
                    asset = "asset-%d" % len(seen)
                    seen[key] = asset
                    plans.append((asset, absolute, key[1]))
                return "/ram/%s/%s" % (entry["id"], seen[key])
            output = []
            for line in lines:
                if line.startswith("#EXT-X-KEY:"):
                    a = attrs(line)
                    if a.get("METHOD") not in ("NONE", "AES-128") or unquote(a.get("KEYFORMAT", "identity")) != "identity":
                        raise ValueError("Bu kaynağın şifreleme yöntemi RAM modunda desteklenmiyor")
                if line.startswith("#EXTINF:"):
                    duration += float(line.split(":", 1)[1].split(",", 1)[0])
                if line.startswith("#"):
                    line = re.sub(r'URI="([^"]+)"', lambda m: 'URI="%s"' % resource(m.group(1)), line)
                elif line:
                    line = resource(line)
                output.append(line)
            entry["duration"] = max(entry["duration"], duration)
            result = "\n".join(output) + "\n"
        self._put(entry, name, result.encode("utf-8"), "application/vnd.apple.mpegurl")
        return "/ram/%s/%s" % (entry["id"], name)

    def _run(self, entry):
        try:
            # The current episode always has priority over prefetch.
            while entry["role"] == "next":
                self._check(entry)
                with self.lock:
                    current = self.entries.get(self.current)
                    pending = current and current["state"] in ("resolving", "downloading")
                if not pending:
                    break
                entry["cancel"].wait(.25)
            plans = []
            playlist = self._manifest(entry, entry["url"], entry["ref"], plans, {})
            if not plans:
                raise ValueError("Yayın listesinde indirilecek video parçası bulunamadı")
            with self.lock:
                self._check(entry)
                entry.update(state="downloading", total=len(plans), playlist=playlist)
            def fetch(plan):
                self._check(entry)
                name, url, ref = plan
                body, _, mime = self.download(url, ref, min(32 * 1024 * 1024, self.limit), entry["cancel"])
                self._put(entry, name, body, mime)
                with self.lock:
                    entry["done"] += 1
            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                futures = [executor.submit(fetch, p) for p in plans]
                try:
                    for future in as_completed(futures):
                        future.result()
                except Exception:
                    entry["cancel"].set()
                    for future in futures:
                        future.cancel()
                    raise
            with self.lock:
                self._check(entry)
                entry["state"] = "ready"
        except Cancelled:
            with self.lock:
                if entry["id"] in self.entries:
                    self._drop(entry)
        except Exception as exc:
            with self.lock:
                if entry["id"] in self.entries:
                    self.used -= entry["bytes"]
                    entry["bytes"] = 0
                    entry["assets"].clear()
                    entry["state"] = "error"
                    entry["error"] = str(exc) if isinstance(exc, ValueError) else "Kaynak indirilemedi. Tekrar deneyebilir veya akışla izleyebilirsin."

    def _snapshot(self, entry):
        elapsed = max(.01, time.monotonic() - entry["started"])
        total, done = entry["total"], entry["done"]
        return {k: entry.get(k) for k in ("id", "key", "role", "state", "bytes", "done", "total", "height", "quality", "duration", "error")} | {
            "percent": int(done / total * 100) if total else 0,
            "elapsed": int(elapsed), "eta": round(elapsed / done * (total - done)) if done else None,
            "playlist": entry.get("playlist") if entry["state"] == "ready" else None}

    def status(self, eid=None):
        with self.lock:
            self.reap()
            entry = self.entries.get(eid)
            if entry:
                entry["touched"] = time.monotonic()
            return {"ok": True, "entry": self._snapshot(entry) if entry else None,
                    "entries": [self._snapshot(e) for e in self.entries.values()],
                    "usedBytes": self.used, "limitBytes": self.limit}

    def cancel(self, eid):
        with self.lock:
            entry = self.entries.get(eid)
            if entry:
                self._drop(entry)

    def asset(self, eid, name):
        with self.lock:
            entry = self.entries.get(eid)
            if not entry or entry["state"] != "ready":
                return None
            entry["touched"] = time.monotonic()
            return entry["assets"].get(name)


def byte_range(value, size):
    """Single HTTP byte range; None means the complete body."""
    if not value:
        return None
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", value.strip())
    if not match or not any(match.groups()) or not size:
        raise ValueError("Invalid range")
    first, last = match.groups()
    if not first:
        length = int(last)
        if not length:
            raise ValueError("Invalid suffix")
        return max(0, size - length), size - 1
    start, end = int(first), min(int(last), size - 1) if last else size - 1
    if start >= size or end < start:
        raise ValueError("Range outside resource")
    return start, end
