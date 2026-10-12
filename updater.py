"""Updates from GitHub releases: a check at start and once a day (one call to GitHub's API, nothing about you sent),
then, if you say so, download the new installer, run it quietly, and come back on the new version.
An installed copy updates itself; a source checkout (git) is pointed at the release page instead. Off: "checkUpdates": false."""
import json, os, re, subprocess, sys, tempfile, threading, time, urllib.request
import config

REPO = 'FindlayHi/lorekeeper'
API = f'https://api.github.com/repos/{REPO}/releases/latest'
PAGE = f'https://github.com/{REPO}/releases/latest'
ASSET = 'Lorekeeper-Setup.exe'
DAY = 24 * 3600


def parse(v):
    """'v0.1.10' -> (0, 1, 10); anything odd sorts as oldest."""
    m = re.match(r'v?(\d+)\.(\d+)\.(\d+)', v or '')
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def newer(latest, current):
    return parse(latest) > parse(current)


def installed():
    """The installer's copy (PyInstaller), which can update itself; a source checkout can't."""
    return bool(getattr(sys, 'frozen', False))


def latest():
    """(version, installer url, notes url) of the newest GitHub release, or None."""
    req = urllib.request.Request(API, headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'Lorekeeper-updater'})
    with urllib.request.urlopen(req, timeout=15) as r:
        j = json.load(r)
    url = next((a['browser_download_url'] for a in j.get('assets', []) if a['name'] == ASSET), None)
    return j.get('tag_name', '').lstrip('v'), url, j.get('html_url', PAGE)


def download(url, progress=lambda done, total: None):
    """The installer to a temp file -> its path."""
    path = os.path.join(tempfile.gettempdir(), ASSET)
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Lorekeeper-updater'}), timeout=60) as r, \
            open(path + '.part', 'wb') as out:
        total, got = int(r.headers.get('Content-Length') or 0), 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            got += len(chunk)
            progress(got, total)
    os.replace(path + '.part', path)
    return path


def install(path):
    """Run the installer quietly; it closes this app, installs, and starts the new one (/AUTOSTART=1)."""
    subprocess.Popen([path, '/SILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/AUTOSTART=1'], close_fds=True)


class Updater:
    """Watches for releases in the background. .available = (version, url, page) once one is newer than ours."""

    def __init__(self, current, cfg, on_found=lambda v: None):
        self.current, self.cfg, self.on_found = current, cfg, on_found
        self.available, self.told = None, None

    def start(self):
        def loop():
            time.sleep(20)   # let the app settle first
            while True:
                if self.cfg.get('checkUpdates', True):
                    self.check()
                time.sleep(DAY)
        threading.Thread(target=loop, daemon=True).start()

    def check(self):
        try:
            v, url, page = latest()
        except Exception as e:
            print('update check:', e)
            return None
        if newer(v, self.current):
            self.available = (v, url, page)
            if self.told != v:
                self.told = v
                self.on_found(v)
        return self.available

    def update(self, box):
        """Download and install, or for a source checkout open the release page."""
        if not self.available:
            return
        v, url, page = self.available
        if not installed() or not url:
            os.startfile(page)
            return

        def run():
            box.show('Updating Lorekeeper', f'Downloading {v}…', stay=True, title=True)
            last = [-1]

            def progress(done, total):
                pct = int(done * 100 / total) if total else 0
                if pct >= last[0] + 10:
                    last[0] = pct
                    box.show('Updating Lorekeeper', f'Downloading {v}: {pct}%', stay=True, title=True)
            try:
                path = download(url, progress)
            except Exception as e:
                return box.show('Update failed', f"Couldn't download it ({e}). Try again from the tray later.", title=True)
            box.show('Updating Lorekeeper', f'Installing {v}. Lorekeeper restarts in a moment.', stay=True, title=True)
            install(path)
        threading.Thread(target=run, daemon=True).start()
