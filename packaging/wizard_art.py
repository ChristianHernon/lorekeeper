"""The installer's artwork, drawn like the landing page: night-sky gradient, pixel stars, the pixel book, pixel fonts.
  python packaging/wizard_art.py   -> packaging/wizard/*.png (committed; lorekeeper.iss lists them)
Several sizes of each, so Inno Setup picks a sharp one at every display scaling."""
import os, random, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import art  # noqa: E402

OUT = os.path.join(HERE, 'wizard')
NIGHT, NIGHT2, INK, SKY, PINK, GOLD, PURPLE, DIM = ((11, 11, 43), (36, 16, 80), (242, 239, 230), (73, 198, 255), (255, 138, 164),
                                                    (255, 210, 63), (122, 60, 255), (150, 145, 190))
PS = lambda n: ImageFont.truetype(os.path.join(ROOT, 'assets', 'fonts', 'PressStart2P-Regular.ttf'), n)
VT = lambda n: ImageFont.truetype(os.path.join(ROOT, 'assets', 'fonts', 'VT323-Regular.ttf'), n)


def sky(w, h, k, stars=60, seed=3, top=NIGHT, bottom=NIGHT2, clear=()):
    """Night gradient with square pixel stars; k = pixel size; clear: (y0, y1) bands kept free of stars (text goes there)."""
    img = Image.new('RGB', (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    rnd = random.Random(seed)
    for _ in range(stars):
        x, y = rnd.randrange(w), rnd.randrange(h)
        s = k * rnd.choice((1, 1, 2))
        if any(a - 6 * k <= y <= b + 6 * k for a, b in clear):
            continue
        d.rectangle((x, y, x + s - 1, y + s - 1), fill=rnd.choice((INK, SKY, PURPLE, DIM)))
    return img


def book(height):
    """The mascot (with sparkles) scaled by a whole number, nearest-neighbour: pixel art stays crisp."""
    src = art.image(128)   # the full mascot, drawn at x5
    bb = src.getbbox()
    src = src.crop(bb)
    k = max(1, height // src.height)
    return src.resize((src.width * k, src.height * k), Image.NEAREST)


def shadow_text(d, xy, text, font, fill, depth):
    x, y = xy
    d.text((x + depth, y + depth), text, font=font, fill=(90, 10, 30))
    d.text((x, y), text, font=font, fill=fill)


def banner(scale):
    """Welcome and finish pages: a tall panel on the left."""
    w, h = round(202 * scale), round(386 * scale)
    k = max(1, round(2 * scale))
    img = sky(w, h, k, stars=55, seed=7, clear=((round(196 * scale), round(244 * scale)), (round(264 * scale), round(336 * scale)),
                                                (h - round(52 * scale), h)))
    d = ImageDraw.Draw(img)
    b = book(round(110 * scale))
    img.paste(b, ((w - b.width) // 2, round(54 * scale)), b)
    f = PS(max(8, round(14 * scale)))
    for i, word in enumerate(('LORE', 'KEEPER')):
        tw = d.textlength(word, font=f)
        shadow_text(d, ((w - tw) / 2, round(200 * scale) + i * round(22 * scale)), word, f, INK, max(1, round(2 * scale)))
    vt = VT(max(12, round(24 * scale)))
    for i, (line, colour) in enumerate((('Hold a key.', INK), ('Ask out loud.', SKY), ('Hear the answer.', PINK))):
        tw = d.textlength(line, font=vt)
        d.text(((w - tw) / 2, round(268 * scale) + i * round(22 * scale)), line, font=vt, fill=colour)
    small = VT(max(10, round(19 * scale)))
    for i, t in enumerate(('A voice companion', 'for PC games')):
        d.text(((w - d.textlength(t, font=small)) / 2, h - round(46 * scale) + i * round(18 * scale)), t, font=small, fill=GOLD)
    return img


def corner(size):
    """Top-right logo on the inner pages."""
    img = Image.new('RGB', (size, size), NIGHT)
    b = art.image(64 if size >= 64 else 32)
    b = b.crop(b.getbbox())
    k = max(1, (size - 6) // max(b.width, b.height))
    b = b.resize((b.width * k, b.height * k), Image.NEAREST)
    img.paste(b, ((size - b.width) // 2, (size - b.height) // 2), b)
    return img


def raptor(px):
    """The site's pixel raptor (docs/img/raptor-a.svg), px screen pixels per art pixel."""
    import re
    svg = open(os.path.join(ROOT, 'docs', 'img', 'raptor-a.svg'), encoding='utf-8').read()
    w, h = (int(v) for v in re.search(r'viewBox="0 0 (\d+) (\d+)"', svg).groups())
    img = Image.new('RGBA', (w * px, h * px), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for x, y, c in re.findall(r'<rect x="(\d+)" y="(\d+)" width="1" height="1" fill="(#[0-9a-f]{6})"/>', svg):
        x, y = int(x), int(y)
        d.rectangle((x * px, y * px, x * px + px - 1, y * px + px - 1), fill=c)
    return img


def backdrop(scale):
    """Behind every page: the night sky, quiet enough to read text over: a few dim stars, only along the bottom and
    right, where no text goes."""
    w, h = round(600 * scale), round(460 * scale)
    img = sky(w, h, 1, stars=0, top=(9, 9, 34), bottom=(22, 12, 54))
    d = ImageDraw.Draw(img)
    rnd, k = random.Random(11), max(1, round(2 * scale))
    for _ in range(26):
        if rnd.random() < 0.5:
            x, y = rnd.randrange(w), rnd.randrange(int(h * 0.80), h)          # the strip by the buttons
        else:
            x, y = rnd.randrange(int(w * 0.86), w), rnd.randrange(int(h * 0.22), h)   # the right margin
        c = rnd.choice((INK, SKY, PURPLE))
        c = tuple(int(a * 0.45 + b * 0.55) for a, b in zip(c, (16, 10, 44)))   # dimmed toward the sky
        d.rectangle((x, y, x + k - 1, y + k - 1), fill=c)
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    for pct in (100, 125, 150, 175, 200, 250):
        s = pct / 100
        banner(s).save(os.path.join(OUT, f'banner-{pct}.png'))
        backdrop(s).save(os.path.join(OUT, f'back-{pct}.png'))
    for k in (3, 4, 5, 6, 8):   # the finish page's raptor, one size per display scaling, on the sky's colour where he stands
        r = raptor(k)
        t = 0.88   # how far down the page he stands: the backdrop's gradient there
        sky_c = tuple(int(a + (b - a) * t) for a, b in zip((9, 9, 34), (22, 12, 54)))
        bg = Image.new('RGB', r.size, sky_c)
        bg.paste(r, (0, 0), r)
        bg.save(os.path.join(OUT, f'raptor-{k}.bmp'))
    for px in (58, 64, 72, 80, 96, 116, 128):
        corner(px).save(os.path.join(OUT, f'corner-{px}.png'))
    print('\n'.join(sorted(os.listdir(OUT))))


if __name__ == '__main__':
    main()
