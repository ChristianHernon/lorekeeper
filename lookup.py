"""Wiki text fetched before the model starts thinking: one DuckDuckGo search, then the top wiki pages' source.
Most questions are answered from this in one pass, skipping the model's own search-then-fetch round trips (~10 s)."""
import html, json, os, re, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
import config

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
WIKIS = ('bg3.wiki', 'wiki.gg', 'fandom.com', 'fextralife.com', 'game8.co', 'wikia', 'wiki')   # earlier = preferred
# MediaWiki sites whose page source we can fetch (infoboxes keep quotes and stats): host pattern -> api.php path
APIS = {r'[^/]+\.wiki\.gg': '/api.php', r'[^/]+\.fandom\.com': '/api.php', r'bg3\.wiki': '/w/api.php'}
MEDIAWIKI = re.compile(r'^https?://(' + '|'.join(APIS) + r')/wiki/([^?#]+)')


def get(url, timeout=4):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    return urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8', 'replace')


def text_of(h):
    m = re.search(r'(?is)<main\b.*?</main>|<article\b.*?</article>', h)
    h = m.group(0) if m else h
    h = re.sub(r'(?is)<(script|style|noscript|svg|head|nav|header|footer|aside)\b.*?</\1>', ' ', h)
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', h)).split())


def search(q):
    page = get('https://html.duckduckgo.com/html/?q=' + urllib.parse.quote(q), timeout=5)
    out = []
    for u in re.findall(r'class="result__a" href="([^"]+)"', page)[:8]:
        u = urllib.parse.parse_qs(urllib.parse.urlparse(html.unescape(u)).query).get('uddg', [u])[0]
        if u.startswith('http') and u not in out:
            out.append(u)
    return out


def rank(urls):
    def score(u):
        host = urllib.parse.urlparse(u).netloc
        return next((i for i, w in enumerate(WIKIS) if w in host), len(WIKIS))
    return sorted(urls, key=score)


def page(url, most=3500):
    """A wiki page's source (infoboxes keep the quote/flavor text and stats), else the page as plain text."""
    m = MEDIAWIKI.match(url)
    try:
        if m:
            api_path = next(p for h, p in APIS.items() if re.fullmatch(h, m[1]))
            api = f'https://{m[1]}{api_path}?action=parse&format=json&prop=wikitext&redirects=1&page=' + m[2]
            j = json.loads(get(api))
            wt = j.get('parse', {}).get('wikitext', {}).get('*', '')
            wt = re.sub(r'\[\[(?:File|Image|Category):[^\]]*\]\]|<!--.*?-->|<ref[^>]*>.*?</ref>', '', wt, flags=re.S)
            if wt.strip():
                return wt.strip()[:most]
        return text_of(get(url))[:most]
    except Exception:
        return ''


KNOWN = {"baldur's gate 3": 'bg3.wiki', 'enter the gungeon': 'enterthegungeon.wiki.gg', 'hades': 'hades.fandom.com',
         'hades ii': 'hades.fandom.com', 'terraria': 'terraria.wiki.gg', 'risk of rain 2': 'riskofrain2.wiki.gg',
         'dead by daylight': 'deadbydaylight.wiki.gg', 'deep rock galactic': 'deeprockgalactic.wiki.gg', 'subnautica 2': 'subnautica.fandom.com',
         'stardew valley': 'stardewvalleywiki.com', 'the binding of isaac: rebirth': 'bindingofisaacrebirth.wiki.gg'}
HOSTS = os.path.join(config.DIR, 'wikis.json')   # learned: game name -> its MediaWiki host ('' = none found)
STOP = r"\b(what|whats|does|do|is|are|the|a|an|did|i|just|get|got|me|tell|about|how|can|should|where|who|which|my|to|of|in|for|it|this|that|please|ok|okay|hey)\b"


def api_path(host):
    return next((p for h, p in APIS.items() if re.fullmatch(h, host)), '/api.php')


