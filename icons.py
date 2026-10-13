"""Things on screen named only by an icon (Dead by Daylight perks, add-ons, items): a model can't name them from the
art, so they're found and matched against the game's wiki icons here, offline, and named in the question.
  recipes: per game, which wiki and which icon sets, and the shape each sits in on screen. Kept in recipes.json on
           the site (fetched at startup), so a game is added without a release; assets/recipes.json is the fallback.
  find:    a coloured patch of that shape with an empty edge -> a slot (diamonds: turned 45 deg into squares;
           summed-area tables). A slot dimmed on cooldown is placed from its cluster of four.
  match:   the slot's light-grey art against every icon of that shape, normalised correlation (right ~0.9+, wrong <0.8).
Icons come from the wiki once per set (perks ~13 s) and are kept as one small file each."""
import hashlib, io, json, os, re, threading, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image, ImageFilter
import lookup

URL = 'https://lorekeeper-cgv.pages.dev/recipes.json'
BUNDLED = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'recipes.json')
SHAPES = {'diamond': (1.0, 1.1, 1.2, 1.3),   # icon scales: the icon's square is a little bigger than the diamond it sits in
          'square': (0.8, 0.9, 1.0, 1.1)}
EDGE = {'diamond': (0.7, 0.15), 'square': (0.5, 0.08)}   # fill just inside the edge, at least; just outside, at most.
# Squares: an item's dark fill is patchy and its art reaches the edge, but nothing sits right outside it.
HOST = re.compile(r'[a-z0-9-]+\.wiki\.gg|[a-z0-9-]+\.fandom\.com')   # a recipe can only point at a game wiki
PREFIX = re.compile(r'[A-Za-z0-9]+_?')
R = 48                     # matching resolution
BLUR = ImageFilter.GaussianBlur(1.2)   # line art is thin: a pixel off would miss it
SURE = {'diamond': 0.88, 'square': 0.85}   # a match is this good (wrong ones < 0.8); squares also need a square beside them
MARGIN = 0.05              # and better than the next icon (Dark Sense vs Kindred), unless that one looks alike: then both
SIZES = {'diamond': (1.0,), 'square': (0.96, 1.02, 1.08)}   # a square's patchy fill makes it look a little small
WIDE = 1280                # finding works at this width
PAGES = 6                  # wiki pages fetched for what was read


# recipes

def valid(doc):
    """A recipes document -> {game name lowercased: recipe}, keeping only well-formed entries (it comes off the network)."""
    out = {}
    for name, r in (doc.get('games') or {}).items() if isinstance(doc, dict) else ():
        try:
            sets = [s for s in r['sets'] if s['shape'] in SHAPES and PREFIX.fullmatch(s['prefix'])
                    and re.fullmatch(r'[a-z -]{2,30}', s['kind'])]
            if HOST.fullmatch(r['host']) and sets:
                out[name.lower()] = {'host': r['host'], 'sets': sets, 'asks': [a for a in r.get('asks', []) if re.fullmatch(r'[a-z -]{2,30}', a)]}
        except (KeyError, TypeError):
            pass
    return out


def _read(path):
    try:
        with open(path, encoding='utf-8') as f:
            return valid(json.load(f))
    except (OSError, ValueError):
        return {}


_recipes, _lock = None, threading.Lock()


def recipes(folder):
    """The cached recipes from the site, else the ones shipped with the app."""
    global _recipes
    if _recipes is None:
        _recipes = _read(os.path.join(folder, 'recipes.json')) or _read(BUNDLED)
    return _recipes


def refresh(folder):
    """Fetch the site's recipes into the cache (startup, background). Returns the games it knows."""
    global _recipes
    doc = json.loads(lookup.get(URL, timeout=10))
    got = valid(doc)
    if got:
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, 'recipes.json'), 'w', encoding='utf-8') as f:
            json.dump(doc, f, indent=1)
        _recipes = got
    return got


def recipe(game, folder):
    return recipes(folder).get((game or {}).get('name', '').lower())


def asks(question, game, folder):
    """Is the question about what these icons show (perks, add-ons...), screen words or not?"""
    r = recipe(game, folder)
    words = [s['kind'] for s in r['sets']] + r['asks'] if r else []
    return bool(words) and bool(re.search(r'\b(?:' + '|'.join(re.escape(w.rstrip('s')) for w in words) + r')s?\b', question, re.I))


# icons: from the wiki, once per set

