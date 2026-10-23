"""Bagimliliksiz Chrome DevTools Protocol istemcisi (yalniz standart kutuphane).

browser-harness'in fetcher'da kullanilan yardimcilarinin karsiligi:
cdp, js, goto_url, wait, wait_for_load, list_tabs, current_tab, new_tab,
switch_tab, activate_tab, click_at_xy, capture_screenshot.
Tek tarayici baglantisi (browser endpoint) + flatten oturumlar kullanilir.
"""
import base64
import json
import os
import socket
import struct
import threading
import time
import urllib.parse
import urllib.request

from browser import CDP_URL

CALL_TIMEOUT = float(os.environ.get("KINO_CDP_TIMEOUT", "60"))


class CDPError(RuntimeError):
    pass


class _WebSocket:
    """RFC 6455 istemcisi: metin cerceveleri, parcali mesaj, ping/pong."""

    def __init__(self, url, timeout=10):
        u = urllib.parse.urlsplit(url)
        host, port = u.hostname, u.port or 80
        path = u.path + ("?" + u.query if u.query else "")
        self.sock = socket.create_connection((host, port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = ("GET %s HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\n"
               "Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\n"
               "Sec-WebSocket-Version: 13\r\n\r\n" % (path, host, port, key))
        self.sock.sendall(req.encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise CDPError("WebSocket el sikismasi kesildi")
            head += chunk
        head, self._buf = head.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise CDPError("WebSocket reddedildi: %r" % head[:120])
        self.sock.settimeout(None)
        self._wlock = threading.Lock()

    def _read(self, n):
        while len(self._buf) < n:
            chunk = self.sock.recv(max(65536, n - len(self._buf)))
            if not chunk:
                raise EOFError("WebSocket kapandi")
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def _frame(self, opcode, payload):
        hdr = bytes([0x80 | opcode])
        n = len(payload)
        if n < 126:
            hdr += bytes([0x80 | n])
        elif n < 65536:
            hdr += bytes([0x80 | 126]) + struct.pack("!H", n)
        else:
            hdr += bytes([0x80 | 127]) + struct.pack("!Q", n)
        mask = os.urandom(4)
        body = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        with self._wlock:
            self.sock.sendall(hdr + mask + body)

    def send(self, text):
        self._frame(0x1, text.encode("utf-8"))

    def recv(self):
        parts = []
        while True:
            b0, b1 = self._read(2)
            fin, opcode = b0 & 0x80, b0 & 0x0F
            n = b1 & 0x7F
            if n == 126:
                n = struct.unpack("!H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack("!Q", self._read(8))[0]
            mask = self._read(4) if b1 & 0x80 else None
            data = self._read(n)
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if opcode == 0x8:
                raise EOFError("WebSocket kapandi")
            if opcode == 0x9:
                self._frame(0xA, data)
                continue
            if opcode == 0xA:
                continue
            parts.append(data)
            if fin:
                return b"".join(parts).decode("utf-8", "replace")

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


class Browser:
    def __init__(self, cdp_url=CDP_URL):
        with urllib.request.urlopen(cdp_url + "/json/version", timeout=10) as r:
            ws_url = json.loads(r.read().decode())["webSocketDebuggerUrl"]
        self.ws = _WebSocket(ws_url)
        self._id = 0
        self._lock = threading.Lock()
        self._pending = {}
        self._closed = False
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        try:
            while True:
                msg = json.loads(self.ws.recv())
                slot = self._pending.get(msg.get("id"))
                if slot is not None:
                    slot[1] = msg
                    slot[0].set()
        except Exception:
            self._closed = True
            for slot in list(self._pending.values()):
                slot[0].set()

    def call(self, method, params=None, session_id=None, timeout=CALL_TIMEOUT):
        if self._closed:
            raise CDPError("CDP baglantisi kapali")
        with self._lock:
            self._id += 1
            mid = self._id
        slot = [threading.Event(), None]
        self._pending[mid] = slot
        msg = {"id": mid, "method": method, "params": params or {}}
        if session_id:
            msg["sessionId"] = session_id
        try:
            self.ws.send(json.dumps(msg))
            if not slot[0].wait(timeout):
                raise TimeoutError("%s %gs icinde yanit vermedi" % (method, timeout))
        finally:
            self._pending.pop(mid, None)
        res = slot[1]
        if res is None:
            raise CDPError("CDP baglantisi koptu (%s)" % method)
        if "error" in res:
            raise CDPError("%s: %s" % (method, res["error"].get("message")))
        return res.get("result", {})

    def close(self):
        self.ws.close()


# ---------------------------------------------------------------- yardimcilar
_B = None
_SESSION = None
_TARGET = None
_BROWSER_DOMAINS = ("Target.", "Browser.", "SystemInfo.")


def connect(cdp_url=CDP_URL):
    global _B
    if _B is None or _B._closed:
        _B = Browser(cdp_url)
    return _B


def cdp(method, session_id=None, **params):
    """Ham CDP. Target.*/Browser.* tarayiciya, digerleri bagli sekmeye gider."""
    b = connect()
    if session_id is None and not method.startswith(_BROWSER_DOMAINS):
        if _SESSION is None:
            _attach_default()
        session_id = _SESSION
    return b.call(method, params, session_id=session_id)


def _attach_default():
    """Sekmeye baglanilmadan sayfa komutu gelirse ilk sekmeye (yoksa yenisine) baglan."""
    tabs = list_tabs()
    if tabs:
        switch_tab(tabs[0]["targetId"])
    else:
        new_tab()


def _evaluate(expression, session_id):
    r = connect().call("Runtime.evaluate", {
        "expression": expression, "returnByValue": True, "awaitPromise": True},
        session_id=session_id)
    if r.get("exceptionDetails"):
        d = r["exceptionDetails"]
        desc = (d.get("exception") or {}).get("description") or d.get("text")
        raise CDPError("JavaScript hatasi: %s" % desc)
    res = r.get("result", {})
    return res.get("value")


def js(expression, target_id=None):
    """Sekmede (ya da target_id verilen iframe'de) JS ifadesi calistir."""
    if not target_id:
        if _SESSION is None:
            _attach_default()
        return _evaluate(expression, _SESSION)
    sid = cdp("Target.attachToTarget", targetId=target_id, flatten=True)["sessionId"]
    try:
        return _evaluate(expression, sid)
    finally:
        try:
            cdp("Target.detachFromTarget", sessionId=sid)
        except Exception:
            pass


def list_tabs():
    return [{"targetId": t["targetId"], "title": t.get("title", ""), "url": t.get("url", "")}
            for t in cdp("Target.getTargets")["targetInfos"] if t["type"] == "page"]


def current_tab():
    info = cdp("Target.getTargetInfo", targetId=_TARGET)["targetInfo"]
    return {"targetId": info["targetId"], "title": info.get("title", ""),
            "url": info.get("url", "")}


def switch_tab(target_id):
    global _SESSION, _TARGET
    _SESSION = cdp("Target.attachToTarget", targetId=target_id, flatten=True)["sessionId"]
    _TARGET = target_id
    return _SESSION


def activate_tab(target_id):
    cdp("Target.activateTarget", targetId=target_id)
    return target_id


def new_tab(url="about:blank"):
    tid = cdp("Target.createTarget", url="about:blank")["targetId"]
    switch_tab(tid)
    if url != "about:blank":
        goto_url(url)
    return tid


def goto_url(url):
    return cdp("Page.navigate", url=url)


def wait(seconds=1.0):
    time.sleep(seconds)


def wait_for_load(timeout=15.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if js("document.readyState") == "complete":
                return True
        except Exception:
            pass  # gezinme sirasinda baglam yok olabilir
        time.sleep(0.3)
    return False


def click_at_xy(x, y):
    for t in ("mouseMoved", "mousePressed", "mouseReleased"):
        cdp("Input.dispatchMouseEvent", type=t, x=x, y=y, button="left", clickCount=1)


def capture_screenshot(path):
    data = cdp("Page.captureScreenshot", format="png")["data"]
    with open(path, "wb") as f:
        f.write(base64.b64decode(data))
    return path