def _hosts():
    try:
        with open(HOSTS, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _learn(game, host):
    h = _hosts()
    h[game.lower()] = host
    os.makedirs(config.DIR, exist_ok=True)
    with open(HOSTS, 'w', encoding='utf-8') as f:
        json.dump(h, f, indent=1)


def guess_host(game):
    """<game>.wiki.gg, then <game>.fandom.com, if either answers as a MediaWiki -> host or ''."""
    base = re.sub(r'[^a-z0-9]', '', game.lower())
    for host in (f'{base}.wiki.gg', f'{base}.fandom.com'):
        try:
            j = json.loads(get(f'https://{host}/api.php?action=query&meta=siteinfo&format=json', timeout=3))
            if j.get('query', {}).get('general'):
                return host
        except Exception:
            pass
    return ''


def host_for(game, urls=()):
    """The game's wiki host: known, learned, seen in search results, or guessed once."""
    g = game.lower()
    if g in KNOWN:
        return KNOWN[g]
    h = _hosts()
    if h.get(g):
        return h[g]
    for u in urls:
        m = MEDIAWIKI.match(u)
        if m:
            _learn(game, m[1])
            return m[1]
    if g not in h:   # guess once per game
        found = guess_host(game)
        _learn(game, found)
        return found
    return ''


GENERIC = r"\b(perks?|power|item|items|synergy|synergies|skills?|abilit(?:y|ies)|spells?|builds?|weapon|armou?r|boss|quest|location|lore|killer|survivor|add-?ons?|effect|work|works|mean|good|best|better|use)\b"


def titles(question):
    """Page titles the question may name, likeliest first: its capitalized runs ("Dead Hard"), then its key words."""
    q = re.sub(r"[^\w' -]", ' ', question)
    runs = [r for r in re.findall(r"\b[A-Z][\w'-]*(?:\s+(?:of|the|de|du)?\s*[A-Z][\w'-]*)*", q) if r.lower() not in ('i', 'what', 'who', 'how')]
    key = ' '.join(re.sub(GENERIC, ' ', re.sub(STOP, ' ', q, flags=re.I), flags=re.I).split())
    out = []
    for t in runs + [key, key.title()] + [f'The {r}' for r in runs]:   # "The Nurse" is how DBD titles killers
        t = re.sub(GENERIC, ' ', t, flags=re.I)
        t = ' '.join(t.split())
        if t and t not in out:
            out.append(t)
    return out[:8]


def site_search(host, question, n=2):
    """The wiki's own API: names in the question that are page titles first, then its full-text search. ~0.3 s, no captchas."""
    api = f'https://{host}{api_path(host)}?format=json&action=query'
    url = lambda t: f"https://{host}/wiki/{urllib.parse.quote(t.replace(' ', '_'))}"
    out = []
    cands = titles(question)
    if cands:
        j = json.loads(get(api + '&redirects=1&titles=' + urllib.parse.quote('|'.join(cands)), timeout=4)).get('query', {})
        real = {p['title'] for p in j.get('pages', {}).values() if 'missing' not in p and 'invalid' not in p}
        moved = {r['from']: r['to'] for r in j.get('redirects', [])} | {nm['from']: nm['to'] for nm in j.get('normalized', [])}
        for c in cands:
            t = moved.get(moved.get(c, c), moved.get(c, c))
            if t in real and url(t) not in out:
                out.append(url(t))
    terms = ' '.join(re.sub(STOP, ' ', re.sub(r"[^\w' ]", ' ', question), flags=re.I).split())
    if len(out) < n and terms:
        j = json.loads(get(api + f'&list=search&srlimit={n}&srsearch=' + urllib.parse.quote(terms), timeout=4))
        out += [url(r['title']) for r in j.get('query', {}).get('search', []) if url(r['title']) not in out]
    return out[:n]


def query(question, game):
    q = re.sub(STOP, ' ', question, flags=re.I)
    return f"{game} wiki {' '.join(q.split())}" if game else ' '.join(q.split())


def wiki(question, game, pages=2):
    """'Source: <url>\n<text>' blocks for the prompt, or '' when the search finds nothing (the model searches itself)."""
    urls = []
    host = host_for(game) if game else ''
    if host:
        try:
            urls = site_search(host, question, pages)
        except Exception:
            urls = []
    if not urls:
        try:
            found = search(query(question, game))
        except Exception:
            found = []
        if game and not host and found:
            host_for(game, found)   # learn the wiki for next time
        urls = rank(found)[:pages]
    if not urls:
        return ''
    with ThreadPoolExecutor(pages or 1) as ex:
        texts = list(ex.map(page, urls))
    return '\n\n'.join(f'Source: {u}\n{t}' for u, t in zip(urls, texts) if t)
