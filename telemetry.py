"""Anonymous usage counts: how many installs, and how many are used each day. Nothing about play ever leaves.

Sent, to PostHog: a random install id (made here, tied to nothing), the event ("installed" once, "active" at most once a
day), the app version and commit, the Windows version, and whether listen mode / RomM are on and which voice engine.
Never: games, questions, answers, notes, paths, names, hardware. Off: tray → "Share anonymous usage counts",
"telemetry": false in config.json, or the DO_NOT_TRACK environment variable. With no posthogKey nothing is sent at all.
"""
import json, os, platform, threading, time, urllib.request, uuid
import config

VERSION = '0.1'
FILE = os.path.join(config.DIR, 'telemetry.json')   # {"id", "active": last day counted, "noticed"}
FIRST_WAIT = 300          # first run: nothing is sent for 5 minutes, so the notice can be read and acted on
EVERY = 3 * 3600          # a tray app runs for days: check the day this often
NOTICE = ('Lorekeeper counts installs anonymously: a random id, the app and Windows version, and which features are on. '
          'Never your games, questions or answers. Turn it off in the tray: "Share anonymous usage counts".')


def allowed(cfg):
    dnt = os.environ.get('DO_NOT_TRACK', '').strip()   # the cross-tool opt-out (consoledonottrack.com)
    return bool(cfg.get('telemetry') and cfg.get('posthogKey')) and dnt in ('', '0')


def _load():
    try:
        with open(FILE, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save(st):
    os.makedirs(config.DIR, exist_ok=True)
    with open(FILE, 'w', encoding='utf-8') as f:
        json.dump(st, f)


def notice(cfg):
    """The one-time disclosure, or '' once it has been shown (or when nothing would be sent anyway)."""
    if not allowed(cfg):
        return ''
    st = _load()
    if st.get('noticed'):
        return ''
    st['noticed'] = True
    _save(st)
    return NOTICE


def _commit(root=os.path.dirname(os.path.abspath(__file__))):
    git = os.path.join(root, '.git')
    try:
        if os.path.isfile(git):   # a worktree: ".git" names the real folder
            git = open(git, encoding='utf-8').read().split('gitdir:', 1)[1].strip()
        head = open(os.path.join(git, 'HEAD'), encoding='utf-8').read().strip()
        if not head.startswith('ref: '):
            return head[:7]
        ref = head[5:]
        if os.path.exists(os.path.join(git, 'commondir')):
            git = os.path.join(git, open(os.path.join(git, 'commondir'), encoding='utf-8').read().strip())
        if os.path.exists(os.path.join(git, ref)):
            return open(os.path.join(git, ref), encoding='utf-8').read().strip()[:7]
        for line in open(os.path.join(git, 'packed-refs'), encoding='utf-8'):
            if line.rstrip().endswith(' ' + ref):
                return line[:7]
    except (OSError, IndexError):
        pass
    return ''


def _windows():
    try:
        build = int(platform.version().split('.')[2])
    except (IndexError, ValueError):
        return platform.system() or 'unknown', ''
    return ('Windows 11' if build >= 22000 else 'Windows 10'), str(build)


def props(cfg):
    """Everything an event carries besides its name and the install id. Keep this list in step with the README."""
    os_name, build = _windows()
    return {'version': VERSION, 'commit': _commit(), 'os': os_name, 'os_build': build,
            'listen': bool(cfg.get('listen')), 'romm': bool(cfg.get('rommUrl')), 'voice': cfg.get('voice') or '',
            '$process_person_profile': False, '$geoip_disable': True, '$lib': 'lorekeeper'}


def send(cfg, event, distinct_id, properties):
    """One event to PostHog's capture API. Quick, and silent on any failure."""
    body = json.dumps({'api_key': cfg['posthogKey'], 'event': event, 'distinct_id': distinct_id, 'properties': properties}).encode()
    req = urllib.request.Request(cfg.get('posthogHost', config.DEFAULTS['posthogHost']).rstrip('/') + '/i/v0/e/', body,
                                 {'Content-Type': 'application/json', 'User-Agent': 'lorekeeper'})
    try:
        urllib.request.urlopen(req, timeout=5).close()
    except Exception:
        pass


def ping(cfg, sender=None):
    """"installed" the first time, "active" once a day. Returns the events sent (for tests)."""
    if not allowed(cfg):
        return []
    st, today, events = _load(), time.strftime('%Y-%m-%d'), []
    if not st.get('id'):
        st['id'] = uuid.uuid4().hex
        events.append('installed')
    if st.get('active') != today:
        st['active'] = today
        events.append('active')
    if not events:
        return []
    _save(st)   # before sending: a failed send loses that day's count, it never repeats it
    p = props(cfg)
    for e in events:
        (sender or send)(cfg, e, st['id'], p)
    return events


def start(cfg, wait=0):
    """In the background: wait (first run), then count today and each new day while the app runs. Reads cfg live,
    so unticking the tray box stops it from the next check."""
    def run():
        time.sleep(wait)
        while True:
            try:
                ping(cfg)
            except Exception:
                pass
            time.sleep(EVERY)
    threading.Thread(target=run, daemon=True).start()
