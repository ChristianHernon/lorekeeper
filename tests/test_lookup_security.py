import os, sys, tempfile
os.environ.setdefault('LOREKEEPER_DIR', tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest  # noqa: E402
import config, lookup  # noqa: E402


@pytest.mark.parametrize('url, host', [
    ('https://terraria.wiki.gg/wiki/Zenith', 'terraria.wiki.gg'),
    ('https://the-witcher.fandom.com/wiki/Geralt', 'the-witcher.fandom.com'),
    ('https://bg3.wiki/wiki/Shield_of_Devotion', 'bg3.wiki'),
    ('https://www.poe2wiki.net/wiki/Spark', 'www.poe2wiki.net'),
])
def test_real_wiki_hosts_match(url, host):
    assert lookup.MEDIAWIKI.match(url)[1] == host


@pytest.mark.parametrize('url', [
    'https://evil.example?x=.fandom.com/wiki/Foo',        # the "host" would run on past the '?'
    'https://evil.example#.wiki.gg/wiki/Foo',
    'https://user@evil.example/x.wiki.gg/wiki/Foo',
    'https://evil.example:8443?.fandom.com/wiki/Foo',
    'https://evil.example/.wiki.gg/wiki/Foo',
    'https://notwiki.gg/wiki/Foo',
])
def test_lookalike_hosts_do_not_match(url):
    assert lookup.MEDIAWIKI.match(url) is None


def test_a_page_title_cannot_add_query_parameters(monkeypatch):
    seen = []
    monkeypatch.setattr(lookup, 'get', lambda url, timeout=4: seen.append(url) or '{"parse": {"wikitext": {"*": "text"}}}')
    lookup.page('https://terraria.wiki.gg/wiki/Zenith&action=delete')
    assert seen and '&action=delete' not in seen[0] and seen[0].endswith('page=Zenith%26action%3Ddelete')


def test_a_saved_host_that_is_not_a_hostname_is_ignored(monkeypatch, tmp_path):
    monkeypatch.setattr(config, 'DIR', str(tmp_path))
    monkeypatch.setattr(lookup, 'HOSTS', str(tmp_path / 'wikis.json'))
    monkeypatch.setattr(lookup, 'guess_host', lambda game: '')
    (tmp_path / 'wikis.json').write_text('{"somegame": "evil.example?x=.fandom.com", "other": "other.wiki.gg"}')
    assert lookup.host_for('somegame') == ''
    assert lookup.host_for('other') == 'other.wiki.gg'


@pytest.mark.parametrize('url', [
    'http://example.com/', 'file:///C:/Windows/win.ini', 'ftp://example.com/', 'https:///nohost',
    'https://localhost/', 'https://127.0.0.1/', 'https://[::1]/', 'https://10.0.0.5/', 'https://192.168.1.1/admin',
    'https://169.254.169.254/latest/meta-data/', 'https://172.16.0.1/', 'https://0.0.0.0/',
])
def test_get_refuses_non_public_or_non_https(url, monkeypatch):
    monkeypatch.setattr(lookup._opener, 'open', lambda *a, **k: pytest.fail('must not be fetched'))
    with pytest.raises(ValueError):
        lookup.get(url)


def test_a_redirect_to_an_internal_address_is_refused():
    handler = lookup._Redirects()
    req = lookup.urllib.request.Request('https://example.com/')
    with pytest.raises(ValueError):
        handler.redirect_request(req, None, 302, 'Found', {}, 'https://127.0.0.1/secret')
