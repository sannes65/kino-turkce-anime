"""Kino icin tarayici bulma/baslatma (Windows, WSL, macOS, Linux).

Bolum cekimi Chrome DevTools Protocol (CDP) ile calisir. Bu modul makineye
ozel her seyi tek yerde tutar: Chromium tabanli tarayicinin yolu, ayri profil
klasoru ve makineye ozel (Drive'a senkronlanmamasi gereken) yerel klasor.
"""
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

CDP_PORT = int(os.environ.get("KINO_CDP_PORT", "9222"))
CDP_URL = (os.environ.get("KINO_CDP_URL") or os.environ.get("BU_CDP_URL")
           or "http://127.0.0.1:%d" % CDP_PORT)


def is_wsl():
    if not sys.platform.startswith("linux"):
        return False
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


def local_dir():
    """Makineye ozel klasor (pid, tarayici profili). Drive'da DEGIL."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    d = base / "Kino"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _win_candidates(drive_root, local_appdata=None):
    rel = [
        "Google/Chrome/Application/chrome.exe",
        "Microsoft/Edge/Application/msedge.exe",
        "BraveSoftware/Brave-Browser/Application/brave.exe",
    ]
    bases = [drive_root + "/Program Files", drive_root + "/Program Files (x86)"]
    if local_appdata:
        bases.append(local_appdata)
    return [b + "/" + r for r in rel for b in bases]


def browser_candidates():
    if sys.platform == "win32":
        la = (os.environ.get("LOCALAPPDATA") or "").replace("\\", "/")
        return _win_candidates("C:", la)
    if sys.platform == "darwin":
        return [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
    out = []
    if is_wsl():
        # mirrored ag modunda Windows tarayicisinin 127.0.0.1:9222'si WSL'den gorunur
        user = os.environ.get("KINO_WIN_USER") or ""
        if not user:
            try:
                user = subprocess.run(["cmd.exe", "/c", "echo %USERNAME%"],
                                      capture_output=True, text=True, timeout=5,
                                      cwd="/mnt/c").stdout.strip()
            except Exception:
                user = ""
        la = "/mnt/c/Users/%s/AppData/Local" % user if user else None
        out += _win_candidates("/mnt/c", la)
    for name in ("google-chrome", "google-chrome-stable", "chromium",
                 "chromium-browser", "microsoft-edge", "brave-browser"):
        p = shutil.which(name)
        if p:
            out.append(p)
    return out


def find_browser():
    env = os.environ.get("KINO_CHROME")
    if env:
        return env
    for p in browser_candidates():
        if os.path.exists(p):
            return p
    return None


def profile_dir(exe):
    """Ayri profil (CDP varsayilan profilde calismaz). Tarayicinin gordugu yol."""
    env = os.environ.get("KINO_CHROME_PROFILE")
    if env:
        return env
    if exe.startswith("/mnt/") or sys.platform == "win32":
        # Windows tarayicisi: daha once kullanilan profil varsa onu koru
        old = "/mnt/c/chrome-debug-profile" if exe.startswith("/mnt/") else "C:/chrome-debug-profile"
        if os.path.isdir(old):
            return "C:\\chrome-debug-profile"
        if sys.platform == "win32":
            return str(local_dir() / "chrome-profile")
        return "C:\\chrome-debug-profile"
    return str(local_dir() / "chrome-profile")


def cdp_up(timeout=3):
    try:
        with urllib.request.urlopen(CDP_URL + "/json/version", timeout=timeout) as r:
            return bool(r.read(64))
    except Exception:
        return False


def ensure_browser(start_url=None, wait_s=18):
    """CDP aciksa dokunma; degilse tarayiciyi ayri profille baslat. (ok, mesaj)"""
    if cdp_up():
        return True, "CDP hazir"
    exe = find_browser()
    if not exe:
        return False, ("Chrome/Edge bulunamadi. Kurun ya da KINO_CHROME ile "
                       "tarayici yolunu verin.")
    args = [exe, "--remote-debugging-port=%d" % CDP_PORT,
            "--user-data-dir=" + profile_dir(exe),
            "--no-first-run", "--no-default-browser-check"]
    if os.environ.get("KINO_CHROME_HEADLESS") == "1":
        args.append("--headless=new")
    if start_url:
        args.append(start_url)
    kw = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
          "stdin": subprocess.DEVNULL}
    if sys.platform == "win32":
        kw["creationflags"] = 0x00000008 | 0x00000200  # DETACHED | NEW_GROUP
    else:
        kw["start_new_session"] = True
    try:
        subprocess.Popen(args, **kw)
    except Exception as e:
        return False, "Tarayici baslatilamadi (%s): %s" % (exe, e)
    deadline = time.time() + wait_s
    while time.time() < deadline:
        time.sleep(0.75)
        if cdp_up():
            return True, "Tarayici acildi: %s" % exe
    return False, ("Tarayici acildi ama CDP %s yanit vermiyor. Ayni profille acik "
                   "baska bir pencere varsa kapatip tekrar deneyin." % CDP_URL)


if __name__ == "__main__":
    print("tarayici:", find_browser())
    print("profil   :", profile_dir(find_browser() or ""))
    print("yerel    :", local_dir())
    print("CDP      :", CDP_URL, "acik" if cdp_up() else "kapali")
