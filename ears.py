"""The mic while the hotkey is held, and Whisper (faster-whisper) on this PC. Audio never leaves it."""
import threading
import numpy as np

RATE = 16000


class Ears:
    def __init__(self, size='base.en', device='cpu'):
        self.model, self.chunks, self.stream = None, [], None
        self.ready = threading.Event()
        threading.Thread(target=self._load, args=(size, device), daemon=True).start()   # a few seconds; the first ask waits for it

    def _load(self, size, device):
        from faster_whisper import WhisperModel
        try:
            self.model = WhisperModel(size, device=device, compute_type='int8' if device == 'cpu' else 'float16')
        except Exception:
            self.model = WhisperModel(size, device='cpu', compute_type='int8')   # no CUDA after all
        self.ready.set()

    def start(self):
        import sounddevice as sd
        self.chunks = []
        self.stream = sd.InputStream(samplerate=RATE, channels=1, dtype='float32', callback=lambda d, *_: self.chunks.append(d.copy()))
        self.stream.start()

    def stop(self):
        """The recording so far, as one float32 array (empty if nothing)."""
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        return np.concatenate(self.chunks)[:, 0] if self.chunks else np.zeros(0, dtype='float32')

    def text(self, audio, hint=''):
        """hint: the game's name and names from its notes, so Whisper spells "Malenia" right."""
        if len(audio) < RATE * 0.4:
            return ''
        self.ready.wait(60)
        segs, _ = self.model.transcribe(audio, language='en', beam_size=1, vad_filter=True, initial_prompt=hint or None,
                                        condition_on_previous_text=False)
        return ' '.join(s.text.strip() for s in segs).strip()
