"""Which game is in front: the foreground exe matched against the games Steam, Epic and GOG installed.

The index is [{name, id, source, dir}], cached in games.json and rebuilt when an exe matches nothing
(a game installed since). A pinned game (tray menu, or "I'm playing X") wins until the exe in front changes.
"""
import difflib, glob, json, os, re, sys, time
import config, romm, win

INDEX = os.path.join(config.DIR, 'games.json')
_missed = set()   # exes that matched nothing even after a rescan
PIN = os.path.join(config.DIR, 'pinned.json')
NOT_GAMES = re.compile(r'redistributable|runtime|steamvr|proton|dedicated server|soundtrack|\bsdk\b|benchmark|3dmark|wallpaper engine', re.I)
LAUNCHERS = re.compile(r'\\(steam|steamwebhelper|epicgameslauncher|galaxyclient|explorer|lorekeeper|python|pythonw|windowsterminal|chrome|msedge|firefox|discord)\.exe$', re.I)


def vdf(text):
    """Valve's KeyValues text (libraryfolders.vdf, appmanifest_*.acf) -> nested dicts."""
    root, stack, key = {}, [], None
    cur = root
    for tok in re.findall(r'"((?:[^"\\]|\\.)*)"|([{}])', text):
        s, brace = tok
        if brace == '{':
            new = {}
            cur[key] = new
            stack.append(cur)
            cur, key = new, None
        elif brace == '}':
            cur = stack.pop() if stack else root
        elif key is None:
            key = s
        else:
            cur[key] = s.replace('\\\\', '\\')
            key = None
    return root


def _reg(root, path, name):
    try:
        import winreg
        with winreg.OpenKey(root, path) as k:
            return winreg.QueryValueEx(k, name)[0]
    except (OSError, ImportError):
        return ''


