"""Lorekeeper's pixel art: the open-book mascot from docs/img, for the tray and the Start menu shortcut. Each size is
drawn from a pixel grid and only ever scaled by whole numbers, so it stays crisp. `python art.py` rewrites assets/*.ico."""
import ctypes, os

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')
ICO = {False: os.path.join(ASSETS, 'lorekeeper.ico'), True: os.path.join(ASSETS, 'lorekeeper-listening.ico')}

# the landing page's palette (docs/index.html); listen mode turns the crimson cover sky blue
PALETTE = {'n': '#0b0b2b', 'w': '#f2efe6', 'b': '#2f6bff', 'g': '#bfb8a6', 'r': '#e0284f', 'd': '#8a1636', 'p': '#7a3cff', 's': '#49c6ff'}
LISTENING = {'r': '#49c6ff', 'd': '#2f6bff', 'p': '#2f6bff'}

BOOK16 = (   # docs/img/favicon.svg
    '................',
    '.nnnnnn..nnnnnn.',
    'nwwwwwwnnwwwwwwn',
    'nwbbbbwnnwbbbbwn',
    'nwwwwwwnnwwwwwwn',
    'nwbbbwwnnwbbbwwn',
    'nwwwwwwnnwwwwwwn',
    'nwbbbbwnnwbbbbwn',
    'nwwwwwwnnwwwwwwn',
    'ngwwwwwnnwwwwwgn',
    'nrggggwnnwggggrn',
    'nrrnnnnnnnnnnrrn',
    'nrrrrrrrrrrrrrrn',
    '.nnnnnnnnnnnnnn.',
    '................',
    '................',
)
BOOK20 = (   # the favicon with wider pages and a fourth line, for 125% scaling
    '....................',
    '....................',
    '.nnnnnnnn..nnnnnnnn.',
    'nwwwwwwwwnnwwwwwwwwn',
    'nwbbbbbbwnnwbbbbbbwn',
    'nwwwwwwwwnnwwwwwwwwn',
    'nwbbbbwwwnnwbbbbbwwn',
    'nwwwwwwwwnnwwwwwwwwn',
    'nwbbbbbbwnnwbbbbbbwn',
    'nwwwwwwwwnnwwwwwwwwn',
    'nwbbbbbwwnnwbbbbwwwn',
    'ngwwwwwwwnnwwwwwwwgn',
    'nrgggggwwnnwwgggggrn',
    'nrrnnnnnnnnnnnnnnrrn',
    'nrrrrrrrrrrrrrrrrrrn',
    '.nnnnnnnnnnnnnnnnnn.',
    '....................',
    '....................',
    '....................',
    '....................',
)
MASCOT = (   # docs/img/book.svg, 24 x 18; the first three rows are its sparkles
    '..........s.....s.......',
    '......s..........s....s.',
    '..........s.............',
    '..nnnnnnnn....nnnnnnnn..',
    '.nwwwwwwwwn..nwwwwwwwwn.',
    '.nwbbbbbwwwnnwwbbbbbwwn.',
    '.nwwwwwwwwwnnwwwwwwwwwn.',
    '.nwbbbbbbwwnnwwbbbbbbwn.',
    '.nwwwwwwwwwnnwwwwwwwwwn.',
    '.nwbbbbwwwwnnwwbbbbwwwn.',
    '.nwwwwwwwwwnnwwwwwwwwwn.',
    '.nwbbbbbwwwnnwwpppppwwn.',
    '.ngwwwwwwwwnnwwwwwwwwgn.',
    'nrngggwwwwwnnwwwwwgggnrn',
    'nrrnnnggggwnnwggggnnnrrn',
    'nrrrrrnnnnnnnnnnnnrrrrrn',
    '.nndddrrrrrrrrrrrrdddnn.',
    '....nnnnnnnnnnnnnnnn....',
)
BOOK24 = ('',) * 4 + MASCOT[3:] + ('',) * 5   # the mascot without sparkles: single stray pixels read as dirt on a taskbar

# size: (grid, scale). Tray sizes are 16/20/24/32 at 100/125/150/200% scaling.
SIZES = {16: (BOOK16, 1), 20: (BOOK20, 1), 24: (BOOK24, 1), 32: (BOOK16, 2), 40: (BOOK20, 2), 48: (BOOK24, 2),
         64: (BOOK16, 4), 128: (MASCOT, 5), 256: (MASCOT, 10)}


def image(size, listening=False):
    """The book as an RGBA PIL image, size x size, pixel-exact."""
    from PIL import Image, ImageDraw
    grid, k = SIZES[size]
    pal = {**PALETTE, **(LISTENING if listening else {})}
    w, h = max(len(r) for r in grid) * k, len(grid) * k
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ox, oy = (size - w) // 2, (size - h) // 2
    for y, row in enumerate(grid):
        for x, c in enumerate(row):
            if c != '.':
                d.rectangle((ox + x * k, oy + y * k, ox + x * k + k - 1, oy + y * k + k - 1), fill=pal[c])
    return img


def build():
    """Write assets/lorekeeper.ico and lorekeeper-listening.ico with a hand-drawn frame for every size."""
    for listening, path in ICO.items():
        frames = [image(s, listening) for s in sorted(SIZES)]
        frames[-1].save(path, format='ICO', sizes=[f.size for f in frames], append_images=frames[:-1])


def tray_size():
    """The notification-area icon size in physical pixels, even for a DPI-unaware process."""
    try:
        u = ctypes.WinDLL('user32')
        u.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
        u.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        old = u.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))   # per-monitor v2, just long enough to ask
        try:
            return u.GetSystemMetricsForDpi(49, u.GetDpiForSystem())   # SM_CXSMICON
        finally:
            if old:
                u.SetThreadDpiAwarenessContext(ctypes.c_void_p(old))
    except Exception:
        return 16


def tray_icon(pystray, *args):
    """A pystray Icon showing the book. pystray on its own lets Windows shrink a 32px frame, which blurs the pixel art;
    this one loads the frame drawn for the tray's exact size. Set .listening to switch to the listen-mode book."""
    class Icon(pystray.Icon):
        _listening = False
        on_click = None   # set to open Lorekeeper's own pixel menu; the native menu is the fallback

        def _on_notify(self, wparam, lparam):
            if self.on_click and lparam in (0x0202, 0x0205):   # WM_LBUTTONUP, WM_RBUTTONUP
                try:
                    return self.on_click()
                except Exception as e:
                    print('panel:', e)
            return super()._on_notify(wparam, lparam)

        @property
        def listening(self):
            return self._listening

        @listening.setter
        def listening(self, on):
            if on != self._listening:
                self._listening = on
                self.icon = image(64, on)   # pystray reloads the handle below when the image changes

        def _assert_icon_handle(self):
            if self._icon_handle:
                return
            try:
                u = ctypes.WinDLL('user32')
                u.LoadImageW.restype = ctypes.c_void_p
                u.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
                n = tray_size()
                self._icon_handle = u.LoadImageW(None, ICO[self._listening], 1, n, n, 0x10)   # IMAGE_ICON, LR_LOADFROMFILE
            except Exception:
                self._icon_handle = None
            if not self._icon_handle:
                super()._assert_icon_handle()

    return Icon(args[0], image(64), *args[1:])


if __name__ == '__main__':
    build()
    print('\n'.join(ICO.values()))
