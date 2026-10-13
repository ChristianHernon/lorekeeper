import os, sys, tempfile

os.environ['LOREKEEPER_DIR'] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
import perks  # noqa: E402


def icon(seed):
    """Made-up perk art: white strokes on black, 96 x 96, like the wiki's icons."""
    rng = np.random.default_rng(seed)
    im = Image.new('L', (96, 96))
    d = ImageDraw.Draw(im)
    for _ in range(7):
        x0, y0, x1, y1 = rng.integers(22, 74, 4)
        d.line((x0, y0, x1, y1), fill=255, width=3)
    d.ellipse(tuple(rng.integers(25, 45, 2)) + tuple(rng.integers(55, 72, 2)), outline=255, width=3)
    return np.asarray(im)


def screen(slots, art, dim=()):
    """A dark game screen with perk diamonds (purple fill, the art on top) -> image. dim: slots on cooldown."""
    im = Image.new('RGB', (2560, 1440), (28, 30, 32))
    d = ImageDraw.Draw(im)
    d.rectangle((300, 300, 900, 700), fill=(140, 30, 30))   # a red wall: coloured, but no diamond
    for i, (cx, cy, D) in enumerate(slots):
        h = D / 2
        fill = (40, 18, 46) if i in dim else (100, 47, 117)
        d.polygon([(cx, cy - h), (cx + h, cy), (cx, cy + h), (cx - h, cy)], fill=fill)
        side = round(D * 1.2)
        a = Image.fromarray(art[i]).resize((side, side))
        white = Image.new('RGB', (side, side), (120, 120, 120) if i in dim else (235, 235, 235))
        im.paste(white, (round(cx - side / 2), round(cy - side / 2)), a)
    return im


def test_finds_and_names_the_hud_cluster():
    art = np.stack([icon(s) for s in range(40)])
    bank = perks.Bank(art, [f'Perk {i}' for i in range(40)])
    D, c = 122, (2321, 1161)
    s = 0.73 * D
    hud = [(c[0], c[1] - s, D), (c[0] - s, c[1], D), (c[0] + s, c[1], D), (c[0], c[1] + s, D)]
    pick = [3, 17, 25, 38]
    got = perks.find(screen(hud, art[pick]), bank)
    assert [p['name'] for p in got] == ['Perk 3', 'Perk 17', 'Perk 25', 'Perk 38']   # top, left, right, bottom


def test_small_lobby_cluster_and_nothing_on_a_plain_screen():
    art = np.stack([icon(s) for s in range(40)])
    bank = perks.Bank(art, [f'Perk {i}' for i in range(40)])
    D, c, s = 62, (2328, 282), 40
    lobby = [(c[0], c[1] - s, D), (c[0] - s, c[1], D), (c[0] + s, c[1], D), (c[0], c[1] + s, D)]
    assert len(perks.find(screen(lobby, art[[1, 2, 3, 4]]), bank)) == 4
    assert perks.find(screen([], art[:0]), bank) == []


def test_names_from_wiki_files():
    assert perks._name('IconPerks hexNoOneEscapesDeath.png', ['Perks', 'Hex: No One Escapes Death']) == 'Hex: No One Escapes Death'
    assert perks._name('IconPerks_aNursesCalling.png', ["A Nurse's Calling", 'Achievements']) == "A Nurse's Calling"
    assert perks._name('IconPerks windowsOfOpportunity.png', []) == 'Windows Of Opportunity'


def test_only_known_games_and_perk_questions():
    assert perks.spec({'name': 'Dead by Daylight'}) and not perks.spec({'name': 'Hades'}) and not perks.spec(None)
    assert perks.ASKS.search('what perks do I have') and perks.ASKS.search('is my build good')
    assert not perks.ASKS.search('where is the exit gate')
