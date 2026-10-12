"""The tray menu, drawn like the landing page: Windows' own menu can't take the site's fonts or colours, so a click on the
tray book opens this pixel panel instead (the native menu stays as the fallback).

Rows are Items: an action, an on/off switch (check), a radio choice, or a page of more Items (sub). Mouse and keys both
work: ↑↓ move, Enter/Space choose, → opens a page, ← / Backspace goes back, Esc or a click elsewhere closes. Switches
and radio choices keep the panel open (it's a settings panel); actions close it."""
import tkinter as tk
import tkinter.font as tkfont
import box as boxmod
from box import BG, INK, DIM, PINK, SKY, GOLD, INDIGO, LILAC, SHADOW, KEY, PX

W = 340
ROW = 30
HOVER = '#1b1452'


class Item:
    def __init__(self, label, action=None, check=None, radio=None, sub=None, enabled=True, header=False, note=None):
        self.label, self.action, self.check, self.radio, self.sub = label, action, check, radio, sub
        self.enabled, self.header, self.note = enabled, header, note

    def text(self):
        return self.label() if callable(self.label) else self.label

    def is_enabled(self):
        return self.enabled() if callable(self.enabled) else self.enabled

    def selectable(self):
        return not self.header and self.is_enabled() and bool(self.action or self.sub)


