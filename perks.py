"""Perks on screen, by their icons. A model can't name a Dead by Daylight perk from its art (no text on screen),
so the four diamonds are found and matched against the wiki's icons here, offline, then named in the question.
  find:  coloured diamond with an empty edge -> a perk slot (rotate 45 deg: diamonds become squares, summed-area tables)
  match: the slot's light-grey art against every icon, normalised correlation inside the diamond (~0.9 right, <0.6 wrong)
Icons come from the game's wiki once (~6 MB, ~15 s) and are kept as one small file."""
import io, json, os, re, threading, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image, ImageFilter
import lookup

ASKS = re.compile(r'\bperks?\b|\bloadout\b|\bbuild\b', re.I)   # a question about them, screen words or not
GAMES = {'dead by daylight': {'host': 'deadbydaylight.wiki.gg', 'prefix': 'IconPerks'}}
R = 48                     # matching resolution
BLUR = ImageFilter.GaussianBlur(1.2)   # line art is thin: a pixel off would miss it
KS = (1.0, 1.1, 1.2, 1.3)  # the icon's square is a little bigger than the diamond it sits in
SURE, MARGIN = 0.88, 0.05  # a match: this good (wrong ones < 0.8), and better than the next icon (similar art: Dark Sense vs Kindred)
WIDE = 1280                # finding works at this width


def spec(game):
    return GAMES.get((game or {}).get('name', '').lower())


# icons: from the wiki, once

def _bank_path(folder, game):
    return os.path.join(folder, 'icons', re.sub(r'[^a-z0-9]+', '-', game['name'].lower()).strip('-') + '.npz')


def _api(host, **q):
    return json.loads(lookup.get(f'https://{host}/api.php?' + urllib.parse.urlencode({'format': 'json', **q}), timeout=15))


def _name(file, pages):
    """IconPerks_hexNoOneEscapesDeath.png + the pages using it -> 'Hex: No One Escapes Death'."""
    stem = re.sub(r'(?i)^iconperks[ _]|\.png$', '', file)
    key = re.sub(r'[^a-z0-9]', '', stem.lower())
    for p in pages:
        if re.sub(r'[^a-z0-9]', '', p.lower()) == key:
            return p
    return re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', re.split('[ _]', stem)[0]).strip().title()


def _art(data):
    """Icon PNG bytes -> its art on black, 96 x 96 uint8."""
    im = Image.open(io.BytesIO(data)).convert('LA').resize((96, 96), Image.LANCZOS)
    l, a = (np.asarray(c, dtype=np.float32) for c in im.split())
    return (l * a / 255).astype(np.uint8)


def download(game, folder):
    """Every icon from the game's wiki -> the bank file. Slow (hundreds of images): call off the main thread."""
    s = spec(game)
    files, cont = {}, {}
    while True:
        d = _api(s['host'], action='query', generator='allimages', gaiprefix=s['prefix'], gailimit='500',
                 prop='imageinfo|fileusage', iiprop='url', funamespace='0', fulimit='500', **cont)
        for p in d['query']['pages'].values():
            f = files.setdefault(p['title'].split(':', 1)[1], {'pages': []})
            if p.get('imageinfo'):
                f['url'] = p['imageinfo'][0]['url']
            f['pages'] += [u['title'] for u in p.get('fileusage', [])]
        if 'continue' not in d:
            break
        cont = d['continue']
    want = sorted(k for k, v in files.items() if v.get('url', '').startswith(f"https://{s['host']}/"))

    def fetch(k):
        lookup.check_url(files[k]['url'])
        req = urllib.request.Request(files[k]['url'], headers={'User-Agent': lookup.UA})
        return _art(lookup._opener.open(req, timeout=15).read())
    with ThreadPoolExecutor(6) as ex:
        arts = list(ex.map(fetch, want))
    path = _bank_path(folder, game)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.savez_compressed(path + '.tmp.npz', art=np.stack(arts), names=np.array([_name(k, files[k]['pages']) for k in want]))
    os.replace(path + '.tmp.npz', path)
    return path


