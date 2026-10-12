"""Hold-to-talk hotkey through low-level keyboard and mouse hooks (WH_KEYBOARD_LL, WH_MOUSE_LL): they fire in
exclusive-fullscreen games too. Any key or mouse side button, with or without modifiers; set it from the tray.
If a game runs as administrator, Lorekeeper must too, or Windows keeps that game's input from it."""
import ctypes, sys, threading

VK = {'space': 0x20, 'esc': 0x1B, 'tab': 0x09, 'enter': 0x0D, 'backspace': 0x08, 'capslock': 0x14, '`': 0xC0, 'backquote': 0xC0,
      'insert': 0x2D, 'delete': 0x2E, 'home': 0x24, 'end': 0x23, 'pageup': 0x21, 'pagedown': 0x22, 'pause': 0x13, 'scrolllock': 0x91,
      'mouse3': 0x04, 'mouse4': 0x05, 'mouse5': 0x06,
      **{f'f{i}': 0x6F + i for i in range(1, 25)}, **{f'num{i}': 0x60 + i for i in range(10)},
      '-': 0xBD, '=': 0xBB, '[': 0xDB, ']': 0xDD, ';': 0xBA, "'": 0xDE, ',': 0xBC, '.': 0xBE, '/': 0xBF, '\\': 0xDC}
NAME = {v: k for k, v in reversed(list(VK.items()))}   # first name wins ('`' over 'backquote')
MOD_KEYS = {'ctrl': (0xA2, 0xA3, 0x11), 'alt': (0xA4, 0xA5, 0x12), 'shift': (0xA0, 0xA1, 0x10), 'win': (0x5B, 0x5C)}
MOD_OF = {vk: m for m, vks in MOD_KEYS.items() for vk in vks}
ORDER = ['ctrl', 'alt', 'shift', 'win']


def parse(combo):
    """"ctrl+alt+space" -> ({'ctrl', 'alt'}, 0x20). "mouse4" -> (set(), 0x05)."""
    parts = [p.strip().lower() for p in combo.replace(' ', '').split('+') if p.strip()]
    if not parts:
        raise ValueError('empty hotkey')
    mods, key = set(parts[:-1]), parts[-1]
    if mods - set(MOD_KEYS):
        raise ValueError(f'bad hotkey: {combo}')
    vk = VK.get(key) or (ord(key.upper()) if len(key) == 1 and key.isalnum() else None)
    if vk is None:
        raise ValueError(f'bad hotkey key: {key}')
    return mods, vk


def name(mods, vk):
    key = NAME.get(vk) or (chr(vk).lower() if 0x30 <= vk <= 0x5A else f'vk{vk}')
    return '+'.join([m for m in ORDER if m in mods] + [key])


def pretty(combo):
    """"ctrl+alt+space" -> "Ctrl+Alt+Space", "mouse4" -> "Mouse 4"."""
    return '+'.join(p.replace('mouse', 'Mouse ').title() if p.startswith('mouse') else p.upper() if len(p) <= 3 and p[0] == 'f' else p.title()
                    for p in combo.split('+'))


