"""Answers read aloud a sentence at a time, so speech starts before the whole answer is in.
sapi: Windows' own voice, offline. edge: Microsoft's online neural voices (edge-tts), played through winmm."""
import ctypes, os, queue, re, tempfile, threading


class Voice:
    def __init__(self, kind='sapi', edge_voice='en-US-AndrewNeural', rate=0):
        self.kind, self.edge_voice, self.rate = kind, edge_voice, rate
        self.q, self.gen, self.speaking = queue.Queue(), 0, False
        self._now = None   # the playing SAPI voice or mci alias, for stop()
        threading.Thread(target=self._loop, daemon=True).start()

    def say(self, text):
        for s in split(text):
            self.q.put((self.gen, s))

    def stop(self):
        """True if it was talking."""
        was = self.speaking or not self.q.empty()
        self.gen += 1
        while not self.q.empty():
            try:
                self.q.get_nowait()
            except queue.Empty:
                break
        now = self._now
        if now is not None:
            try:
                now.Speak('', 3) if self.kind == 'sapi' else _mci(f'stop {now}')   # SVSFAsync | SVSFPurgeBeforeSpeak
            except Exception:
                pass
        return was

    def busy(self):
        return self.speaking or not self.q.empty()

    def _loop(self):
        if self.kind == 'sapi':
            import comtypes, comtypes.client
            comtypes.CoInitialize()
            sp = comtypes.client.CreateObject('SAPI.SpVoice')
            sp.Rate = self.rate
        while True:
            gen, s = self.q.get()
            if gen != self.gen:
                continue
            self.speaking = True
            try:
                if self.kind == 'sapi':
                    self._now = sp
                    sp.Speak(s, 1)   # async, so stop() can cut it off
                    while not sp.WaitUntilDone(100) and gen == self.gen:
                        pass
                else:
                    self._edge(s, gen)
            except Exception as e:
                print('voice:', e)
            finally:
                self._now = None
                self.speaking = not self.q.empty()

    def _edge(self, s, gen):
        import asyncio, edge_tts
        fd, path = tempfile.mkstemp(suffix='.mp3', prefix='lorekeeper-')
        os.close(fd)
        try:
            asyncio.run(edge_tts.Communicate(s, self.edge_voice).save(path))
            if gen != self.gen:
                return
            alias = f'lk{gen}'
            _mci(f'open "{path}" type mpegvideo alias {alias}')
            self._now = alias
            _mci(f'play {alias} wait')   # returns early on stop
            _mci(f'close {alias}')
        finally:
            os.remove(path)


def _mci(cmd):
    ctypes.windll.winmm.mciSendStringW(cmd, None, 0, None)


def split(text):
    """Sentences, for speaking as they arrive. Markdown and links are not for ears."""
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[*_#`>]+', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', text) if re.search(r'\w', s)]
