"""Found and junk per icon set for one game's cart, on labelled frames (screenshots at native resolution).
  python tools/cart/eval_cart.py "Dead by Daylight" labels.json frames/      (from the repo root)
labels.json: {"frame.jpg": {"perks": ["Dark Sense", ...], "item": [...]}, "menu.jpg": {}}: list what's really on screen;
a kind left out counts as empty. "A|B" accepts either name (the wiki has some art under two names). Icons download once
into %TEMP%\\lk_cart_eval (perks ~13 s). Target: everything found, 0 junk, under 2 s a frame."""
import json, os, re, sys, time
sys.path.insert(0, os.getcwd())
import icons
from PIL import Image

game, labels, frames = sys.argv[1], json.load(open(sys.argv[2], encoding='utf-8')), sys.argv[3]
icons._carts = icons._read('assets/cartridges.json')   # the cart being worked on, not the site's
g = {'name': game}
r = icons.cart(g, '')
if not r:
    sys.exit(f'no cart for {game!r} in assets/cartridges.json (or python tools/cart/check.py drops it)')
folder = os.path.join(os.environ.get('TEMP', '.'), 'lk_cart_eval')
for s in r['sets']:
    if not os.path.exists(icons._bank_path(folder, g, r, s)):
        print('downloading', s['kind'], flush=True)
        icons.download(g, folder, r, s)
bs = icons.banks(g, folder)


def key(n):
    return re.sub(r'[^a-z0-9]', '', re.sub(r' \(or .*', '', n).lower())


tp, fp, fn, ts = {}, {}, {}, []
for f, want in labels.items():
    img = Image.open(os.path.join(frames, f)).convert('RGB')
    t = time.time()
    got = icons.find(img, bs)
    ts.append(time.time() - t)
    by = {}
    for p in got:
        by.setdefault(p['kind'], []).append(p['name'])
    bad = []
    for k in set(want) | set(by):
        w = [{key(a) for a in n.split('|')} for n in want.get(k, [])]
        h = by.get(k, [])
        hit = [n for n in h if any(key(n) in alts for alts in w)]
        miss = [n for n in want.get(k, []) if not any(key(x) in {key(a) for a in n.split('|')} for x in h)]
        tp[k] = tp.get(k, 0) + len(w) - len(miss); fn[k] = fn.get(k, 0) + len(miss); fp[k] = fp.get(k, 0) + len(h) - len(hit)
        bad += [f'junk {k}: {n}' for n in h if n not in hit] + [f'miss {k}: {n}' for n in miss]
    print(f, f'{ts[-1]:.2f}s', '; '.join(bad) or 'ok', flush=True)
for k in sorted(set(tp) | set(fp)):
    print(f"{k:22s} found {tp.get(k, 0)}/{tp.get(k, 0) + fn.get(k, 0)}  junk {fp.get(k, 0)}")
print(f'mean {sum(ts) / len(ts):.2f}s  max {max(ts):.2f}s')
