"""Step 2 of the demo: voice script.json (player: a second Kokoro voice; Lorekeeper: its real voice), draw 8-bit frames in
time with the speech, and encode docs/demo.mp4. No game footage: games appear by name only.
  python demo/make_video.py            -> docs/demo.mp4 (1280x720, 30 fps)
Needs: kokoro-onnx + model (setup.ps1), pillow, numpy, imageio-ffmpeg."""
import json, os, random, subprocess, sys, textwrap
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import config  # noqa: E402

W, H, FPS, SR = 1280, 720, 30, 24000
PLAYER_VOICE = 'am_michael'
LK_VOICE = config.DEFAULTS['kokoroVoice']
NIGHT, NIGHT2, INK, DIM, SKY, PINK, GOLD, CRIMSON, PURPLE = ((11, 11, 43), (36, 16, 80), (242, 239, 230), (170, 165, 200), (73, 198, 255),
                                                             (255, 138, 164), (255, 210, 63), (224, 40, 79), (122, 60, 255))
PS = lambda n: ImageFont.truetype(os.path.join(HERE, 'fonts', 'PressStart2P-Regular.ttf'), n)
VT = lambda n: ImageFont.truetype(os.path.join(HERE, 'fonts', 'VT323-Regular.ttf'), n)


# audio

def tts():
    from kokoro_onnx import Kokoro
    k = Kokoro(os.path.join(config.MODELS, 'kokoro-v1.0.int8.onnx'), os.path.join(config.MODELS, 'voices-v1.0.bin'))

    def style(v):
        if ':' not in v:
            return v
        parts = [(n, float(w)) for n, w in (p.split(':') for p in v.split(','))]
        return sum(k.get_voice_style(n) * w for n, w in parts) / sum(w for _, w in parts)

    def say(text, voice, lang):
        a, sr = k.create(text, voice=style(voice), speed=1.15, lang=lang)
        assert sr == SR
        return a.astype(np.float32)
    return say


def silence(s):
    return np.zeros(int(s * SR), np.float32)


# drawing

random.seed(7)
STARS = [(random.randrange(W), random.randrange(H), random.choice([2, 2, 3]), random.choice([INK, SKY, PURPLE, DIM])) for _ in range(90)]


def background():
    img = Image.new('RGB', (W, H))
    top, bot = np.array(NIGHT), np.array(NIGHT2)
    grad = (top + (bot - top) * np.linspace(0, 1, H)[:, None]).astype(np.uint8)
    img = Image.fromarray(np.repeat(grad[:, None, :], W, axis=1))
    d = ImageDraw.Draw(img)
    for x, y, s, c in STARS:
        d.rectangle((x, y, x + s - 1, y + s - 1), fill=c)
    return img


def scanlines(img):
    a = np.asarray(img).copy()
    a[::3] = (a[::3] * 0.82).astype(np.uint8)
    return Image.fromarray(a)


def pixel_box(d, box, border=INK, fill=(8, 8, 42), shadow=(4, 4, 20)):
    x0, y0, x1, y1 = box
    d.rectangle((x0 + 10, y0 + 10, x1 + 10, y1 + 10), fill=shadow)
    d.rectangle((x0, y0, x1, y1), fill=fill)
    d.rectangle((x0 + 4, y0 - 4, x1 - 4, y0 - 1), fill=border)   # stepped corners: four bars, corners left out
    d.rectangle((x0 + 4, y1 + 1, x1 - 4, y1 + 4), fill=border)
    d.rectangle((x0 - 4, y0 + 4, x0 - 1, y1 - 4), fill=border)
    d.rectangle((x1 + 1, y0 + 4, x1 + 4, y1 - 4), fill=border)


def shadow_text(d, xy, text, font, fill, depth=3, under=(90, 10, 30)):
    x, y = xy
    d.text((x + depth, y + depth), text, font=font, fill=under)
    d.text((x, y), text, font=font, fill=fill)


def wrap(text, font, width):
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if font.getlength(t) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])