class Bank:
    """Icon art at matching size, normalised, for every scale: (icons, scales, pixels)."""
    def __init__(self, art, names):
        self.names = [str(n) for n in names]
        stack = []
        for a in art:
            im = Image.fromarray(a)
            row = []
            for k in KS:
                side = round(R * k)
                out = Image.new('L', (R, R))
                out.paste(im.resize((side, side), Image.LANCZOS), ((R - side) // 2, (R - side) // 2))
                row.append(np.asarray(out.filter(BLUR), dtype=np.float32)[MASK])
            stack.append(row)
        self.v = _norm(np.stack(stack))


_banks, _busy, _lock = {}, set(), threading.Lock()


def bank(game, folder):
    """The game's icons, or None while they download (started here, in the background)."""
    path = _bank_path(folder, game)
    with _lock:
        if path in _banks:
            return _banks[path]
        if os.path.exists(path):
            with np.load(path) as z:
                _banks[path] = Bank(z['art'], z['names'])
            return _banks[path]
        if path not in _busy:
            _busy.add(path)
            threading.Thread(target=_fetch_bg, args=(game, folder, path), daemon=True).start()
    return None


def _fetch_bg(game, folder, path):
    try:
        download(game, folder)
    except Exception as e:
        print('perks: icons:', e)
    finally:
        with _lock:
            _busy.discard(path)


# finding the slots

def _diamond(n, frac=0.92):
    y, x = np.mgrid[0:n, 0:n] + 0.5 - n / 2
    return (np.abs(x) + np.abs(y)) < frac * n / 2


MASK = _diamond(R)


def _norm(v):
    v = v - v.mean(-1, keepdims=True)
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-6)


def fill(img):
    """How coloured each pixel is, 0..1: a perk's rarity fill, lit or dimmed. Chroma, not saturation: dark noise has high S."""
    a = np.asarray(img, dtype=np.float32)
    hi, lo = a.max(2), a.min(2)
    return np.clip((hi - lo - 8) / 10, 0, 1) * (hi < 220) * ((hi - lo) * 255 > 70 * hi)


def _squares(a, ns, f):
    """Squares of fill with an empty edge in the turned mask a -> [(score, x, y, n)] in units f times a's pixels."""
    ii = np.pad(a, ((1, 0), (1, 0))).cumsum(0).cumsum(1)

    def sums(n):   # sum over the n x n square at every top-left
        return ii[n:, n:] - ii[:-n, n:] - ii[n:, :-n] + ii[:-n, :-n]
    found = []
    for n in ns:
        b, g = max(2, n // 9), max(2, n // 8)
        N = n + 2 + 2 * g   # outside: 1 px gap, then a ring g wide
        outer = sums(N)
        h, w = outer.shape
        sq = sums(n)[g + 1:g + 1 + h, g + 1:g + 1 + w]
        core = sums(n - 2 * b)[g + 1 + b:g + 1 + b + h, g + 1 + b:g + 1 + b + w]
        band = (sq - core) / (n * n - (n - 2 * b) ** 2)   # just inside the edge: fill, the art doesn't reach it
        ys, xs = np.nonzero(band > 0.7)
        if not len(ys):
            continue
        gap = sums(n + 2)[g:g + h, g:g + w][ys, xs]
        ring = (outer[ys, xs] - gap) / (N * N - (n + 2) ** 2)   # just outside: not
        ok = ring < 0.15
        s = band[ys, xs][ok] - ring[ok]
        found += [(v, (x + g + 1 + n / 2) * f, (y + g + 1 + n / 2) * f, n * f) for v, y, x in zip(s, ys[ok], xs[ok])]
    return found


def slots(img, most=16):
    """Diamond-shaped coloured patches with a clear edge -> [(cx, cy, D)] in img pixels, D = the diamond's width.
    Small diamonds at WIDE, big ones at half that (4x fewer pixels, same answer)."""
    scale = WIDE / img.width
    small = img.convert('RGB').resize((WIDE, round(img.height * scale)))
    r = Image.fromarray((fill(small) * 255).astype(np.uint8)).rotate(45, expand=True, resample=Image.BILINEAR)
    a = np.asarray(r, dtype=np.float32) / 255
    half = np.asarray(r.resize((r.width // 2, r.height // 2), Image.BOX), dtype=np.float32) / 255
    found = _squares(a, range(14, 40), 1) + _squares(half, range(20, 38), 2)
    found.sort(reverse=True)
    keep = []
    for s, x, y, n in found:
        if all(abs(x - kx) > (n + kn) * 0.4 or abs(y - ky) > (n + kn) * 0.4 for _, kx, ky, kn in keep):
            keep.append((s, x, y, n))
        if len(keep) >= most:
            break
    c, t = np.array([r.width / 2, r.height / 2]), np.radians(45)
    rot = np.array([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]])   # undo PIL's counter-clockwise turn
    out = []
    for _, x, y, n in keep:
        ox, oy = rot @ (np.array([x, y]) - c) + [small.width / 2, small.height / 2]
        out.append((ox / scale, oy / scale, n * np.sqrt(2) / scale))
    return out + _complete(out)


def _complete(found):
    """Perks sit four to a cluster, in a diamond. A dimmed one (on cooldown) can hide from slots(): two neighbours
    that match place the other corners, and the icon match decides whether a perk is really there."""
    extra = []
    for i, (ax, ay, ad) in enumerate(found):
        for bx, by, bd in found[i + 1:]:
            dx, dy = bx - ax, by - ay
            if abs(ad - bd) > 0.12 * ad or not 0.4 * ad < abs(dx) < 1.0 * ad or abs(abs(dx) - abs(dy)) > 0.15 * ad:
                continue
            for sgn in (1, -1):   # the square on either side of the A-B edge
                px, py = -dy * sgn, dx * sgn
                for x, y in ((ax + px, ay + py), (bx + px, by + py)):
                    if all(abs(x - fx) > 0.3 * ad or abs(y - fy) > 0.3 * ad for fx, fy, _ in found + extra):
                        extra.append((x, y, (ad + bd) / 2))
    return extra


def _art_at(img, cx, cy, D):
    h = D / 2
    c = img.crop((round(cx - h), round(cy - h), round(cx + h), round(cy + h))).convert('RGB').resize((R, R), Image.LANCZOS)
    c = Image.fromarray(np.asarray(c).min(2)).filter(BLUR)
    return np.asarray(c, dtype=np.float32)[MASK]   # light grey art on a coloured fill: the art is what's bright in every channel


def match(img, slot, bank):
    """(name, score, second best score) for the icon in this slot, nudged a little for a loose fit."""
    cx, cy, D = slot
    best = None
    for dx in (-0.04, 0, 0.04):
        for dy in (-0.04, 0, 0.04):
            s = (bank.v @ _norm(_art_at(img, cx + dx * D, cy + dy * D, D))).max(1)
            i, j = np.argsort(s)[::-1][:2]
            if best is None or s[i] > best[1]:
                best = (bank.names[i], float(s[i]), float(s[j]))
    return best


def find(img, bank):
    """Perks on this screen -> [{'name', 'score', 'at': (cx, cy, D)}], clusters top to bottom, left to right."""
    out = []
    for slot in slots(img):
        name, s, second = match(img, slot, bank)
        if s >= SURE and s - second >= MARGIN and all(abs(slot[0] - o['at'][0]) > slot[2] / 3 or abs(slot[1] - o['at'][1]) > slot[2] / 3 for o in out):
            out.append({'name': name, 'score': round(s, 3), 'at': tuple(round(v) for v in slot)})
    return sorted(out, key=lambda p: (round(p['at'][1] * 2 / max(p['at'][2], 1)), p['at'][0]))


def text(img, game, folder, question=''):
    """For the question: the perks on screen, read from their icons, and each one's wiki page; or why not, or ''."""
    s = spec(game)
    if not s or img is None:
        return ''
    b = bank(game, folder)
    if b is None:
        return 'Perk icons are still downloading from the wiki, so the perks on screen could not be read this time.'
    names = list(dict.fromkeys(p['name'] for p in find(img, b)))
    if not names:
        return ''
    with ThreadPoolExecutor(4) as ex:
        pages = list(ex.map(lambda n: lookup.page(f"https://{s['host']}/wiki/" + urllib.parse.quote(n.replace(' ', '_')), question, 1200), names))
    return ('Perks on screen, read from their icons (exact names; trust these over the screenshot): ' + ', '.join(names)
            + ''.join(f'\n\n{n} (wiki):\n{p}' for n, p in zip(names, pages) if p))
