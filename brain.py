"""The answer: `claude -p` on the user's Claude plan, with web search and nothing else.
Started at key-down with the game already known, so its ~1 s startup overlaps the talking."""
import atexit, base64, json, os, re, shutil, subprocess, sys, tempfile, threading

if sys.platform == 'win32':
    class _Quiet(subprocess.Popen):   # claude.cmd never flashes a console
        def __init__(self, *a, **k):
            k.setdefault('creationflags', 0x08000000)
            super().__init__(*a, **k)
    POPEN = _Quiet
else:
    POPEN = subprocess.Popen

HOME = os.path.expanduser('~')
os.environ['PATH'] = os.pathsep.join([os.path.join(HOME, '.local', 'bin'), os.path.join(HOME, '.claude', 'local'), os.environ.get('PATH', '')])

SYSTEM = """You are Lorekeeper, a game companion. The player holds a hotkey mid-game, asks out loud, and hears your answer read aloud.

Answer for the game named in the request. Wiki pages fetched for the question may come with it: answer from them when they cover it (no tools needed, fastest), and correct the question kindly if it names things wrong (an item called a synergy). Otherwise look it up: use WebSearch, then WebFetch on the best page, favoring the game's wiki (wiki.gg, Fandom, Fextralife, Game8, the official wiki) over forums. Do not answer specifics from memory alone: item stats, synergies, quest steps and locations change with patches.
Write nothing before or between tool calls. Only the final answer is spoken.

The answer is heard, not read:
- 1 to 3 short sentences. No lists, no markdown, no links, no "according to the wiki".
- Say numbers the way a person would ("about twenty percent").
- Items, synergies, gear, spells: what it does in plain words, what it pairs with if asked, then its in-game flavor text if it has one (wiki infobox "quote" and "desc"; read the quote, plus one line of the description if short), introduced as "Its flavor text:".
- "What is this", "what did I just get": the screenshots are the player's screen at the moment they pressed the key and the seconds before. Read the item or synergy name from them (pickup banners and notifications fade fast; check every frame), then look it up. If no name is readable, say so in one sentence.
- Lore: tell it like a story, a few sentences.
- Unsure or the wiki disagrees with itself: say so briefly.

SPOILER_RULE"""

SPOILER_SAFE = """Spoilers: the player's progress notes below are the horizon. Never reveal story events, character deaths or betrayals, twists, endings, or areas and bosses past that horizon. For "where do I go" give only the next step. If a true answer needs a spoiler, say it would spoil something and that they can say "spoil it". Item effects, builds and mechanics are not spoilers."""
SPOILER_OFF = "Spoilers are on for this answer: answer fully."

DEEP = re.compile(r'\b(in detail|explain|everything about|full (story|lore)|tell me more|go deeper|long version)\b', re.I)


def claude_ok():
    return bool(shutil.which('claude'))


def start(model='haiku', spoilers=False):
    """A `claude -p` waiting for the request on stdin."""
    claude = shutil.which('claude')
    if not claude:
        return None
    d = tempfile.mkdtemp(prefix='lorekeeper-')
    atexit.register(shutil.rmtree, d, True)
    sp = os.path.join(d, 'system.md')   # a file: claude.cmd runs through cmd.exe, which cuts command lines at 8 KB
    with open(sp, 'w', encoding='utf-8') as f:
        f.write(SYSTEM.replace('SPOILER_RULE', SPOILER_OFF if spoilers else SPOILER_SAFE))
    errors = tempfile.TemporaryFile(mode='w+', encoding='utf-8', errors='replace')
    p = POPEN([claude, '-p', '--input-format', 'stream-json', '--output-format', 'stream-json', '--verbose', '--include-partial-messages',
               '--model', model, '--system-prompt-file', sp, '--tools', 'WebSearch,WebFetch', '--permission-mode', 'bypassPermissions',
               '--setting-sources', '', '--no-session-persistence', '--strict-mcp-config', '--disable-slash-commands'],
              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors, text=True, encoding='utf-8', errors='replace', cwd=d)
    p.model, p.spoilers, p.errors = model, spoilers, errors
    atexit.register(stop, p)
    return p


def stop(p):
    if p and p.poll() is None:
        if sys.platform == 'win32':
            subprocess.run(['taskkill', '/T', '/F', '/PID', str(p.pid)], capture_output=True, creationflags=0x08000000)
        else:
            p.kill()


def request(question, game, notes, turns, wiki=''):
    """The text sent with the question: which game, where the player is, the last few turns for "and where is that?"."""
    parts = [f"Game: {game['name']}" + (f" (Steam app {game['id']})" if game.get('source') == 'steam' and game.get('id') else '') if game
             else 'Game: unknown (no game detected; ask which game if it matters)']
    if notes:
        parts.append('Player progress notes (oldest first):\n' + notes)
    if turns:
        parts.append('Recent questions:\n' + '\n'.join(f"Q: {t['q']}\nA: {t['a']}" for t in turns))
    if wiki:
        parts.append('Wiki pages fetched for this question:\n' + wiki)
    parts.append('Question: ' + question)
    return '\n\n'.join(parts)


def ask(p, text, shots=(), on_text=lambda s: None):
    """Sends the request, streams the answer's text to on_text as it arrives -> (answer, usd). shots: [(jpeg path, label)]."""
    content = [b for path, label in shots if os.path.exists(path) for b in (
        {'type': 'text', 'text': label},
        {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(open(path, 'rb').read()).decode()}})]
    content.append({'type': 'text', 'text': text})
    p.stdin.write(json.dumps({'type': 'user', 'message': {'role': 'user', 'content': content}}) + '\n')
    p.stdin.close()
    answer, usd, streamed = '', 0, ''
    for line in p.stdout:
        try:
            j = json.loads(line)
        except ValueError:
            continue
        if j.get('type') == 'stream_event':
            e = j.get('event', {})
            if e.get('type') == 'message_start':
                streamed = ''
            elif e.get('type') == 'content_block_delta' and e.get('delta', {}).get('type') == 'text_delta':
                streamed += e['delta']['text']
                on_text(streamed)
        elif j.get('type') == 'result':
            answer, usd = (j.get('result') or '').strip(), j.get('total_cost_usd', 0)
    p.wait()
    if not answer and p.returncode:
        p.errors.seek(0)
        err = p.errors.read(300)
        answer = 'Claude Code is signed out. Run claude in a terminal to sign in.' if re.search(r'log ?in|auth', err, re.I) else f'Claude failed: {err[:150]}'
    return answer or 'No answer came back.', usd


class Warm:
    """One process started ahead per hotkey press; swapped if the question needs the bigger model or spoilers."""

    def __init__(self):
        self.p, self.lock = None, threading.Lock()

    def prime(self, model, spoilers):
        with self.lock:
            stop(self.p)
            self.p = start(model, spoilers)

    def take(self, model, spoilers):
        with self.lock:
            p, self.p = self.p, None
        if p and (p.poll() is not None or p.model != model or p.spoilers != spoilers):
            stop(p)
            p = None
        return p or start(model, spoilers)

    def drop(self):
        with self.lock:
            stop(self.p)
            self.p = None
