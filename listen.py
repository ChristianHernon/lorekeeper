"""Listen mode: the mic stays open, no key to hold. Start with "Lorekeeper, …"; for a few seconds after an answer,
follow-ups need no wake word.

Cheap while you're quiet: a loudness check on 30 ms frames finds speech (the noise floor adapts to fans and game
audio), and only those clips go to Whisper. Everything is ignored while Lorekeeper itself is talking, or while the
hotkey is held, or when no game is in front."""
import collections, queue, re, threading, time
import numpy as np

RATE, FRAME = 16000, 480   # 30 ms
WAKE = re.compile(r"^\W*(?:(?:hey|hi|ok(?:ay)?|yo)[\s,]+)?(?:lore ?keeper|lord ?keeper|lor ?keeper|law ?keeper|lore ?kipper|keeper)\b[\s,.:!?-]*(.*)$", re.I)


def wake(text):
    """("Lorekeeper, what does this do?") -> 'what does this do?'; '' for the name alone; None if not addressed."""
    m = WAKE.match(text.strip())
    return None if not m else m.group(1).strip()


class Segmenter:
    """Feeds 30 ms frames, returns a whole utterance (float32) when one ends. Pure: tested without a mic."""

    def __init__(self, start_ms=150, end_ms=700, max_s=15, pre_ms=300):
        self.voiced, self.quiet = 0, 0
        self.levels = collections.deque(maxlen=100)   # the last 3 s of loudness; its quiet end is the room's noise
        self.start_n, self.end_n, self.max_n = start_ms // 30, end_ms // 30, max_s * 1000 // 30
        self.pre = collections.deque(maxlen=pre_ms // 30)   # keep the word's first sound
        self.cur = None

    def feed(self, frame):
        rms = float(np.sqrt(np.mean(frame ** 2)) + 1e-9)
        self.levels.append(rms)
        if len(self.levels) < 33:   # the first second only learns the room
            self.pre.append(frame)
            return None
        loud = rms > max(float(np.percentile(self.levels, 10)) * 3.0, 0.008)
        if self.cur is None:
            self.pre.append(frame)
            self.voiced = self.voiced + 1 if loud else 0
            if self.voiced >= self.start_n:
                self.cur, self.quiet = list(self.pre), 0
                self.started = time.time()
            return None
        self.cur.append(frame)
        self.quiet = 0 if loud else self.quiet + 1
        if self.quiet >= self.end_n or len(self.cur) >= self.max_n:
            out = np.concatenate(self.cur[:len(self.cur) - self.quiet + 3])   # trim most of the trailing silence
            self.cur, self.voiced = None, 0
            self.pre.clear()
            return out
        return None

    def reset(self):
        self.cur, self.voiced = None, 0
        self.pre.clear()


class Listener:
    """on_text(question) for each addressed utterance. muted(): skip audio now (speaking, hotkey held, no game)."""

    def __init__(self, ears, on_text, muted, follow_s=8, on_wake=lambda: None, hint=lambda: ''):
        self.ears, self.on_text, self.muted, self.follow_s, self.on_wake, self.hint = ears, on_text, muted, follow_s, on_wake, hint
        self.on, self.open_until, self.stream = False, 0.0, None
        self.q, self.seg = queue.Queue(), Segmenter()
        threading.Thread(target=self._work, daemon=True).start()

    def follow_up(self):
        """Called when an answer finishes speaking: the next few seconds need no wake word."""
        self.open_until = time.time() + self.follow_s

    def start(self):
        import sounddevice as sd
        if self.on:
            return
        self.seg.reset()
        self.stream = sd.InputStream(samplerate=RATE, channels=1, dtype='float32', blocksize=FRAME,
                                     callback=lambda d, *_: self.q.put(d[:, 0].copy()))
        self.stream.start()
        self.on = True

    def stop(self):
        self.on = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def _work(self):
        buf = np.zeros(0, dtype='float32')
        while True:
            block = self.q.get()
            try:
                muted = self.muted()
            except Exception:
                muted = True   # the app is still starting
            if muted:
                self.seg.reset()
                buf = np.zeros(0, dtype='float32')
                continue
            buf = np.concatenate([buf, block])
            while len(buf) >= FRAME:
                frame, buf = buf[:FRAME], buf[FRAME:]
                clip = self.seg.feed(frame)
                if clip is not None and len(clip) > RATE * 0.4:
                    threading.Thread(target=self._heard, args=(clip, time.time() < self.open_until), daemon=True).start()

    def _heard(self, clip, open_):
        text = self.ears.text(clip, 'Lorekeeper, ' + self.hint())
        if not text or self.muted():
            return
        q = wake(text)
        if q is None and open_:
            q = text   # a follow-up right after an answer
        if q is None:
            return   # talking to someone else
        if not q:   # just the name: listen for the question without it
            self.open_until = time.time() + self.follow_s
            return self.on_wake()
        self.open_until = 0
        self.on_text(q)
