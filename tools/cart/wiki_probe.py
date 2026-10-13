"""What a game's MediaWiki holds, for building its cart: icon file prefixes, big categories, title shapes.
  python wiki_probe.py deadbydaylight.wiki.gg [--prefix IconPerks_] [--twins IconPerks_]"""
import collections, json, re, sys, urllib.error, urllib.parse, urllib.request

UA = 'Lorekeeper-cartmaker/0.1 (https://github.com/FindlayHi/lorekeeper)'


def api(host, **q):
    for path in ('/api.php', '/w/api.php'):   # wiki.gg and Fandom; most others (bg3.wiki)
        url = f'https://{host}{path}?' + urllib.parse.urlencode({'format': 'json', 'action': 'query', **q})
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=20))
        except urllib.error.HTTPError as e:
            if e.code != 404 or path != '/api.php':
                raise


def every(host, key, **q):
    cont = {}
    while True:
        d = api(host, **q, **cont)
        yield from d.get('query', {}).get(key, [])
        if 'continue' not in d:
            return
        cont = d['continue']


def prefixes(host, most=5000):
    """Image name prefixes ('IconPerks_') -> count: the icon sets a cart can name."""
    c = collections.Counter()
    for n, im in enumerate(every(host, 'allimages', list='allimages', ailimit='500', aiprop='')):
        m = re.match(r'([A-Za-z]+[_ ]?)', im['name'])
        if m:
            c[m[1].replace(' ', '_')] += 1
        if n >= most:
            break
    return c


def icon_sets(host, n=25):
    """Image categories ('Perk images', 'Addon images') -> (category, size, the file prefix their members share):
    the candidates for a cart's icon sets. Wikis file icons by category, not by an alphabet a scan reaches."""
    out = []
    for name, size in categories(host, 200):
        if not re.search(r'(?i)\b(images?|icons?)\b', name) or size < 5:
            continue
        files = [t.split(':', 1)[1] for t in sample(host, name, 20) if t.startswith('File:')]
        heads = collections.Counter(m[1].replace(' ', '_') for f in files if (m := re.match(r'([A-Za-z]+[_ ])', f)))
        if heads:
            head, k = heads.most_common(1)[0]
            if k >= len(files) * 0.6:
                out.append((name, size, head))
    return out[:n]


def categories(host, n=40):
    d = api(host, list='allcategories', aclimit='500', acprop='size')
    cats = sorted(d['query']['allcategories'], key=lambda c: -c.get('size', 0))
    return [(c['*'], c.get('size', 0)) for c in cats[:n]]


def sample(host, cat, n=8):
    return [p['title'] for p in api(host, list='categorymembers', cmtitle=f'Category:{cat}', cmlimit=str(n))['query']['categorymembers']]


def twins(host, prefix):
    """Icons whose file name isn't the title of a page using them: candidates for 'aka' in the library."""
    out = []
    for p in every(host, 'pages', generator='allimages', gaiprefix=prefix, gailimit='500', prop='fileusage', funamespace='0', fulimit='50'):
        stem = re.sub(r'(?i)^' + re.escape(prefix.rstrip('_')) + r'[ _]?|\.png$', '', p['title'].split(':', 1)[1])
        key = re.sub(r'[^a-z0-9]', '', stem.lower())
        pages = [u['title'] for u in p.get('fileusage', [])]
        if pages and not any(re.sub(r'[^a-z0-9]', '', t.lower()) == key for t in pages):
            out.append((stem, pages[:3]))
    return out


if __name__ == '__main__':
    host = sys.argv[1]
    if '--twins' in sys.argv:
        for stem, pages in twins(host, sys.argv[sys.argv.index('--twins') + 1]):
            print(f'{stem:40s} used on {pages}')
        sys.exit()
    print('icon sets (image categories sharing a file prefix):')
    for name, size, head in icon_sets(host):
        print(f'  {head:20s} {size:5d}  {name}')
    print('categories:')
    for name, size in categories(host):
        print(f'  {name:40s} {size:5d}  e.g. {sample(host, name, 4)}')