def _slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def _bank_path(folder, game, r, s):
    tag = hashlib.sha1(f"{r['host']}|{s['prefix']}".encode()).hexdigest()[:8]   # a changed recipe: a new download
    return os.path.join(folder, 'icons', _slug(game['name']), f"{_slug(s['kind'])}-{tag}.npz")


def _api(host, **q):
    return json.loads(lookup.get(f'https://{host}/api.php?' + urllib.parse.urlencode({'format': 'json', **q}), timeout=15))


def _name(file, pages, prefix='IconPerks'):
    """IconPerks_hexNoOneEscapesDeath.png + the pages using it -> ('Hex: No One Escapes Death', True: a page's title)."""
    stem = re.sub(r'(?i)^' + re.escape(prefix.rstrip('_')) + r'[ _]?|\.png$', '', file)
    key = re.sub(r'[^a-z0-9]', '', stem.lower())
    for p in pages:
        if re.sub(r'[^a-z0-9]', '', p.lower()) == key:
            return p, True
    words = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', re.split('[ _]', stem)[0]).strip()
    return ' '.join(w[:1].upper() + w[1:] for w in words.split()), False


def _art(data):
    """Icon PNG bytes -> its art on black, 96 x 96 uint8."""
    im = Image.open(io.BytesIO(data)).convert('LA').resize((96, 96), Image.LANCZOS)
    l, a = (np.asarray(c, dtype=np.float32) for c in im.split())
    return (l * a / 255).astype(np.uint8)


def download(game, folder, r, s):
    """Every icon of one set from the game's wiki -> its bank file. Slow (hundreds of images): off the main thread."""
    files, cont = {}, {}
    while True:
        d = _api(r['host'], action='query', generator='allimages', gaiprefix=s['prefix'], gailimit='500',
                 prop='imageinfo|fileusage', iiprop='url', funamespace='0', fulimit='500', **cont)
        for p in d.get('query', {}).get('pages', {}).values():
            f = files.setdefault(p['title'].split(':', 1)[1], {'pages': []})
            if p.get('imageinfo'):
                f['url'] = p['imageinfo'][0]['url']
            f['pages'] += [u['title'] for u in p.get('fileusage', [])]
        if 'continue' not in d:
            break
        cont = d['continue']
    want = sorted(k for k, v in files.items() if v.get('url', '').startswith(f"https://{r['host']}/"))

    def fetch(k):
        try:
            lookup.check_url(files[k]['url'])
            req = urllib.request.Request(files[k]['url'], headers={'User-Agent': lookup.UA})
            return _art(lookup._opener.open(req, timeout=15).read())
        except Exception:
            return None   # one bad file doesn't lose the set
    with ThreadPoolExecutor(6) as ex:
        arts = list(ex.map(fetch, want))
    keep = [i for i, a in enumerate(arts) if a is not None]
    if not keep:
        raise ValueError(f"no {s['kind']} icons on {r['host']}")
    path = _bank_path(folder, game, r, s)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    named = [_name(want[i], files[want[i]]['pages'], s['prefix']) for i in keep]
    np.savez_compressed(path + '.tmp.npz', art=np.stack([arts[i] for i in keep]),
                        names=np.array([n for n, _ in named]), paged=np.array([p for _, p in named]))
    os.replace(path + '.tmp.npz', path)
    return path


