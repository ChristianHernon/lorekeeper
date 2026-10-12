"""Hold-to-talk hotkey through a low-level keyboard hook (WH_KEYBOARD_LL): it fires in exclusive-fullscreen games too.
If a game runs as administrator, Lorekeeper must too, or Windows keeps that game's keys from it."""
import ctypes, sys, threading

VK = {'ctrl': 0x11, 'alt': 0x12, 'shift': 0x10, 'win': 0x5B, 'space': 0x20, 'esc': 0x1B, 'tab': 0x09,
      'backquote': 0xC0, '`': 0xC0, 'capslock': 0x14, **{f'f{i}': 0x6F + i for i in range(1, 25)}}
MOD_KEYS = {'ctrl': (0xA2, 0xA3, 0x11), 'alt': (0xA4, 0xA5, 0x12), 'shift': (0xA0, 0xA1, 0x10), 'win': (0x5B, 0x5C)}


def parse(combo):
    """"ctrl+alt+g" -> ({'ctrl', 'alt'}, 0x47)."""
    parts = [p.strip().lower() for p in combo.split('+') if p.strip()]
    mods, key = {p for p in parts[:-1]}, parts[-1]
    if not parts or mods - set(MOD_KEYS):
        raise ValueError(f'bad hotkey: {combo}')
    vk = VK.get(key) or (ord(key.upper()) if len(key) == 1 and key.isalnum() else None)
    if vk is None:
        raise ValueError(f'bad hotkey key: {key}')
    return mods, vk


class Hotkey:
    """on_down() when the combo goes down, on_up() when its key comes up, on_cancel() for Esc while held."""

    def __init__(self, combo, on_down, on_up, on_cancel=lambda: None):
        self.mods, self.vk = parse(combo)
        self.on_down, self.on_up, self.on_cancel = on_down, on_up, on_cancel
        self.held, self.down = False, set()

    def _mods_down(self):
        return all(any(k in self.down for k in MOD_KEYS[m]) for m in self.mods)

    def _event(self, vk, up):
        """True = swallow the key (the game never sees our hotkey's letter)."""
        (self.down.discard if up else self.down.add)(vk)
        if vk == self.vk:
            if not up and not self.held and self._mods_down():
                self.held = True
                threading.Thread(target=self.on_down, daemon=True).start()
                return True
            if up and self.held:
                self.held = False
                threading.Thread(target=self.on_up, daemon=True).start()
                return True
            return self.held   # key repeat while held
        if vk == 0x1B and not up and self.held:
            self.held = False
            threading.Thread(target=self.on_cancel, daemon=True).start()
            return True
        return False

    def run(self):
        """Blocks: installs the hook and pumps messages. Run it on its own thread."""
        from ctypes import wintypes as W
        user32 = ctypes.windll.user32

        class KB(ctypes.Structure):
            _fields_ = [('vkCode', W.DWORD), ('scanCode', W.DWORD), ('flags', W.DWORD), ('time', W.DWORD), ('dwExtraInfo', ctypes.c_size_t)]
        LRESULT = ctypes.c_ssize_t
        HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, W.WPARAM, W.LPARAM)
        user32.CallNextHookEx.argtypes = [W.HHOOK, ctypes.c_int, W.WPARAM, W.LPARAM]
        user32.CallNextHookEx.restype = LRESULT
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, W.HINSTANCE, W.DWORD]
        user32.SetWindowsHookExW.restype = W.HHOOK

        def proc(code, wparam, lparam):
            if code == 0:
                kb = ctypes.cast(lparam, ctypes.POINTER(KB)).contents
                if not kb.flags & 0x10:   # LLKHF_INJECTED: ignore keys apps type for us
                    try:
                        if self._event(kb.vkCode, wparam in (0x0101, 0x0105)):   # WM_KEYUP, WM_SYSKEYUP
                            return 1
                    except Exception as e:
                        print('hotkey:', e, file=sys.stderr)
            return user32.CallNextHookEx(None, code, wparam, lparam)
        self._proc = HOOKPROC(proc)   # keep a reference, or it is collected and the hook crashes
        if not user32.SetWindowsHookExW(13, self._proc, None, 0):   # WH_KEYBOARD_LL
            raise OSError('could not install the keyboard hook')
        msg = W.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
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
    keys = [MOD_KEYS[m][-1] for m in sorted(mods)] + [vk]
    seq = [(k, 0) for k in keys] + [(k, 2) for k in reversed(keys)]   # 2 = KEYEVENTF_KEYUP
    arr = (INPUT * len(seq))(*[INPUT(type=1, ki=KI(wVk=k, dwFlags=f)) for k, f in seq])
    ctypes.windll.user32.SendInput(len(seq), arr, ctypes.sizeof(INPUT))
