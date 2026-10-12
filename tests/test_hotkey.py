import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hotkey  # noqa: E402

CTRL, ALT, SPACE, M4 = 0xA2, 0xA4, 0x20, 0x05


def make(combo, active=True):
    ev = []
    h = hotkey.Hotkey(combo, lambda: ev.append('down'), lambda: ev.append('up'), lambda: ev.append('cancel'), lambda: active)
    h._fire = lambda f, *a: f(*a)   # no threads in tests
    return h, ev


def test_parse_and_names():
    assert hotkey.parse('ctrl+alt+space') == ({'ctrl', 'alt'}, SPACE)
    assert hotkey.parse('mouse4') == (set(), M4)
    assert hotkey.name({'alt', 'ctrl'}, SPACE) == 'ctrl+alt+space'
    assert hotkey.pretty('ctrl+alt+space') == 'Ctrl+Alt+Space' and hotkey.pretty('mouse5') == 'Mouse 5' and hotkey.pretty('f13') == 'F13'


def test_combo_fires_and_swallows():
    h, ev = make('ctrl+alt+space')
    assert not h._event(CTRL, False) and not h._event(ALT, False)
    assert h._event(SPACE, False) and h._event(SPACE, False)   # repeat swallowed too
    assert h._event(SPACE, True)
    assert ev == ['down', 'up']
    h._event(ALT, True)
    assert not h._event(SPACE, False)   # ctrl+space alone: not ours


def test_not_in_game_passes_through():
    h, ev = make('ctrl+alt+space', active=False)
    h._event(CTRL, False), h._event(ALT, False)
    assert not h._event(SPACE, False) and not h._event(SPACE, True) and ev == []


def test_mouse_button_allows_shift_held():
    h, ev = make('mouse4')
    h._event(0xA0, False)   # sprinting with shift
    assert h._event(M4, False) and h._event(M4, True) and ev == ['down', 'up']


def test_record_new_hotkey():
    h, _ = make('ctrl+alt+space')
    got = []
    h.recording = got.append
    h._event(CTRL, False)
    assert h._event(ord('Q'), False) and h._event(ord('Q'), True)   # the press and its release are swallowed
    assert got == ['ctrl+q'] and h.combo == 'ctrl+q'
    h._event(CTRL, True)
    h.recording = got.append
    assert not h._event(0x01, False)   # left click ignored while recording
    assert h._event(M4, False) and got[-1] == 'mouse4'