class Bank:
    """One set's icon art at matching size, normalised, for every scale: (icons, scales, pixels)."""
    def __init__(self, art, names, shape='diamond', kind='', paged=None):
        self.names, self.shape, self.kind = [str(n) for n in names], shape, kind
        self.paged = list(paged) if paged is not None else [False] * len(self.names)   # name is a wiki page's title
        stack = []
        for a in art:
            im = Image.fromarray(a)
            row = []
            for k in SHAPES[shape]:
                side = round(R * k)
                out = Image.new('L', (R, R))
                out.paste(im.resize((side, side), Image.LANCZOS), ((R - side) // 2, (R - side) // 2))
                row.append(np.asarray(out.filter(BLUR), dtype=np.float32)[MASKS[shape]])
            stack.append(row)
        self.v = _norm(np.stack(stack))
        k = SHAPES[shape].index(1.0)
        self.like = self.v[:, k] @ self.v[:, k].T   # icon vs icon: the wiki has some art twice under two names


_banks, _busy = {}, set()


def banks(game, folder):
    """The game's icon sets that are ready; the rest start downloading here, in the background."""
    r = recipe(game, folder)
    out = []
    for s in r['sets'] if r else ():
        path = _bank_path(folder, game, r, s)
        with _lock:
            if path not in _banks and os.path.exists(path):
                try:
                    with np.load(path) as z:
                        _banks[path] = Bank(z['art'], z['names'], s['shape'], s['kind'], z['paged'] if 'paged' in z else None)
                except Exception as e:
                    print('icons:', path, e)
                    os.remove(path)
            if path in _banks:
                out.append(_banks[path])
            elif path not in _busy:
                _busy.add(path)
                threading.Thread(target=_fetch_bg, args=(game, folder, r, s, path), daemon=True).start()
    return out


def _fetch_bg(game, folder, r, s, path):
    try:
        download(game, folder, r, s)
    except Exception as e:
        print('icons:', s['kind'], e)
    finally:
        with _lock:
            _busy.discard(path)


def prefetch(gs, folder):
    """At startup: the site's recipes, then icons for the games installed here."""
    try:
        refresh(folder)
    except Exception as e:
        print('icons: recipes:', e)
    for g in gs:
        banks(g, folder)


# finding the slots

def _mask(shape, n=R):
    y, x = np.mgrid[0:n, 0:n] + 0.5 - n / 2
    if shape == 'diamond':
        return (np.abs(x) + np.abs(y)) < 0.92 * n / 2
    return (x * x + y * y) < (0.44 * n) ** 2   # square: the middle; its corners carry badges ("+", key prompts)


MASKS = {s: _mask(s) for s in SHAPES}


def _norm(v):
    v = v - v.mean(-1, keepdims=True)
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-6)


def fill(img):
    """How coloured each pixel is, 0..1: a slot's rarity fill, lit or dimmed. Chroma, not saturation: dark noise has high S."""
    a = np.asarray(img, dtype=np.float32)
    hi, lo = a.max(2), a.min(2)
    return np.clip((hi - lo - 8) / 10, 0, 1) * (hi < 220) * ((hi - lo) * 255 > 70 * hi)


def _squares(a, ns, f, edge=EDGE['diamond']):
    """Squares of fill with an empty edge in the mask a -> [(score, x, y, n)] in units f times a's pixels."""
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
        ys, xs = np.nonzero(band > edge[0])
        if not len(ys):
            continue
        gap = sums(n + 2)[g:g + h, g:g + w][ys, xs]
        ring = (outer[ys, xs] - gap) / (N * N - (n + 2) ** 2)   # just outside: not
        ok = ring < edge[1]
        s = band[ys, xs][ok] - ring[ok]
        found += [(v, (x + g + 1 + n / 2) * f, (y + g + 1 + n / 2) * f, n * f) for v, y, x in zip(s, ys[ok], xs[ok])]
    return found


def slots(img, shape='diamond', most=16):
    """Patches of colour in this shape with a clear edge -> [(cx, cy, D)] in img pixels, D = the shape's width.
    Small ones at WIDE, big ones at half that (4x fewer pixels, same answer)."""
    scale = WIDE / img.width
    small = img.convert('RGB').resize((WIDE, round(img.height * scale)))
    m = Image.fromarray((fill(small) * 255).astype(np.uint8))
    turn = shape == 'diamond'
    r = m.rotate(45, expand=True, resample=Image.BILINEAR) if turn else m
    a = np.asarray(r, dtype=np.float32) / 255
    half = np.asarray(r.resize((r.width // 2, r.height // 2), Image.BOX), dtype=np.float32) / 255
    found = _squares(a, range(14, 40), 1, EDGE[shape]) + _squares(half, range(20, 38), 2, EDGE[shape])
    found.sort(reverse=True)
    keep = []
    for s, x, y, n in found:
        if all(abs(x - kx) > (n + kn) * 0.4 or abs(y - ky) > (n + kn) * 0.4 for _, kx, ky, kn in keep):
            keep.append((s, x, y, n))
        if len(keep) >= most:
            break
    out = []
    if turn:
        c, t = np.array([r.width / 2, r.height / 2]), np.radians(45)
        rot = np.array([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]])   # undo PIL's counter-clockwise turn
        for _, x, y, n in keep:
            ox, oy = rot @ (np.array([x, y]) - c) + [small.width / 2, small.height / 2]
            out.append((ox / scale, oy / scale, n * np.sqrt(2) / scale))
        return out + _complete(out)
    return [(x / scale, y / scale, n / scale) for _, x, y, n in keep]


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


def _art_at(img, cx, cy, D, shape):
    h = D / 2
    c = img.crop((round(cx - h), round(cy - h), round(cx + h), round(cy + h))).convert('RGB').resize((R, R), Image.LANCZOS)
    c = Image.fromarray(np.asarray(c).min(2)).filter(BLUR)   # light grey art on a coloured fill: bright in every channel
    return np.asarray(c, dtype=np.float32)[MASKS[shape]]


def match(img, slot, bank):
    """(name, score, runner-up's score, runner-up's name, how alike their art is) for the icon in this slot,
    nudged a little for a loose fit. Of identical art under two names, the one that is a wiki page's title."""
    cx, cy, D = slot
    best = None
    for z in SIZES[bank.shape]:
        for dx in (-0.04, 0, 0.04):
            for dy in (-0.04, 0, 0.04):
                s = (bank.v @ _norm(_art_at(img, cx + dx * D, cy + dy * D, D * z, bank.shape))).max(1)
                if best is None or s.max() > best[0].max():
                    best = (s,)
    s = best[0]
    order = np.argsort(s)[::-1]
    i = order[0]
    twins = [i] + [j for j in order[1:8] if bank.like[i, j] > 0.97]   # the same art: the same thing, not a rival
    rest = [j for j in order[1:] if bank.like[i, j] <= 0.97][:1]
    name = bank.names[min(twins, key=lambda j: (not bank.paged[j], len(bank.names[j])))]
    if not rest:
        return name, float(s[i]), 0.0, '', 0.0
    j = rest[0]
    other = bank.names[min([j] + [k for k in order[:12] if bank.like[j, k] > 0.97], key=lambda k: (not bank.paged[k], len(bank.names[k])))]
    return name, float(s[i]), float(s[j]), other, float(bank.like[i, j])


def find(img, bs):
    """What these icon banks see on this screen -> [{'kind', 'name', 'score', 'at': (cx, cy, D)}], top to bottom."""
    out = []
    for shape in dict.fromkeys(b.shape for b in bs):
        found = slots(img, shape)
        for slot in found:
            if any(abs(slot[0] - o['at'][0]) < slot[2] / 3 and abs(slot[1] - o['at'][1]) < slot[2] / 3 for o in out):
                continue
            if shape == 'square' and not any(o is not slot and 0.3 < o[2] / slot[2] < 3 and np.hypot(o[0] - slot[0], o[1] - slot[1]) < 2.5 * max(o[2], slot[2])
                                             for o in found):
                continue   # an item's add-ons sit beside it: a lone square is a sign, a wall, a status icon
            got = [(b.kind,) + match(img, slot, b) for b in bs if b.shape == shape]
            kind, name, s, second, other, alike = max(got, key=lambda g: g[2])
            runner = max([second] + [g[2] for g in got if g[0] != kind])   # next best across the sets too
            if s < SURE[shape] or (s - runner < MARGIN and not (runner == second and alike > 0.8)):
                continue
            if s - runner < MARGIN:
                name = f'{name} (or {other}: they look alike)'
            out.append({'kind': kind, 'name': name, 'score': round(s, 3), 'at': tuple(round(v) for v in slot)})
    return sorted(out, key=lambda p: (round(p['at'][1] * 2 / max(p['at'][2], 1)), p['at'][0]))


def text(img, game, folder, question=''):
    """For the question: what's on screen, read from its icons, and each thing's wiki page; or why not, or ''."""
    r = recipe(game, folder)
    if not r or img is None:
        return ''
    bs = banks(game, folder)
    if not bs:
        return 'Icons for this game are still downloading from its wiki, so nothing on screen could be read from them this time.'
    seen = find(img, bs)
    if not seen:
        return ''
    by = {}
    for p in seen:
        by.setdefault(p['kind'], [])
        if p['name'] not in by[p['kind']]:
            by[p['kind']].append(p['name'])
    names = [n for ns in by.values() for n in ns][:PAGES]
    with ThreadPoolExecutor(4) as ex:
        pages = list(ex.map(lambda n: lookup.page(f"https://{r['host']}/wiki/" + urllib.parse.quote(n.replace(' ', '_')), question, 1200), names))
    return ('On screen, read from their icons (exact names; trust these over the screenshot): '
            + '; '.join(f"{k}: {', '.join(ns)}" for k, ns in by.items())
            + ''.join(f'\n\n{n} (wiki):\n{p}' for n, p in zip(names, pages) if p))
