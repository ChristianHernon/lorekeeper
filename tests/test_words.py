import os, sys, tempfile

os.environ['LOREKEEPER_DIR'] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import brain, capture, commands, notes, voice  # noqa: E402


def test_commands():
    p = commands.parse
    assert p('Clip it.') == ('clip', '')
    assert p('Lorekeeper, clip that!') == ('clip', '')
    assert p('Okay, spoil it.') == ('spoil', '')
    assert p("I'm playing Enter the Gungeon") == ('playing', 'Enter the Gungeon')
    assert p('I just beat Margit.') == ('note', 'I just beat Margit')
    assert p("I'm at Stormveil Castle") == ('note', "I'm at Stormveil Castle")
    assert p('Note: I went with a dex build') == ('note', 'I went with a dex build')
    assert p("I'm at Stormveil, where do I go next?") is None
    assert p('What synergy did I just get?') is None
    assert p('Stop.') == ('stop', '')
    assert p('repeat that') == ('repeat', '')


def test_screen_words():
    assert capture.wants('what synergy did I just get')
    assert capture.wants('what does this item do')
    assert not capture.wants('what does the Shadow Bullets synergy do')
    assert capture.JUST.search('what synergy did I just get')


def test_deep_model_words():
    assert brain.DEEP.search('tell me more about the Gungeon lore')
    assert not brain.DEEP.search('what does the casey do')


def test_request_and_prompt():
    g = {'name': 'Enter the Gungeon', 'id': '311690', 'source': 'steam'}
    r = brain.request('what does Shadow Clone do', g, '- 2026-10-12: on chamber 3', [{'q': 'a', 'a': 'b'}])
    assert r.startswith('Game: Enter the Gungeon (Steam app 311690)') and 'chamber 3' in r and r.endswith('Question: what does Shadow Clone do')
    assert 'Game: unknown' in brain.request('hi', None, '', [])
    assert len(brain.SYSTEM + brain.SPOILER_SAFE) < 4000


def test_notes_and_names():
    g = {'name': 'ELDEN RING'}
    notes.add(g, 'I just beat Margit at Stormveil Castle')
    assert 'Margit' in notes.read(g) and 'Stormveil Castle' in notes.names(g)
    assert notes.path(g).endswith('elden-ring.md')


def test_split_for_speech():
    assert voice.split('**Shadow Clone** doubles you. See https://x.y/z for more.\nIts flavor text: "Me too."') == \
        ['Shadow Clone doubles you.', 'See  for more.', 'Its flavor text: "Me too."']
