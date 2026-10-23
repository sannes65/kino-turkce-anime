#!/usr/bin/env python3
"""Kino baslatici (Windows / macOS / Linux / WSL).

    python start.py          # arka planda baslat (calisiyorsa dokunma) + tarayicida ac
    python start.py stop     # durdur
    python start.py status   # calisiyor mu?
    python start.py fg       # on planda calistir (loglar terminalde)
"""
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from browser import is_wsl, local_dir  # noqa: E402

PORT = int(os.environ.get("KINO_PORT", "8484"))
URL = "http://localhost:%d" % PORT
PID_FILE = local_dir() / ("server-%d.pid" % PORT)
LOG_FILE = local_dir() / "kino.log"


def running(timeout=1.5):
    try:
        with urllib.request.urlopen(URL + "/api/queue", timeout=timeout) as r:
            return "queue" in json.loads(r.read().decode("utf-8"))
    except Exception:
        return False


def read_pid():
    try:
        return int(PID_FILE.read_text().strip())
    except (OSError, ValueError):
        return None


def open_ui():
    if is_wsl():
        try:
            subprocess.run(["cmd.exe", "/c", "start", URL], cwd="/mnt/c",
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            return
        except Exception:
            pass
    webbrowser.open(URL)


def start(open_browser=True):
    if running():
        print("Kino zaten calisiyor ->", URL)
    else:
        exe = sys.executable
        kw = {"stdin": subprocess.DEVNULL, "cwd": str(ROOT)}
        if sys.platform == "win32":
            w = Path(exe).with_name("pythonw.exe")
            if w.exists():
                exe = str(w)
            kw["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000
        else:
            kw["start_new_session"] = True
        log = open(LOG_FILE, "a", encoding="utf-8")
        subprocess.Popen([exe, "-X", "utf8", str(ROOT / "server.py")],
                         stdout=log, stderr=subprocess.STDOUT, **kw)
        for _ in range(40):
            time.sleep(0.25)
            if running():
                break
        if not running():
            print("Kino baslamadi. Log:", LOG_FILE)
            try:
                print("".join(LOG_FILE.read_text(encoding="utf-8").splitlines(True)[-15:]))
            except OSError:
                pass
            return 1
        print("Kino basladi ->", URL)
    if open_browser:
        open_ui()
    return 0


def stop():
    pid = read_pid()
    if not pid:
        if running():
            print("Kino calisiyor ama bu bilgisayardaki baslaticiyla acilmamis "
                  "(ornegin WSL ya da baska bir terminal). Orada kapatin.")
            return 1
        print("Kino zaten kapali.")
        return 0
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
    for _ in range(20):
        time.sleep(0.25)
        if not running():
            break
    try:
        PID_FILE.unlink()
    except OSError:
        pass
    print("Kino durduruldu." if not running() else "Kino durmadi (PID %s)." % pid)
    return 0 if not running() else 1


def main(argv):
    cmd = (argv[1] if len(argv) > 1 else "start").lower()
    if cmd == "start":
        return start()
    if cmd == "stop":
        return stop()
    if cmd == "status":
        print("calisiyor ->" if running() else "kapali", URL if running() else "")
        return 0
    if cmd == "fg":
        os.execv(sys.executable, [sys.executable, "-X", "utf8", str(ROOT / "server.py")])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