def steam_dir():
    if sys.platform == 'win32':
        import winreg
        d = _reg(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam', 'SteamPath')
        if d and os.path.isdir(d):
            return os.path.normpath(d)
    d = os.path.join(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'), 'Steam')
    return d if os.path.isdir(d) else ''


def steam_games(steam=None):
    steam = steam if steam is not None else steam_dir()
    if not steam:
        return []
    libs = {steam}
    try:
        with open(os.path.join(steam, 'steamapps', 'libraryfolders.vdf'), encoding='utf-8') as f:
            libs |= {v['path'] for v in vdf(f.read()).get('libraryfolders', {}).values() if isinstance(v, dict) and v.get('path')}
    except OSError:
        pass
    out = []
    for lib in {os.path.normcase(os.path.normpath(l)): l for l in sorted(libs)}.values():   # registry path is lower-case, the vdf's is not
        for acf in glob.glob(os.path.join(lib, 'steamapps', 'appmanifest_*.acf')):
            try:
                with open(acf, encoding='utf-8') as f:
                    a = vdf(f.read()).get('AppState', {})
            except OSError:
                continue
            if a.get('name') and a.get('installdir') and not NOT_GAMES.search(a['name']):
                out.append({'name': a['name'], 'id': a.get('appid', ''), 'source': 'steam',
                            'dir': os.path.join(lib, 'steamapps', 'common', a['installdir'])})
    return out


def epic_games(manifests=None):
    manifests = manifests or os.path.join(os.environ.get('ProgramData', r'C:\ProgramData'), 'Epic', 'EpicGamesLauncher', 'Data', 'Manifests')
    out = []
    for item in glob.glob(os.path.join(manifests, '*.item')):
        try:
            with open(item, encoding='utf-8') as f:
                m = json.load(f)
        except (OSError, ValueError):
            continue
        if m.get('DisplayName') and m.get('InstallLocation') and 'games' in [c.lower() for c in m.get('AppCategories', ['games'])]:
            out.append({'name': m['DisplayName'], 'id': m.get('AppName', ''), 'source': 'epic', 'dir': m['InstallLocation']})
    return out


def gog_games():
    if sys.platform != 'win32':
        return []
    import winreg
    out = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\GOG.com\Games') as k:
            for i in range(winreg.QueryInfoKey(k)[0]):
                gid = winreg.EnumKey(k, i)
                sub = r'SOFTWARE\WOW6432Node\GOG.com\Games' + '\\' + gid
                name, path = _reg(winreg.HKEY_LOCAL_MACHINE, sub, 'gameName'), _reg(winreg.HKEY_LOCAL_MACHINE, sub, 'path')
                if name and path:
                    out.append({'name': name, 'id': gid, 'source': 'gog', 'dir': path})
    except OSError:
        pass
    return out


def build():
    games = steam_games() + epic_games() + gog_games()
    os.makedirs(config.DIR, exist_ok=True)
    with open(INDEX, 'w', encoding='utf-8') as f:
        json.dump(games, f, indent=1)
    return games


def index():
    try:
        with open(INDEX, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return build()


def _under(path, d):
    path, d = os.path.normcase(os.path.normpath(path)), os.path.normcase(os.path.normpath(d))
    return path.startswith(d + os.sep)


def key(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def match(exe, title, games):
    """The game that exe belongs to (deepest install folder wins), else one whose name is in the window title."""
    if exe:
        hits = [g for g in games if _under(exe, g['dir'])]
        if hits:
            return max(hits, key=lambda g: len(g['dir']))
    t = key(title)
    named = [g for g in games if len(key(g['name'])) >= 4 and key(g['name']) in t]
    return max(named, key=lambda g: len(g['name'])) if named else None


def find(words, games):
    """The installed game the user named ("I'm playing elden ring"), else a made-up entry with their words."""
    k = key(words)
    if not k:
        return None
    exact = [g for g in games if key(g['name']) == k]
    part = [g for g in games if k in key(g['name']) or key(g['name']) in k]
    close = difflib.get_close_matches(k, [key(g['name']) for g in games], n=1, cutoff=0.75)
    hit = (exact or part or [g for g in games if close and key(g['name']) == close[0]] or [None])[0]
    return hit or {'name': ' '.join(w.capitalize() if w.islower() else w for w in words.split()), 'id': '', 'source': 'named', 'dir': ''}


def pin(game, exe=''):
    """Stick to this game until the exe in front changes (exe='': until unpinned)."""
    os.makedirs(config.DIR, exist_ok=True)
    with open(PIN, 'w', encoding='utf-8') as f:
        json.dump({'game': game, 'exe': exe, 'at': time.time()}, f)


def unpin():
    try:
        os.remove(PIN)
    except OSError:
        pass


def pinned():
    try:
        with open(PIN, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def current(exe=None, title=None):
    """(game or None, exe in front). Pinned game first, then the index, rebuilt once if a non-launcher exe misses."""
    if exe is None:
        exe, title = win.front()
    p = pinned()
    if p and (not p['exe'] or not exe or LAUNCHERS.search(exe) or os.path.normcase(p['exe']) == os.path.normcase(exe)):
        return p['game'], exe   # alt-tabbed to Discord or a browser: still that game
    if p:
        unpin()   # a different game is in front now
    games = index()
    g = match(exe, title or '', games)
    if not g and exe and not LAUNCHERS.search(exe) and not romm.EMULATORS.search(exe) and exe not in _missed:
        _missed.add(exe)   # a game installed since the index was built? rescan once per app, not every few seconds
        g = match(exe, title or '', build())
    if not g:
        g = romm.current(exe, title)   # an emulator or the RomM web player: RomM knows the game
    if not g and exe and romm.EMULATORS.search(exe):   # no RomM: the emulator's window title names the game
        names = romm.clean_title(title or '')
        if names:
            g = {'name': names[0], 'id': '', 'source': 'emulator', 'dir': ''}
    return g, exe