class Hotkey:
    """on_down() when the combo goes down, on_up() when its key comes up, on_cancel() for Esc while held.
    active(): is it ours right now? When not (no game in front), the key passes through, e.g. to Atticus on the same combo."""

    def __init__(self, combo, on_down, on_up, on_cancel=lambda: None, active=lambda: True):
        self.set(combo)
        self.on_down, self.on_up, self.on_cancel, self.active = on_down, on_up, on_cancel, active
        self.held, self.down, self.recording = False, set(), None

    def set(self, combo):
        self.mods, self.vk = parse(combo)
        self.combo = name(self.mods, self.vk)
        self._mouse_update()

    def record(self, done):
        """The next key or mouse button pressed (with its modifiers) becomes the hotkey; done(combo or None for Esc)."""
        def finish(combo):
            self._mouse_update()
            done(combo)
        self.recording = finish
        self._mouse_update()

    def _wants_mouse(self):
        return self.vk in (0x04, 0x05, 0x06) or bool(getattr(self, 'recording', None))

    def _mouse_update(self):
        """The mouse hook sees every mouse move, so it is only on while a mouse button is (or may become) the hotkey."""
        tid = getattr(self, '_tid', None)
        if tid:
            ctypes.windll.user32.PostThreadMessageW(tid, 0x8001, 0, 0)   # WM_APP+1: the hook thread re-checks

    def _mods_down(self):
        return {m for m, vks in MOD_KEYS.items() if any(k in self.down for k in vks)}

    def _fire(self, f, *a):
        threading.Thread(target=f, args=a, daemon=True).start()

    def _event(self, vk, up):
        """True = swallow it (the game never sees our hotkey)."""
        (self.down.discard if up else self.down.add)(vk)
        if self.recording and not up and vk not in MOD_OF:
            done, self.recording = self.recording, None
            if vk == 0x1B:
                self._fire(done, None)
            elif vk in (0x01, 0x02):   # left/right click can't be the hotkey
                self.recording = done
                return False
            else:
                self.set(name(self._mods_down(), vk))
                self._fire(done, self.combo)
            self._swallow_up = vk
            return True
        if up and getattr(self, '_swallow_up', None) == vk:
            self._swallow_up = None
            return True
        if vk == self.vk:
            if not up and not self.held and self._mods_down() >= self.mods and (not self.mods or self._mods_down() == self.mods):
                if not self.active():
                    return False
                self.held = True
                self._fire(self.on_down)
                return True
            if up and self.held:
                self.held = False
                self._fire(self.on_up)
                return True
            return self.held   # key repeat while held
        if vk == 0x1B and not up and self.held:
            self.held = False
            self._fire(self.on_cancel)
            return True
        return False

    def run(self):
        """Blocks: installs both hooks and pumps messages. Run it on its own thread."""
        from ctypes import wintypes as W
        user32 = ctypes.windll.user32

        class KB(ctypes.Structure):
            _fields_ = [('vkCode', W.DWORD), ('scanCode', W.DWORD), ('flags', W.DWORD), ('time', W.DWORD), ('dwExtraInfo', ctypes.c_size_t)]

        class MS(ctypes.Structure):
            _fields_ = [('pt', W.POINT), ('mouseData', W.DWORD), ('flags', W.DWORD), ('time', W.DWORD), ('dwExtraInfo', ctypes.c_size_t)]
        LRESULT = ctypes.c_ssize_t
        HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, W.WPARAM, W.LPARAM)
        user32.CallNextHookEx.argtypes = [W.HHOOK, ctypes.c_int, W.WPARAM, W.LPARAM]
        user32.CallNextHookEx.restype = LRESULT
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, W.HINSTANCE, W.DWORD]
        user32.SetWindowsHookExW.restype = W.HHOOK

        def keys(code, wparam, lparam):
            if code == 0:
                kb = ctypes.cast(lparam, ctypes.POINTER(KB)).contents
                if not kb.flags & 0x10:   # LLKHF_INJECTED: ignore keys apps type, ours included
                    try:
                        if self._event(kb.vkCode, wparam in (0x0101, 0x0105)):   # WM_KEYUP, WM_SYSKEYUP
                            return 1
                    except Exception as e:
                        print('hotkey:', e, file=sys.stderr)
            return user32.CallNextHookEx(None, code, wparam, lparam)

        BUTTONS = {0x0201: (0x01, False), 0x0202: (0x01, True), 0x0204: (0x02, False), 0x0205: (0x02, True),
                   0x0207: (0x04, False), 0x0208: (0x04, True)}   # left, right, middle down/up

        def mouse(code, wparam, lparam):
            if code == 0:
                ms = ctypes.cast(lparam, ctypes.POINTER(MS)).contents
                hit = BUTTONS.get(wparam)
                if wparam in (0x020B, 0x020C):   # side buttons: which one is in mouseData's high word
                    hit = (0x05 if ms.mouseData >> 16 == 1 else 0x06, wparam == 0x020C)
                if hit and not ms.flags & 0x01:   # LLMHF_INJECTED
                    try:
                        if self._event(*hit):
                            return 1
                    except Exception as e:
                        print('hotkey:', e, file=sys.stderr)
            return user32.CallNextHookEx(None, code, wparam, lparam)
        self._procs = HOOKPROC(keys), HOOKPROC(mouse)   # keep references, or they are collected and the hooks crash
        if not user32.SetWindowsHookExW(13, self._procs[0], None, 0):
            raise OSError('could not install the keyboard hook')
        user32.UnhookWindowsHookEx.argtypes = [W.HHOOK]
        mhook = None

        def sync():
            nonlocal mhook
            if self._wants_mouse() and not mhook:
                mhook = user32.SetWindowsHookExW(14, self._procs[1], None, 0)
            elif not self._wants_mouse() and mhook:
                user32.UnhookWindowsHookEx(mhook)
                mhook = None
        msg = W.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)   # this thread now has a queue for PostThreadMessage
        self._tid = ctypes.windll.kernel32.GetCurrentThreadId()
        sync()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == 0x8001:
                sync()
                continue
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))


def press(combo):
    """Types a key combo through SendInput (Steam's clip key, Game Bar's Win+Alt+G). The hook ignores injected keys."""
    from ctypes import wintypes as W
    mods, vk = parse(combo)

    class KI(ctypes.Structure):
        _fields_ = [('wVk', W.WORD), ('wScan', W.WORD), ('dwFlags', W.DWORD), ('time', W.DWORD), ('dwExtraInfo', ctypes.c_size_t)]

    class INPUT(ctypes.Structure):
        class _U(ctypes.Union):
            _fields_ = [('ki', KI), ('pad', ctypes.c_byte * 32)]
        _anonymous_ = ('u',)
        _fields_ = [('type', W.DWORD), ('u', _U)]
    keys = [MOD_KEYS[m][-1] for m in ORDER if m in mods] + [vk]
    seq = [(k, 0) for k in keys] + [(k, 2) for k in reversed(keys)]   # 2 = KEYEVENTF_KEYUP
    arr = (INPUT * len(seq))(*[INPUT(type=1, ki=KI(wVk=k, dwFlags=f)) for k, f in seq])
    ctypes.windll.user32.SendInput(len(seq), arr, ctypes.sizeof(INPUT))
