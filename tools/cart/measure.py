"""A box round one icon set on a screenshot (pixels) -> its cart region: anchored to the nearest corner, in screen heights.
  python tools/cart/measure.py shot.png --set perks --box X0 Y0 X1 Y1 --slot 119 [--pad 0.03] [--anchor br] [--screen lobby]
--slot: one slot's width in pixels (a diamond: corner to corner). Saves measure_<set>.png with the padded box (magenta)
and one slot (cyan) drawn, to check by eye."""
import argparse, json
from PIL import Image, ImageDraw

p = argparse.ArgumentParser()
p.add_argument('shot'); p.add_argument('--set', required=True)
p.add_argument('--box', type=float, nargs=4, required=True, metavar=('X0', 'Y0', 'X1', 'Y1'))
p.add_argument('--slot', type=float, required=True)
p.add_argument('--pad', type=float, default=0.03, help='screen heights added round the box, for HUD drift between matches')
p.add_argument('--anchor', choices=('tl', 'tr', 'bl', 'br'))
p.add_argument('--screen', default='hud', help="'hud', or 'lobby'... : one screen is up at a time")
a = p.parse_args()
im = Image.open(a.shot).convert('RGB')
W, H = im.size
x0, y0, x1, y1 = a.box
pad = a.pad * H
x0, y0, x1, y1 = max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad)
anchor = a.anchor or ('b' if (y0 + y1) / 2 > H / 2 else 't') + ('r' if (x0 + x1) / 2 > W / 2 else 'l')
xs = (W - x1, W - x0) if anchor[1] == 'r' else (x0, x1)
ys = (H - y1, H - y0) if anchor[0] == 'b' else (y0, y1)
region = {'anchor': anchor, 'x': [round(v / H, 3) for v in xs], 'y': [round(v / H, 3) for v in ys], 'size': round(a.slot / H, 3)}
if a.screen != 'hud':
    region['screen'] = a.screen
if min(xs[1] - xs[0], ys[1] - ys[0]) < a.slot:
    print('warning: the box is smaller than one slot; nothing can be found in it')
d = ImageDraw.Draw(im)
d.rectangle((x0, y0, x1, y1), outline=(255, 0, 255), width=3)
cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
d.rectangle((cx - a.slot / 2, cy - a.slot / 2, cx + a.slot / 2, cy + a.slot / 2), outline=(0, 255, 255), width=2)
im.save(f'measure_{a.set}.png')
print(json.dumps(region))
