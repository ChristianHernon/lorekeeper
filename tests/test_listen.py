import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import commands, listen  # noqa: E402

FRAME = listen.FRAME


def test_wake_word():
    assert listen.wake('Lorekeeper, what does this do?') == 'what does this do?'
    assert listen.wake('Hey Lore Keeper what synergy did I just get') == 'what synergy did I just get'
    assert listen.wake('Lord Keeper. Who is Ranni?') == 'Who is Ranni?'
    assert listen.wake('Lorekeeper.') == ''
    assert listen.wake('push left, I got the boss') is None
    assert listen.wake('the goalkeeper was great') is None


def frames(level, n, seed=0):
    rng = np.random.default_rng(seed)
    return [(rng.standard_normal(FRAME) * level).astype('float32') for _ in range(n)]


def test_segmenter_finds_one_utterance_in_noise():
    seg = listen.Segmenter()
    out = [seg.feed(f) for f in frames(0.002, 60) + frames(0.1, 40, 1) + frames(0.002, 40, 2)]
    clips = [c for c in out if c is not None]
    assert len(clips) == 1
    assert 40 * FRAME <= len(clips[0]) <= 60 * FRAME   # the speech, a little lead-in, little tail


def test_segmenter_ignores_a_click_and_adapts_to_hum():
    seg = listen.Segmenter()
    hum = frames(0.01, 700)   # a loud fan, longer than the 15 s cap: never an utterance
    assert all(seg.feed(f) is None for f in hum[:100] + frames(0.2, 2, 3) + hum[100:])
    assert seg.cur is None
    out = [seg.feed(f) for f in frames(0.15, 40, 4) + frames(0.01, 40, 5)]   # speech over the fan still counts
    assert sum(c is not None for c in out) == 1


def test_listen_commands():
    assert commands.parse('Stop listening.') == ('listen_off', '')
    assert commands.parse('listen mode on') == ('listen_on', '')