def scene_frame(base, mascot, s, held, q_chars, a_chars, status, flash=0.0):
    img = base.copy()
    d = ImageDraw.Draw(img)
    img.paste(mascot, (40, 26), mascot)
    shadow_text(d, (40 + mascot.width + 14, 40), 'LOREKEEPER', PS(18), INK, 2)
    # the hotkey: lit while the player holds it and talks
    x = W - 40
    for cap in reversed(['CTRL', 'ALT', 'SPACE']):
        w = int(PS(13).getlength(cap)) + 26
        x -= w
        d.rectangle((x, 32, x + w, 68), fill=CRIMSON if held else (24, 22, 70), outline=INK if held else DIM, width=3)
        d.text((x + 13, 43), cap, font=PS(13), fill=INK)
        x -= 10
    d.text((W - 40 - 330, 78), 'HOLD TO TALK' if not held else 'LISTENING...', font=VT(26), fill=GOLD if held else DIM)
    # the game in front
    d.text((60, 118), 'NOW PLAYING', font=VT(28), fill=DIM)
    game = s['game'].upper()
    tw = int(VT(58).getlength(game))
    d.rectangle((56, 150, 56 + tw + 28, 210), fill=SKY)
    d.text((70, 150), game, font=VT(58), fill=NIGHT)
    if s.get('shot') is not None:   # what Lorekeeper saw: the screenshot that went with "this"
        th = s['shot']
        img.paste(th, (W - 60 - th.width, 112))
        d.rectangle((W - 64 - th.width, 108, W - 56, 116 + th.height), outline=SKY, width=3)
        d.text((W - 60 - th.width - 132, 112 + th.height // 2 - 12), 'SCREEN SENT', font=VT(24), fill=SKY)
    # the dialogue box
    pixel_box(d, (60, 248, W - 60, H - 46))
    y = 272
    def label(y, text, color):   # "YOU ▸": the pixel font has no ▸, so the arrow is drawn
        d.text((86, y), text, font=VT(46), fill=color)
        x = 86 + VT(46).getlength(text) + 10
        for i in range(5):
            d.rectangle((x + i * 3, y + 16 + i * 3, x + i * 3 + 2, y + 16 + (10 - i) * 3 - 1), fill=color)
    label(y, 'YOU', PINK)
    q = s['q'][:q_chars]
    for line in wrap(q, VT(46), W - 330):
        d.text((200, y), line, font=VT(46), fill=INK)
        y += 46
    y += 12
    if a_chars or status:
        label(y, 'LK', SKY)
        if status and not a_chars:
            d.text((200, y), status, font=VT(46), fill=DIM)
        else:
            lines = wrap(s['a'], VT(42), W - 330)
            for i, line in enumerate(lines):
                start = sum(len(l) + 1 for l in lines[:i])
                shown = line[:max(0, a_chars - start)]
                if shown:
                    d.text((200, y + 2), shown, font=VT(42), fill=GOLD if s.get('clip') else INK)
                y += 41
    if s.get('secs') and a_chars >= len(s['a']):
        d.text((W - 290, H - 82), f"answered in {s['secs']:.1f} s", font=VT(28), fill=DIM)
    if flash > 0:   # the clip's shutter
        img = Image.blend(img, Image.new('RGB', (W, H), INK), min(0.85, flash))
    return scanlines(img)


def main():
    script = json.load(open(os.path.join(HERE, 'script.json'), encoding='utf-8'))
    import answers
    for s in script:   # the gear scene shows the screenshot it was asked about
        s['shot'] = None
        if s['game'] == 'Diablo IV':
            path = answers.tooltip_shot()[0][0]
            shot = Image.open(path).convert('RGB').crop((585, 66, 1265, 440))
            s['shot'] = shot.resize((200, int(200 * shot.height / shot.width)), Image.LANCZOS)
            os.remove(path)
    say = tts()
    base = background()
    card = Image.open(os.path.join(ROOT, 'docs', 'og', 'discord.png')).convert('RGB').resize((W, H))
    book = Image.open(os.path.join(ROOT, 'docs', 'og', 'discord.png')).convert('RGB').crop((490, 70, 815, 310))
    mascot = book.resize((int(book.width * 56 / book.height), 56), Image.NEAREST).convert('RGBA')

    audio, frames = [], []   # frames: (seconds, draw(t_local) -> Image)

    def add(seconds, draw, sound=None):
        n = int(round(seconds * FPS))
        frames.append((n, draw))
        snd = sound if sound is not None else silence(seconds)
        audio.append(np.pad(snd, (0, max(0, int(n / FPS * SR) - len(snd))))[:int(n / FPS * SR)])

    add(2.6, lambda f: scanlines(card))
    for s in script:
        add(0.5, lambda f, s=s: scene_frame(base, mascot, s, False, 0, 0, ''))
        qa = say(s['q'], PLAYER_VOICE, 'en-us')
        qn = len(s['q'])
        add(len(qa) / SR + 0.15, lambda f, s=s, qn=qn, d=len(qa) / SR: scene_frame(base, mascot, s, True, min(qn, int(qn * f / FPS / max(d, .1)) + 1), 0, ''), qa)
        if s.get('clip'):
            add(0.6, lambda f, s=s: scene_frame(base, mascot, s, False, len(s['q']), 0, '', flash=max(0, .9 - f / FPS * 3)))
            s2 = dict(s, a='[REC] Clipped: the last 30 seconds are saved. Silent, so no voice ends up in your clip.')
            add(2.4, lambda f, s2=s2: scene_frame(base, mascot, s2, False, len(s2['q']), len(s2['a']), ''))
            continue
        add(0.7, lambda f, s=s: scene_frame(base, mascot, s, False, len(s['q']), 0, '.' * (1 + (f // 6) % 3)))
        aa = say(s['a'], LK_VOICE, 'en-us')
        an, ad = len(s['a']), len(aa) / SR
        add(ad + 0.2, lambda f, s=s, an=an, ad=ad: scene_frame(base, mascot, s, False, len(s['q']), min(an, int(an * f / FPS / ad * 1.04) + 1), ''), aa)
        add(1.0, lambda f, s=s: scene_frame(base, mascot, s, False, len(s['q']), len(s['a']), ''))
    # outro
    def outro(f):
        img = base.copy()
        d = ImageDraw.Draw(img)
        big = book.resize((int(book.width * 200 / book.height), 200), Image.NEAREST)
        img.paste(big, ((W - big.width) // 2, 70))
        for text, font, fill, y in [('LOREKEEPER', PS(56), INK, 300), ('A voice companion for PC games', VT(46), GOLD, 384),
                                    ('lorekeeper-cgv.pages.dev', PS(22), SKY, 470),
                                    ('Free - open source - runs on your Claude plan', VT(34), DIM, 528),
                                    ('Works with Steam, Epic, GOG, RomM and emulators', VT(34), DIM, 566)]:
            x = (W - font.getlength(text)) / 2
            (shadow_text(d, (x, y), text, font, fill, 4) if font.size == 56 else d.text((x, y), text, font=font, fill=fill))
        return scanlines(img)
    add(4.0, outro)

    import imageio_ffmpeg
    track = np.concatenate(audio)
    wav = os.path.join(HERE, 'demo.wav')
    import soundfile
    soundfile.write(wav, track, SR)
    out = os.path.join(ROOT, 'docs', 'demo.mp4')
    p = subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                          '-r', str(FPS), '-i', '-', '-i', wav, '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-tune', 'animation',
                          '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart', out],
                         stdin=subprocess.PIPE)
    last, last_img = None, None
    total = 0
    for n, draw in frames:
        for f in range(n):
            img = draw(f)
            p.stdin.write(img.tobytes())
            total += 1
    p.stdin.close()
    p.wait()
    os.remove(wav)
    print(f'{out}: {total / FPS:.1f} s, {os.path.getsize(out) / 1e6:.1f} MB')


if __name__ == '__main__':
    main()
