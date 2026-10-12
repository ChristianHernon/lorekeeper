import json, os, sys, tempfile, time
os.environ.setdefault('LOREKEEPER_DIR', tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest  # noqa: E402
import config, telemetry  # noqa: E402

KEY = 'phc_test'


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(telemetry, 'FILE', str(tmp_path / 'telemetry.json'))
    monkeypatch.setattr(config, 'DIR', str(tmp_path))
    monkeypatch.delenv('DO_NOT_TRACK', raising=False)
    monkeypatch.setattr(telemetry.urllib.request, 'urlopen', lambda *a, **k: pytest.fail('no network in tests'))


def cfg(**kw):
    return {**config.DEFAULTS, 'posthogKey': KEY, **kw}


def sent():
    calls = []
    return calls, lambda c, event, did, props: calls.append((event, did, props))


def test_installed_then_active_once_a_day(monkeypatch):
    calls, sender = sent()
    assert telemetry.ping(cfg(), sender) == ['installed', 'active']
    assert telemetry.ping(cfg(), sender) == []   # same day: nothing
    monkeypatch.setattr(telemetry.time, 'strftime', lambda f: '2099-01-01')
    assert telemetry.ping(cfg(), sender) == ['active']
    ids = {did for _, did, _ in calls}
    assert len(ids) == 1 and len(ids.pop()) == 32   # one random install id, kept


def test_off_sends_nothing(monkeypatch):
    calls, sender = sent()
    assert telemetry.ping(cfg(telemetry=False), sender) == []
    assert telemetry.ping(cfg(posthogKey=''), sender) == []   # the shipped default: no key, no-op
    monkeypatch.setenv('DO_NOT_TRACK', '1')
    assert telemetry.ping(cfg(), sender) == []
    assert calls == [] and not os.path.exists(telemetry.FILE)   # not even an id is made


def test_only_counts_and_switches_leave():
    calls, sender = sent()
    c = cfg(listen=True, rommUrl='http://192.168.0.50:3010', voice='edge')
    telemetry.ping(c, sender)
    props = calls[0][2]
    assert set(props) == {'version', 'commit', 'os', 'os_build', 'listen', 'romm', 'voice',
                          '$process_person_profile', '$geoip_disable', '$lib'}
    assert props['listen'] is True and props['romm'] is True and props['voice'] == 'edge'
    assert '192.168' not in json.dumps(props)   # the RomM address itself never goes


def test_notice_once_and_only_when_it_would_send():
    assert telemetry.notice(cfg(posthogKey='')) == ''
    assert telemetry.notice(cfg(telemetry=False)) == ''
    assert 'Share anonymous usage counts' in telemetry.notice(cfg())
    assert telemetry.notice(cfg()) == ''


def test_send_swallows_failures(monkeypatch):
    def boom(*a, **k):
        raise OSError('offline')
    monkeypatch.setattr(telemetry.urllib.request, 'urlopen', boom)
    t = time.time()
    telemetry.send(cfg(), 'active', 'x', {})   # no exception
    assert time.time() - t < 1


def test_send_posts_to_capture(monkeypatch):
    seen = {}

    class R:
        def close(self):
            pass

    def fake(req, timeout):
        seen.update(url=req.full_url, body=json.loads(req.data), timeout=timeout)
        return R()
    monkeypatch.setattr(telemetry.urllib.request, 'urlopen', fake)
    telemetry.send(cfg(), 'active', 'abc', {'version': '0.1'})
    assert seen['url'] == 'https://us.i.posthog.com/i/v0/e/'
    assert seen['body'] == {'api_key': KEY, 'event': 'active', 'distinct_id': 'abc', 'properties': {'version': '0.1'}}
    assert seen['timeout'] <= 5


def test_shipped_key_is_a_public_project_key():   # never a personal API key (phx_)
    assert config.DEFAULTS['posthogKey'] == '' or config.DEFAULTS['posthogKey'].startswith('phc_')


def test_commit_from_a_clone(tmp_path):
    (tmp_path / '.git' / 'refs' / 'heads').mkdir(parents=True)
    (tmp_path / '.git' / 'HEAD').write_text('ref: refs/heads/main\n')
    (tmp_path / '.git' / 'packed-refs').write_text('# pack-refs\nabcdef1234567890 refs/heads/main\n')
    assert telemetry._commit(str(tmp_path)) == 'abcdef1'
    (tmp_path / '.git' / 'refs' / 'heads' / 'main').write_text('1234567abcdef\n')
    assert telemetry._commit(str(tmp_path)) == '1234567'
    assert telemetry._commit(str(tmp_path / 'nowhere')) == ''
