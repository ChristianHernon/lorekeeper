import hashlib, io, os, sys, tempfile
os.environ.setdefault('LOREKEEPER_DIR', tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest  # noqa: E402
import config, firstrun  # noqa: E402

BODY = b'pretend model' * 5000


class Resp(io.BytesIO):
    headers = {'Content-Length': str(len(BODY))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


@pytest.fixture(autouse=True)
def models(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'MODELS', str(tmp_path))
    monkeypatch.setattr(firstrun.urllib.request, 'urlopen', lambda *a, **k: Resp(BODY))
    return tmp_path


def test_every_model_file_has_a_pinned_hash():
    assert set(firstrun.MODEL_SHA256) == set(firstrun.MODEL_FILES)
    assert all(len(v) == 64 for v in firstrun.MODEL_SHA256.values())


def test_a_download_that_matches_is_kept(models, monkeypatch):
    monkeypatch.setattr(firstrun, 'MODEL_SHA256', {f: hashlib.sha256(BODY).hexdigest() for f in firstrun.MODEL_FILES})
    assert firstrun.download_models() is True
    assert all((models / f).read_bytes() == BODY for f in firstrun.MODEL_FILES)


def test_a_download_that_does_not_match_is_thrown_away(models):
    with pytest.raises(ValueError, match='checksum'):
        firstrun.download_models()
    assert os.listdir(models) == []   # no model file, no .part left behind
