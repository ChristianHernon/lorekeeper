import os, sys, tempfile

os.environ['LOREKEEPER_DIR'] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
import json  # noqa: E402
import icons  # noqa: E402


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
    bank = icons.Bank(art, [f'Perk {i}' for i in range(40)], 'diamond', 'perks')
    D, c = 122, (2321, 1161)
    s = 0.73 * D
    hud = [(c[0], c[1] - s, D), (c[0] - s, c[1], D), (c[0] + s, c[1], D), (c[0], c[1] + s, D)]
    pick = [3, 17, 25, 38]
    got = icons.find(screen(hud, art[pick]), [bank])
    assert [p['name'] for p in got] == ['Perk 3', 'Perk 17', 'Perk 25', 'Perk 38']   # top, left, right, bottom


def test_small_lobby_cluster_and_nothing_on_a_plain_screen():
    art = np.stack([icon(s) for s in range(40)])
    bank = icons.Bank(art, [f'Perk {i}' for i in range(40)], 'diamond', 'perks')
    D, c, s = 62, (2328, 282), 40
    lobby = [(c[0], c[1] - s, D), (c[0] - s, c[1], D), (c[0] + s, c[1], D), (c[0], c[1] + s, D)]
    assert len(icons.find(screen(lobby, art[[1, 2, 3, 4]]), [bank])) == 4
    assert icons.find(screen([], art[:0]), [bank]) == []


def squares(boxes, art):
    """A dark screen with square slots (blue fill, the art on top) -> image."""
    im = Image.new('RGB', (2560, 1440), (28, 30, 32))
    d = ImageDraw.Draw(im)
    for (cx, cy, D), a in zip(boxes, art):
        d.rectangle((cx - D / 2, cy - D / 2, cx + D / 2, cy + D / 2), fill=(30, 60, 110))
        side = round(D * 0.9)
        im.paste(Image.new('RGB', (side, side), (235, 235, 235)), (round(cx - side / 2), round(cy - side / 2)), Image.fromarray(a).resize((side, side)))
    return im


def test_item_and_add_ons_but_not_a_lone_square():
    art = np.stack([icon(s) for s in range(100, 130)])
    items = icons.Bank(art[:10], [f'Item {i}' for i in range(10)], 'square', 'item')
    addons = icons.Bank(art[10:], [f'Add-on {i}' for i in range(20)], 'square', 'add-ons')
    hud = [(270, 1210, 104), (152, 1178, 46), (152, 1246, 46)]
    got = icons.find(squares(hud, [art[4], art[15], art[22]]), [items, addons])
    assert sorted((p['kind'], p['name']) for p in got) == [('add-ons', 'Add-on 12'), ('add-ons', 'Add-on 5'), ('item', 'Item 4')]
    assert icons.find(squares([(1800, 600, 60)], [art[15]]), [items, addons]) == []   # alone: a sign or a status icon


def test_twin_art_takes_the_page_name():
    art = np.stack([icon(s) for s in range(200, 210)])
    art = np.concatenate([art, art[3:4]])
    b = icons.Bank(art, [f'A {i}' for i in range(10)] + ['Spool of Wire'], 'square', 'add-ons', [False] * 10 + [True])
    hud = [(400, 400, 50), (400, 470, 50)]
    got = icons.find(squares(hud, [art[3], art[7]]), [b])
    assert {p['name'] for p in got} == {'Spool of Wire', 'A 7'}


def test_recipes_shipped_match_the_site_and_bad_ones_are_dropped():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, 'assets', 'recipes.json'), encoding='utf-8') as f:
        shipped = json.load(f)
    with open(os.path.join(root, 'docs', 'recipes.json'), encoding='utf-8') as f:
        assert json.load(f) == shipped   # the site serves what the app ships
    good = icons.valid(shipped)
    assert [s['kind'] for s in good['dead by daylight']['sets']] == ['perks', 'item', 'add-ons']
    bad = {'games': {'A': {'host': '127.0.0.1', 'sets': [{'kind': 'perks', 'prefix': 'X', 'shape': 'diamond'}]},
                     'B': {'host': 'evil.example.com', 'sets': [{'kind': 'perks', 'prefix': 'X', 'shape': 'diamond'}]},
                     'C': {'host': 'c.wiki.gg', 'sets': [{'kind': 'perks', 'prefix': '../x', 'shape': 'diamond'}, {'kind': 'x', 'prefix': 'Y', 'shape': 'blob'}]},
                     'D': {'host': 'd.fandom.com', 'sets': [{'kind': 'cards', 'prefix': 'Card_', 'shape': 'square'}]}}}
    assert list(icons.valid(bad)) == ['d']
    assert icons.valid('nope') == {} and icons.valid({'games': {'E': None}}) == {}


def test_names_from_wiki_files():
    assert icons._name('IconPerks hexNoOneEscapesDeath.png', ['Perks', 'Hex: No One Escapes Death']) == ('Hex: No One Escapes Death', True)
    assert icons._name('IconPerks_aNursesCalling.png', ["A Nurse's Calling", 'Achievements']) == ("A Nurse's Calling", True)
    assert icons._name('IconPerks windowsOfOpportunity.png', []) == ('Windows Of Opportunity', False)
    assert icons._name('IconAddon_4-coilSpringKit.png', [], 'IconAddon_') == ('4-coil Spring Kit', False)


def test_questions_about_the_icons():
    folder = tempfile.mkdtemp()
    dbd = {'name': 'Dead by Daylight'}
    assert icons.recipe(dbd, folder) and not icons.recipe({'name': 'Hades'}, folder) and not icons.recipe(None, folder)
    for q in ('what perks do I have', 'is my build good', 'what add-on is this', 'which item am I holding', 'what is my loadout'):
        assert icons.asks(q, dbd, folder), q
    assert not icons.asks('where is the exit gate', dbd, folder) and not icons.asks('what perks', {'name': 'Hades'}, folder)
