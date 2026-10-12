"""Preview sheet for the tray icon: every tray size, 1:1 and zoomed 6x, on light and dark taskbars."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw
import art
SIZES, Z = (16, 20, 24, 32, 48), 6
for listening in (False, True):
    rows = [((243, 243, 243), 'light'), ((32, 32, 32), 'dark')]
    W = 20 + sum(s * Z + 24 for s in SIZES) + 20 + sum(s + 16 for s in SIZES)
    H = len(rows) * (48 * Z + 30) + 10
    sheet = Image.new('RGB', (W, H), (128, 128, 128))
    for i, (bg, _) in enumerate(rows):
        y0 = 10 + i * (48 * Z + 30)
        ImageDraw.Draw(sheet).rectangle((0, y0 - 5, W, y0 + 48 * Z + 15), fill=bg)
        x = 20
        for s in SIZES:
            im = art.image(s, listening)
            sheet.paste(im.resize((s * Z, s * Z), Image.NEAREST), (x, y0), im.resize((s * Z, s * Z), Image.NEAREST))
            x += s * Z + 24
        x += 20
        for s in SIZES:
            im = art.image(s, listening)
            sheet.paste(im, (x, y0 + 4), im)
            x += s + 16
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"tray-{'listening' if listening else 'normal'}.png")
    sheet.save(out)
    print(out)
