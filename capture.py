"""The game's screen: a frame a second kept for the last few seconds, so "what synergy did I just get" can still see the
banner that faded before the hotkey went down. DXGI duplication (dxcam) sees most fullscreen games where GDI gets black.
Frames stay in memory; only the ones sent with a question are written (temp, deleted after)."""
import collections, os, re, tempfile, threading, time

WANTS = re.compile(r"\b(this|that|these|those|here|on (?:my |the )?screen|just (?:got|get|picked|pick(?:ed)? up|found|find|unlocked|unlock|looted|triggered|activated|equipped)|"
                   r"i'?m (?:looking at|holding|fighting)|what am i)\b", re.I)
JUST = re.compile(r'\bjust\b|\ba (?:second|moment|sec) ago\b|\bthat (?:popped|came) up\b', re.I)
WIDE = 1280


def wants(question):
    return bool(WANTS.search(question))


class Screen:
    def __init__(self, keep=5, active=lambda: True):
        self.frames = collections.deque(maxlen=keep)   # (time, PIL image)
        self.active, self.cam, self.lock = active, None, threading.Lock()
        threading.Thread(target=self._loop, daemon=True).start()

    def _grab(self):
        from PIL import Image, ImageGrab
        img = None
        try:
            if self.cam is None:
                import dxcam
                self.cam = dxcam.create(output_color='RGB')
            a = self.cam.grab()   # None when nothing changed since the last grab
            if a is not None:
                img = Image.fromarray(a)
            elif self.frames:
                return self.frames[-1][1]
        except Exception:
            self.cam = False   # no DXGI here: GDI from now on
        if img is None:
            img = ImageGrab.grab()
        if img.getbbox() is None:   # all black: exclusive fullscreen that hides from both
            return None
        if img.width > WIDE:
            img = img.resize((WIDE, round(img.height * WIDE / img.width)))
        return img

    def _loop(self):
        while True:
            try:
                if self.active():
                    img = self._grab()
                    if img is not None:
                        with self.lock:
                            self.frames.append((time.time(), img))
            except Exception as e:
                print('screen:', e)
            time.sleep(1)

    def now(self):
        """Grab one this instant (at key-down) -> [(time, image)] with the buffer before it."""
        try:
            img = self._grab()
        except Exception:
            img = None
        with self.lock:
            out = list(self.frames)
        return out + ([(time.time(), img)] if img is not None else [])

    @staticmethod
    def files(frames, question, most=4):
        """The frames worth sending for this question, as jpegs -> [(path, label)]. Just the last one unless it says "just"."""
        if not frames:
            return []
        pick = frames[-most:] if JUST.search(question) else frames[-1:]
        t_end, out = pick[-1][0], []
        for t, img in pick:
            fd, path = tempfile.mkstemp(prefix='lorekeeper-shot-', suffix='.jpg')
            os.close(fd)
            img.convert('RGB').save(path, quality=80)
            ago = round(t_end - t)
            out.append((path, 'Screen when the key went down:' if ago == 0 and t == t_end else f'Screen {ago} s before that:'))
        return out
