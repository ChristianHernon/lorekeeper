"""A small always-on-top box with the question and answer. It goes on a second monitor when there is one, since an
exclusive-fullscreen game covers its own screen. Click it to copy the answer. Tk lives on the main thread; other threads post."""
import queue, tkinter as tk
import win

BG, FG, DIM = '#16161c', '#f2efe6', '#9a968c'


class Box:
    def __init__(self, seconds=12):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True, '-alpha', 0.93)
        self.root.configure(bg=BG)
        self.seconds, self.q, self.hide_at = seconds, queue.Queue(), None
        self.ask = tk.Label(self.root, bg=BG, fg=DIM, font=('Segoe UI', 10), wraplength=400, justify='left', anchor='w')
        self.ans = tk.Label(self.root, bg=BG, fg=FG, font=('Segoe UI', 12), wraplength=400, justify='left', anchor='w')
        self.ask.pack(fill='x', padx=14, pady=(10, 2))
        self.ans.pack(fill='x', padx=14, pady=(2, 12))
        for w in (self.root, self.ask, self.ans):
            w.bind('<Button-1>', self._copy)
        self.root.after(50, self._pump)

    # any thread
    def show(self, question='', answer='', stay=False):
        self.q.put((question, answer, stay))

    def hide(self):
        self.q.put(None)

    # Tk thread
    def _pump(self):
        try:
            while True:
                item = self.q.get_nowait()
                if item is None:
                    self.root.withdraw()
                    continue
                question, answer, stay = item
                if question:
                    self.ask.config(text=question)
                self.ans.config(text=answer)
                self._place()
                self.root.deiconify()
                self.root.lift()
                if self.hide_at:
                    self.root.after_cancel(self.hide_at)
                self.hide_at = None if stay else self.root.after(self.seconds * 1000, self.root.withdraw)
        except queue.Empty:
            pass
        self.root.after(50, self._pump)

    def _place(self):
        self.root.update_idletasks()
        mons = win.monitors() or [(0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight(), True)]
        x, y, w, h, _ = next((m for m in mons if not m[4]), mons[0])   # a second monitor if there is one
        bw, bh = self.root.winfo_reqwidth(), self.root.winfo_reqheight()
        self.root.geometry(f'+{x + w - bw - 24}+{y + h - bh - 24}')

    def _copy(self, _):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.ans.cget('text'))
        self.root.withdraw()

    def run(self):
        self.root.mainloop()

    def quit(self):
        self.root.after(0, self.root.destroy)
