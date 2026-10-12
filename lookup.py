"""Wiki text fetched before the model starts thinking: one DuckDuckGo search, then the top wiki pages' source.
Most questions are answered from this in one pass, skipping the model's own search-then-fetch round trips (~10 s)."""
import html, json, re, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
WIKIS = ('wiki.gg', 'fandom.com', 'fextralife.com', 'game8.co', 'wikia', 'wiki')   # earlier = preferred
MEDIAWIKI = re.compile(r'^https?://([^/]+\.(?:wiki\.gg|fandom\.com))/wiki/([^?#]+)')


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
            api = f'https://{m[1]}/api.php?action=parse&format=json&prop=wikitext&redirects=1&page=' + m[2]
            j = json.loads(get(api))
            wt = j.get('parse', {}).get('wikitext', {}).get('*', '')
            wt = re.sub(r'\[\[(?:File|Image|Category):[^\]]*\]\]|<!--.*?-->|<ref[^>]*>.*?</ref>', '', wt, flags=re.S)
            if wt.strip():
                return wt.strip()[:most]
        return text_of(get(url))[:most]
    except Exception:
        return ''


def query(question, game):
    q = re.sub(r"\b(what|does|do|is|the|a|an|did|i|just|get|got|me|tell|about|how|can)\b", ' ', question, flags=re.I)
    return f"{game} wiki {' '.join(q.split())}" if game else ' '.join(q.split())


def wiki(question, game, pages=2):
    """'Source: <url>\n<text>' blocks for the prompt, or '' when the search finds nothing (the model searches itself)."""
    try:
        urls = rank(search(query(question, game)))[:pages]
    except Exception:
        return ''
    with ThreadPoolExecutor(pages or 1) as ex:
        texts = list(ex.map(page, urls))
    return '\n\n'.join(f'Source: {u}\n{t}' for u, t in zip(urls, texts) if t)
