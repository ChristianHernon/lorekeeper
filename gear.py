"""Saved gear per game: "save this as my helm" reads the hovered tooltip (one Claude call) into <game>.gear.json.
Questions about gear then carry the whole set, so "is this better than my helm?" works when the helm isn't on screen,
and the AI can total stats across slots. Plain JSON, edit freely."""
import json, os, re, time
import notes

SLOTS = {   # what people say -> the slot it's saved under
    'helm': 'helm', 'helmet': 'helm', 'head': 'helm', 'hat': 'helm', 'hood': 'helm', 'crown': 'helm', 'mask': 'helm',
    'chest': 'chest', 'body': 'chest', 'armor': 'chest', 'armour': 'chest', 'chest piece': 'chest', 'chestpiece': 'chest', 'torso': 'chest',
    'gloves': 'gloves', 'hands': 'gloves', 'gauntlets': 'gloves',
    'pants': 'pants', 'legs': 'pants', 'leggings': 'pants', 'legs armor': 'pants',
    'boots': 'boots', 'feet': 'boots', 'shoes': 'boots',
    'shoulders': 'shoulders', 'pauldrons': 'shoulders', 'bracers': 'bracers', 'wrists': 'bracers', 'belt': 'belt', 'waist': 'belt',
    'amulet': 'amulet', 'necklace': 'amulet', 'neck': 'amulet', 'talisman': 'amulet',
    'ring': 'ring 1', 'first ring': 'ring 1', 'ring one': 'ring 1', 'ring 1': 'ring 1', 'left ring': 'ring 1',
    'second ring': 'ring 2', 'other ring': 'ring 2', 'ring two': 'ring 2', 'ring 2': 'ring 2', 'right ring': 'ring 2',
    'weapon': 'main hand', 'main hand': 'main hand', 'mainhand': 'main hand', 'main weapon': 'main hand', 'primary': 'main hand',
    'two hander': 'main hand', 'two-hander': 'main hand', 'sword': 'main hand', 'bow': 'main hand', 'staff': 'main hand',
    'off hand': 'off hand', 'offhand': 'off hand', 'shield': 'off hand', 'focus': 'off hand', 'second weapon': 'off hand', 'secondary': 'off hand',
}
GEARISH = re.compile(r'\b(better|worse|upgrade|downgrade|compare|swap|equip|gear|item|stats?|dps|damage|toughness|armou?r|resist\w*|'
                     r'crit\w*|build|aspect|affix\w*|legendary|unique|my (?:' + '|'.join(sorted({re.escape(k) for k in SLOTS}, key=len, reverse=True)) + r'))\b', re.I)


def slot(words):
    w = re.sub(r'^(?:my|the|new|current)\s+', '', words.strip().lower().strip(' .!?'))
    w = re.sub(r'\s+(?:slot|piece)$', '', w)
    return SLOTS.get(w, w)


def path(game):
    return os.path.join(notes.FOLDER, notes.slug(game['name']) + '.gear.json')


def load(game):
    if not game:
        return {}
    try:
        with open(path(game), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save(game, where, item):
    allg = load(game)
    allg[where] = {**item, 'saved': time.strftime('%Y-%m-%d %H:%M')}
    os.makedirs(notes.FOLDER, exist_ok=True)
    with open(path(game), 'w', encoding='utf-8') as f:
        json.dump(allg, f, indent=1, ensure_ascii=False)


def forget(game, where):
    allg = load(game)
    if allg.pop(where, None) is None:
        return False
    with open(path(game), 'w', encoding='utf-8') as f:
        json.dump(allg, f, indent=1, ensure_ascii=False)
    return True


def line(where, item):
    bits = [f"{where}: {item.get('name', '?')}"]
    for k in ('rarity', 'type', 'power'):
        if item.get(k):
            bits.append(str(item[k]))
    out = ' | '.join(bits)
    if item.get('stats'):
        out += '\n  ' + '; '.join(item['stats'])
    if item.get('aspect'):
        out += '\n  power: ' + item['aspect']
    return out


def text(game):
    """All saved gear, one slot per entry, for the prompt."""
    return '\n'.join(line(k, v) for k, v in sorted(load(game).items()))


def wants(question):
    return bool(GEARISH.search(question))


def summary(game):
    g = load(game)
    if not g:
        return 'No gear saved for this game yet. Hover an item and say: save this as my helm.'
    return 'Saved: ' + ', '.join(f"{v.get('name', '?')} as your {k}" for k, v in sorted(g.items())) + '.'
