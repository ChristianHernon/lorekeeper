"""Where Lorekeeper keeps its files, and its settings (config.json, edited by hand or from the tray)."""
import json, os

HOME = os.path.expanduser('~')
DIR = os.environ.get('LOREKEEPER_DIR') or os.path.join(os.environ.get('APPDATA') or os.path.join(HOME, '.config'), 'Lorekeeper')   # tests point it elsewhere
FILE = os.path.join(DIR, 'config.json')

DEFAULTS = {
    'hotkey': 'ctrl+alt+g',      # hold to talk, let go to ask
    'model': 'haiku',            # quick answers; "in detail" asks use deepModel
    'deepModel': 'sonnet',
    'whisper': 'base.en',        # base.en is quick on CPU; small.en hears names better
    'whisperDevice': 'cpu',      # cuda with an NVIDIA card and the CUDA libraries
    'voice': 'sapi',             # sapi (Windows, offline) or edge (nicer, online)
    'edgeVoice': 'en-US-AndrewNeural',
    'rate': 0,                   # SAPI speed, -10..10
    'box': True,                 # show the question and answer in a small box too
    'boxSeconds': 12,
    'spoilers': False,           # True: answers ignore your progress notes
    'screen': True,              # "what is this item" sends a screenshot
    'clipKeys': '',              # "clip it" presses this: Steam Game Recording's clip key, or Game Bar's win+alt+g
}


def load():
    try:
        with open(FILE, encoding='utf-8') as f:
            return {**DEFAULTS, **json.load(f)}
    except (OSError, ValueError):
        return dict(DEFAULTS)


def save(cfg):
    os.makedirs(DIR, exist_ok=True)
    with open(FILE, 'w', encoding='utf-8') as f:
        json.dump({k: v for k, v in cfg.items() if DEFAULTS.get(k) != v}, f, indent=1)
