import os, sys, tempfile
os.environ.setdefault('LOREKEEPER_DIR', tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import capture  # noqa: E402

# 10 min of long frames every 10 s, then 5 recent at 1 s, ending at t=600
FRAMES = [(float(t), b'x%d' % t) for t in range(0, 591, 10)] + [(float(t), b'y%d' % t) for t in range(596, 601)]


def times(picked):
    return [t for t, _ in picked]


def test_pick_now_just_and_ago():
    assert times(capture.Screen.pick(FRAMES, 'what is this')) == [600]
    assert times(capture.Screen.pick(FRAMES, 'what synergy did I just get')) == [597, 598, 599, 600]
    assert times(capture.Screen.pick(FRAMES, 'what did that sign say two minutes ago')) == [470, 480, 490, 600]
    assert times(capture.Screen.pick(FRAMES, 'the item from 30 seconds ago')) == [560, 570, 580, 600]


def test_pick_earlier_spreads_over_history():
    t = times(capture.Screen.pick(FRAMES, 'what was that chest earlier'))
    assert len(t) == 7 and t[-1] == 600 and t[0] < 200 and t == sorted(t)


def test_wants_time_words():
    assert capture.wants('what did the sign say a few minutes ago')
    assert capture.wants('what was the code I saved')
    assert not capture.wants('who is Ranni')


def test_saved_screens():
    d = tempfile.mkdtemp()
    g = {'name': 'Elden Ring'}
    capture.save_shot(d, g, b'jpg', 'the vault code')
    capture.save_shot(d, g, b'jpg', '')
    hit = capture.saved_for(d, g, 'what was the vault code')
    assert len(hit) == 1 and 'vault code' in hit[0][1]
    assert len(capture.saved_for(d, g, 'what did the screen I saved say')) == 2
    assert capture.saved_for(d, g, 'who is Ranni') == []


def test_relevant_keeps_the_asked_section():
    import lookup
    lead = '{{Quest infobox | name = Family Matters}}\nThe Baron asks Geralt to find his family.\n'
    filler = '\n'.join(f'== Step {i} ==\n' + ('Geralt follows the trail through the woods. ' * 40) for i in range(8))
    late = '== The botchling ==\nGeralt can kill the botchling or lift the curse: the Baron must carry it to the old house.\n'
    page = lead + filler + late + '== Rewards ==\n' + 'XP. ' * 300
    out = lookup.relevant(page, 'I found the Botchling under the house, what should I do with it?')
    assert out.startswith(lead.strip()[:20]) and 'lift the curse' in out and len(out) <= 5000
    assert lookup.relevant('short page', 'anything') == 'short page'
