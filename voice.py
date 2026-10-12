"""Answers read aloud a sentence at a time, so speech starts before the whole answer is in; the next sentence is made
while this one plays.
kokoro: a neural voice on this PC (kokoro-onnx, ~1 s of CPU per 5 s of speech). Voices can be blended:
        "bf_isabella:0.75,bm_george:0.25" is a lower, throatier Isabella.
edge:   Microsoft's online neural voices (edge-tts); Microsoft sometimes blocks it.
sapi:   Windows' own voice, offline and robotic; the fallback when the others fail."""
import ctypes, os, queue, re, tempfile, threading, time
from concurrent.futures import ThreadPoolExecutor


class Voice:
    def __init__(self, kind='kokoro', edge_voice='en-GB-SoniaNeural', rate=0, pitch='-8Hz', kokoro_voice='bf_isabella', models=''):
        self.kind, self.edge_voice, self.rate, self.pitch = kind, edge_voice, rate, pitch
        self.kokoro_voice, self.models, self._kokoro = kokoro_voice, models, None
        self.q, self.gen, self.speaking, self.stopped = queue.Queue(), 0, False, threading.Event()
        self.pool = ThreadPoolExecutor(1 if kind == 'kokoro' else 2)   # kokoro: one at a time, it uses every core
        if kind == 'kokoro':
            self.pool.submit(self._load)   # ~2 s, before the first answer
        threading.Thread(target=self._loop, daemon=True).start()

    def say(self, text):
        for s in split(text):
            self.q.put((self.gen, s, self.pool.submit(self._make, s) if self.kind != 'sapi' else None))

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

    def _load(self):
        from kokoro_onnx import Kokoro
        self._kokoro = Kokoro(os.path.join(self.models, 'kokoro-v1.0.int8.onnx'), os.path.join(self.models, 'voices-v1.0.bin'))

    def _style(self):
        """"bf_isabella" or a blend "bf_isabella:0.75,bm_george:0.25"."""
        if ':' not in self.kokoro_voice:
            return self.kokoro_voice
        parts = [(n.strip(), float(w)) for n, w in (p.split(':') for p in self.kokoro_voice.split(','))]
        return sum(self._kokoro.get_voice_style(n) * w for n, w in parts) / sum(w for _, w in parts)

    def _make(self, s):
        """One sentence as a sound file -> path, or '' if it failed (then SAPI says it)."""
        fd, path = tempfile.mkstemp(suffix='.wav' if self.kind == 'kokoro' else '.mp3', prefix='lorekeeper-')
        os.close(fd)
        try:
            if self.kind == 'kokoro':
                import soundfile
                if not self._kokoro:
                    self._load()
                first = self.kokoro_voice.split(',')[0]
                audio, sr = self._kokoro.create(s, voice=self._style(), speed=1 + self.rate / 20, lang='en-gb' if first.startswith('b') else 'en-us')
                soundfile.write(path, audio, sr)
            else:
                import asyncio, edge_tts
                asyncio.run(edge_tts.Communicate(s, self.edge_voice, rate=f'{self.rate * 5:+d}%', pitch=self.pitch).save(path))
            return path
        except Exception as e:
            print('voice:', e)
            _rm(path)
            return ''

    def _play(self, path):
        """Plays it on this thread; polls so stop() cuts it off within 50 ms."""
        try:
            _mci(f'open "{path}" type {"waveaudio" if path.endswith(".wav") else "mpegvideo"} alias lk')
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


VOICES = {   # tray → Voice: name shown -> kokoroVoice
    'Nicole + Isabella (default)': 'af_nicole:0.5,bf_isabella:0.5',
    'Isabella, low': 'bf_isabella:0.75,bm_george:0.25',
    'Isabella (British)': 'bf_isabella',
    'Nicole (soft, breathy)': 'af_nicole',
    'Emma (British)': 'bf_emma',
    'Alice (British)': 'bf_alice',
    'Heart (American, warm)': 'af_heart',
    'Bella (American)': 'af_bella',
    'Sarah (American)': 'af_sarah',
    'Kore (American)': 'af_kore',
    'George (British man)': 'bm_george',
    'Michael (American man)': 'am_michael',
}
KOKORO_SAMPLES = list(VOICES.values())
PREVIEW = 'Lorekeeper here. Ask me anything about your game.'


def samples(folder, models, line='The Gilded Hydra fires bouncing, piercing bursts. Its flavor text: Heads Up!'):
    """Writes "<voice>.wav" for each kokoro voice and blend, to pick kokoroVoice by ear."""
    os.makedirs(folder, exist_ok=True)
    v = Voice('sapi', models=models)
    v._load()
    v.kind = 'kokoro'
    for name in KOKORO_SAMPLES:
        v.kokoro_voice = name
        os.replace(v._make(line), os.path.join(folder, name.replace(':', ' ').replace(',', ' + ') + '.wav'))
