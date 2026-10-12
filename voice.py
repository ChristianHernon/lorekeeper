"""Answers read aloud a sentence at a time, so speech starts before the whole answer is in.
edge: Microsoft's neural voices (edge-tts, online), the next sentence made while this one plays, played through winmm.
sapi: Windows' own voice, offline; also the fallback when edge can't be reached."""
import ctypes, os, queue, re, tempfile, threading, time
from concurrent.futures import ThreadPoolExecutor


class Voice:
    def __init__(self, kind='edge', edge_voice='en-GB-SoniaNeural', rate=0, pitch='-8Hz'):
        self.kind, self.edge_voice, self.rate, self.pitch = kind, edge_voice, rate, pitch
        self.q, self.gen, self.speaking, self.stopped = queue.Queue(), 0, False, threading.Event()
        self.pool = ThreadPoolExecutor(2)
        threading.Thread(target=self._loop, daemon=True).start()

    def say(self, text):
        for s in split(text):
            self.q.put((self.gen, s, self.pool.submit(self._make, s) if self.kind == 'edge' else None))

    def stop(self):
        """True if it was talking."""
        was = self.busy()
        self.gen += 1
        self.stopped.set()
        while True:
            try:
                _, _, fut = self.q.get_nowait()
            except queue.Empty:
                break
            if fut:
                fut.add_done_callback(lambda f: f.result() and _rm(f.result()))
        return was

    def busy(self):
        return self.speaking or not self.q.empty()

    def _loop(self):
        import comtypes, comtypes.client
        comtypes.CoInitialize()
        sp = comtypes.client.CreateObject('SAPI.SpVoice')
        sp.Rate = self.rate
        while True:
            gen, s, fut = self.q.get()
            if gen != self.gen:
                fut and fut.add_done_callback(lambda f: f.result() and _rm(f.result()))
                continue
            self.speaking = True
            self.stopped.clear()
            try:
                path = fut.result() if fut else ''
                if path:
                    self._play(path)
                else:   # sapi chosen, or edge unreachable
                    sp.Speak(s, 1)   # async, so stop can cut it off
                    while not sp.WaitUntilDone(50):
                        if self.stopped.is_set():
                            sp.Speak('', 3)   # purge
                            break
            except Exception as e:
                print('voice:', e)
            finally:
                self.speaking = not self.q.empty()

    def _make(self, s):
        """One sentence as an mp3 (~0.3-0.8 s) -> path, or '' if it failed."""
        import asyncio, edge_tts
        fd, path = tempfile.mkstemp(suffix='.mp3', prefix='lorekeeper-')
        os.close(fd)
        try:
            asyncio.run(edge_tts.Communicate(s, self.edge_voice, rate=f'{self.rate * 5:+d}%', pitch=self.pitch).save(path))
            return path
        except Exception as e:
            print('voice:', e)
            _rm(path)
            return ''

    def _play(self, path):
        """Plays it on this thread; polls so stop() cuts it off within 50 ms."""
        try:
            _mci(f'open "{path}" type mpegvideo alias lk')
            _mci('play lk')
            while _mci('status lk mode') == 'playing' and not self.stopped.is_set():
                time.sleep(0.05)
            _mci('stop lk')
            _mci('close lk')
        finally:
            _rm(path)


def _rm(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _mci(cmd):
    buf = ctypes.create_unicode_buffer(64)
    ctypes.windll.winmm.mciSendStringW(cmd, buf, 64, None)
    return buf.value


def split(text):
    """Sentences, for speaking as they arrive. Markdown and links are not for ears."""
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[*_#`>]+', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', text) if re.search(r'\w', s)]


def samples(folder, voices, pitches=('+0Hz', '-8Hz', '-14Hz'),
            line='The Gilded Hydra fires bouncing, piercing bursts. Its flavor text: Heads Up!'):
    """Writes <voice> <pitch>.mp3 for each, to pick one by ear."""
    import asyncio, edge_tts
    os.makedirs(folder, exist_ok=True)

    async def all_():
        await asyncio.gather(*[edge_tts.Communicate(line, v, pitch=p).save(os.path.join(folder, f'{v.split("-")[2].replace("Neural", "")} {v[:5]} {p}.mp3'))
                               for v in voices for p in pitches])
    asyncio.run(all_())
