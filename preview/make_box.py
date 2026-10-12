"""Screenshots of the answer box with sample content, on a stand-in backdrop. Run with Windows Python from the repo root."""
import os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import tkinter as tk
from PIL import ImageGrab
import box as boxmod

CASES = [
    ('short', 'What does the Gilded Hydra do?', 'Fires a spread of golden shots that split on hit. Flavor text: "Heads Up!"'),
    ('long', 'Where do I go after Margit?',
     "Head up the stairs past Margit's arena into Stormveil Castle. Inside, take the side path through the courtyard rather "
     "than the main gate, since the gate is guarded by ballistae. Light the Site of Grace at the Rampart Tower, then follow "
     "the ramparts north to reach Godrick. Rest at Secluded Cell before the boss and summon Nepheli if you need help."),
    ('listening', '👂 Listening…', ''),
    ('game', '🎧 Enter the Gungeon…', ''),
    ('clipped', 'Clip that', '🎬 Clipped.'),
]
only = sys.argv[1:]
b = boxmod.Box(30)
back = tk.Toplevel(b.root)
back.overrideredirect(True)
cv = tk.Canvas(back, highlightthickness=0, width=900, height=700)
cv.pack()
for i in range(0, 700, 4):   # a dusky stand-in for a game
    cv.create_rectangle(0, i, 900, i + 4, width=0, fill='#%02x%02x%02x' % (40 + i // 12, 60 + i // 14, 80 + i // 20))
todo = [c for c in CASES if not only or c[0] in only]


def step():
    if not todo:
        return b.root.destroy()
    name, q, a = todo.pop(0)
    b.show(q, a, stay=True)

    def grab():
        r = b.root
        x, y, w, h = r.winfo_rootx(), r.winfo_rooty(), r.winfo_width(), r.winfo_height()
        back.geometry(f'{w + 48}x{h + 48}+{x - 24}+{y - 24}')
        back.lift(); r.lift()
        r.update()
        time.sleep(0.4)
        img = ImageGrab.grab((x - 24, y - 24, x + w + 24, y + h + 24), all_screens=True)
        out = os.path.join(ROOT, 'preview', f'box-{name}.png')
        img.save(out)
        print(out, img.size)
        b.root.after(100, step)
    b.root.after(500, grab)


b.root.after(300, step)
b.run()