class Panel:
    """Panel(root, items_fn, status_fn): items_fn() -> [Item] for the top page; status_fn() -> (playing, hotkey) lines."""

    def __init__(self, root, items_fn, status_fn):
        self.root, self.items_fn, self.status_fn = root, items_fn, status_fn
        self.win = None

    # any thread
    def open(self, x=None, y=None):
        self.root.after(0, lambda: self._open(x, y))

    # Tk thread
    def _open(self, x, y):
        if self.win:
            self._close()
        self.stack = [('MENU', self.items_fn)]   # pages: (title, items function)
        self.sel = None
        w = self.win = tk.Toplevel(self.root)
        w.withdraw()
        w.overrideredirect(True)
        w.attributes('-topmost', True)
        try:
            w.attributes('-transparentcolor', KEY)
            bg = KEY
        except tk.TclError:
            bg = SHADOW
        w.configure(bg=bg)
        have = set(tkfont.families(self.root))
        pixel = 'VT323' if 'VT323' in have else 'Consolas'
        self.f_head = ('Press Start 2P', -8) if 'Press Start 2P' in have else ('Consolas', -11, 'bold')
        self.f_row = (pixel, -22 if pixel == 'VT323' else -14)
        self.f_small = (pixel, -18 if pixel == 'VT323' else -12)
        self.c = tk.Canvas(w, bg=bg, highlightthickness=0, bd=0)
        self.c.pack()
        self.c.bind('<Motion>', self._hover)
        self.c.bind('<Button-1>', self._click)
        self.c.bind('<Leave>', lambda e: self._set_sel(None))
        for k, f in (('<Escape>', lambda e: self._close()), ('<Up>', lambda e: self._move(-1)), ('<Down>', lambda e: self._move(1)),
                     ('<Return>', lambda e: self._choose()), ('<space>', lambda e: self._choose()), ('<Right>', lambda e: self._choose(True)),
                     ('<Left>', lambda e: self._back()), ('<BackSpace>', lambda e: self._back())):
            w.bind(k, f)
        self.had_focus, self.away = False, 0
        w.bind('<FocusIn>', lambda e: setattr(self, 'had_focus', True))
        w.bind('<FocusOut>', lambda e: self.root.after(120, self._maybe_close))
        self.c.bind('<Enter>', lambda e: setattr(self, 'away', 0), add='+')
        self._draw()
        w.update_idletasks()
        cw, ch = self.c.winfo_reqwidth(), self.c.winfo_reqheight()
        if x is None:
            x, y = w.winfo_pointerx(), w.winfo_pointery()
        sx, sy = w.winfo_screenwidth(), w.winfo_screenheight()
        px = min(max(0, x - cw + 8), sx - cw)
        py = y - ch - 6 if y - ch - 6 > 0 else min(y + 6, sy - ch)   # above the cursor (the tray is at the bottom), else below
        w.geometry(f'+{px}+{py}')
        w.deiconify()
        w.lift()
        try:   # a tray click lets this process take the foreground; without it Esc and click-away can't work
            import ctypes
            ctypes.windll.user32.SetForegroundWindow(int(w.frame(), 16))
        except Exception:
            pass
        w.focus_force()
        self.root.after(1000, self._watch)

    def _maybe_close(self):
        if self.win and self.had_focus and self.win.focus_get() is None:
            self._close()

    def _watch(self):
        """If the panel never got focus (Windows can refuse), close it once the mouse has been away from it for 4 s."""
        if not self.win:
            return
        x, y = self.win.winfo_pointerx(), self.win.winfo_pointery()
        wx, wy = self.win.winfo_rootx(), self.win.winfo_rooty()
        inside = wx <= x < wx + self.win.winfo_width() and wy <= y < wy + self.win.winfo_height()
        self.away = 0 if inside else self.away + 1
        if self.away >= 4 and not self.had_focus:
            return self._close()
        self.root.after(1000, self._watch)

    def _close(self):
        if self.win:
            self.win.destroy()
            self.win = None

    # drawing
    def _items(self):
        title, fn = self.stack[-1]
        items = fn()
        if len(self.stack) > 1:
            items = [Item('< Back', action=self._back)] + items
        return title, items

    def _draw(self):
        c = self.c
        c.delete('all')
        title, items = self._items()
        self.rows = []   # (y0, y1, item)
        x0, y0 = PX, PX
        x1 = x0 + W
        y = y0 + 14
        self._pixels(('..x..', '.xxx.', 'xxxxx', '.xxx.', '..x..'), x0 + 18, y, 2, LILAC)
        c.create_text(x0 + 34, y + 1, text='LOREKEEPER' if len(self.stack) == 1 else title, font=self.f_head, fill=LILAC, anchor='nw')
        y += 20
        if len(self.stack) == 1:
            playing, key = self.status_fn()
            c.create_text(x0 + 18, y, text=playing, font=self.f_row, fill=SKY, anchor='nw', width=W - 36)
            y = c.bbox('all')[3] + 2
            c.create_text(x0 + 18, y, text=key, font=self.f_small, fill=DIM, anchor='nw', width=W - 36)
            y = c.bbox('all')[3] + 10
        rule_y = y
        y += PX + 6
        for it in items:
            if it.header:
                y += 12
                c.create_text(x0 + 18, y + 4, text=it.text(), font=self.f_head, fill=PINK, anchor='nw')
                y += 22
                continue
            top = y
            on = it.is_enabled()
            c.create_rectangle(x0 + 4, top, x1 - 4, top + ROW, fill=BG, width=0, tags=(f'bg{len(self.rows)}', 'rowbg'))
            label = it.text()
            c.create_text(x0 + 18, top + ROW // 2, text=label, font=self.f_row, fill=INK if on else DIM, anchor='w',
                          tags=(f'tx{len(self.rows)}',))
            right = x1 - 16
            if it.check is not None:
                self._switch(right - 34, top + 8, bool(it.check()), on)
            elif it.radio is not None:
                self._radio(right - 12, top + 10, bool(it.radio()))
            elif it.sub is not None:
                self._pixels(('x..', 'xx.', 'xxx', 'xx.', 'x..'), right - 8, top + 10, 2, LILAC)
            elif it.note:
                c.create_text(right, top + ROW // 2, text=it.note() if callable(it.note) else it.note, font=self.f_small, fill=DIM, anchor='e')
            self.rows.append((top, top + ROW, it))
            y += ROW
        y1 = y + 10
        under = [c.create_rectangle(x0 + dx, y0 + dy, x1 + dx, y1 + dy, fill=SHADOW, width=0) for dx, dy in ((2 * PX, 3 * PX), (3 * PX, 2 * PX))]
        under += [c.create_rectangle(*r, fill=INK, width=0) for r in ((x0, 0, x1, y0), (x0, y1, x1, y1 + PX), (0, y0, x0, y1), (x1, y0, x1 + PX, y1))]
        under += [c.create_rectangle(x0, y0, x1, y1, fill=BG, width=0), c.create_rectangle(x0, rule_y, x1, rule_y + PX, fill=INDIGO, width=0)]
        for item in reversed(under):
            c.tag_lower(item)
        c.config(width=x1 + 3 * PX, height=y1 + 3 * PX)
        if self.sel is not None and self.sel < len(self.rows):
            self._paint(self.sel, True)

    def _pixels(self, grid, x, y, k, colour, tags=()):
        for j, row in enumerate(grid):
            for i, ch in enumerate(row):
                if ch == 'x':
                    self.c.create_rectangle(x + i * k, y + j * k, x + i * k + k, y + j * k + k, fill=colour, width=0, tags=tags)

    def _switch(self, x, y, on, enabled):
        """A pixel toggle: sky with the knob right when on, indigo with it left when off."""
        c = self.c
        c.create_rectangle(x, y, x + 34, y + 14, fill=(SKY if on else INDIGO) if enabled else '#2a2550', outline=INK, width=2)
        kx = x + 20 if on else x + 2
        c.create_rectangle(kx + 1, y + 3, kx + 11, y + 11, fill=INK if enabled else DIM, width=0)

    def _radio(self, x, y, on):
        self.c.create_rectangle(x, y, x + 10, y + 10, outline=LILAC, width=2)
        if on:
            self.c.create_rectangle(x + 3, y + 3, x + 7, y + 7, fill=GOLD, width=0)

    # input
    def _row_at(self, y):
        return next((i for i, (a, b, it) in enumerate(self.rows) if a <= y < b and it.selectable()), None)

    def _paint(self, i, on):
        self.c.itemconfig(f'bg{i}', fill=HOVER if on else BG)
        it = self.rows[i][2]
        self.c.itemconfig(f'tx{i}', fill=GOLD if on else (INK if it.is_enabled() else DIM))

    def _set_sel(self, i):
        if i == self.sel:
            return
        if self.sel is not None and self.sel < len(self.rows):
            self._paint(self.sel, False)
        self.sel = i
        if i is not None:
            self._paint(i, True)

    def _hover(self, e):
        self._set_sel(self._row_at(e.y))

    def _click(self, e):
        i = self._row_at(e.y)
        if i is not None:
            self.sel = i
            self._choose()

    def _move(self, d):
        ok = [i for i, (_, _, it) in enumerate(self.rows) if it.selectable()]
        if not ok:
            return
        cur = ok.index(self.sel) if self.sel in ok else (-1 if d > 0 else 0)
        self._set_sel(ok[(cur + d) % len(ok)])

    def _choose(self, only_pages=False):
        if self.sel is None:
            return
        it = self.rows[self.sel][2]
        if it.sub is not None:
            self.stack.append((it.text().upper(), it.sub))
            self.sel = None
            self._draw()
            return
        if only_pages or not it.action:
            return
        keep = it.check is not None or it.radio is not None or it.action == self._back
        if not keep:
            self._close()
        try:
            it.action()
        except Exception as e:
            print('menu:', e)
        if keep and self.win:
            self._draw()

    def _back(self):
        if len(self.stack) > 1:
            self.stack.pop()
            self.sel = None
            self._draw()
