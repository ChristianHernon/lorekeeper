#!/usr/bin/env python3
"""Lorekeeper: hold Ctrl+Alt+G in a game, ask out loud, let go, hear the answer.

It knows which game is in front (Steam, Epic, GOG installs; or pin one from the tray / "I'm playing X"), looks the
answer up on the game's wiki through `claude -p` on your Claude plan, and reads it aloud. Progress notes per game keep
answers spoiler-safe ("I just beat Margit"); "spoil it" re-asks without the guard. "Clip it" presses your clip key.
  lorekeeper.py                 run (tray icon)
  lorekeeper.py --ask "<q>"     one question for the game in front, typed, printed (no voice)
  lorekeeper.py --games         the installed games it knows, rebuilt
  lorekeeper.py --voices        sample mp3s of the voices, to choose edgeVoice and pitch
Settings: %APPDATA%/Lorekeeper/config.json. Log: log.jsonl beside it.
"""
import json, os, sys, threading, time

if sys.platform == 'win32':
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brain, commands, config, games, lookup, notes, voice  # noqa: E402

LOG = os.path.join(config.DIR, 'log.jsonl')
TURN_SECS = 600
VOICES = ['en-GB-SoniaNeural', 'en-GB-LibbyNeural', 'en-US-AvaNeural', 'en-US-AriaNeural', 'en-US-MichelleNeural',
          'en-US-JennyNeural', 'en-AU-NatashaNeural', 'en-IE-EmilyNeural']   # follow-ups ("and where is that?") see the last few turns from these ten minutes


def log(row):
    os.makedirs(config.DIR, exist_ok=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps({'at': time.strftime('%Y-%m-%d %H:%M:%S'), **row}) + '\n')


class App:
    def __init__(self, cfg, box=None):
        import ears, capture
        self.cfg, self._box = cfg, box
        self.ears = ears.Ears(cfg['whisper'], cfg['whisperDevice'])
        self.voice = voice.Voice(cfg['voice'], cfg['edgeVoice'], cfg['rate'], cfg['pitch'])
        self.warm = brain.Warm()
        self.screen = capture.Screen(active=lambda: bool(self.game))
        self.game, self.gen, self.frames = None, 0, []
        self.turns, self.last, self.last_q, self.spoil_next = [], '', '', False
        self.down_at = 0
        threading.Thread(target=self._watch_game, daemon=True).start()

    def _watch_game(self):
        while True:   # cheap: one window call and a list scan; keeps the tray and the screen buffer current
            try:
                g, exe = games.current()
                if g or not games.LAUNCHERS.search(exe or ''):   # alt-tabbed to a browser or Discord: keep the last game
                    self.game = g
            except Exception as e:
                print('game:', e)
            time.sleep(2)

    @property
    def box(self):
        return self._box if self.cfg['box'] else None

    def say(self, question, answer):
        self.voice.say(answer)
        if self.box:
            self.box.show(question, answer)

    # hotkey
    def down(self):
        self.gen += 1
        self.voice.stop()
        self.down_at = time.time()
        g, _ = games.current()
        self.game = g or self.game
        try:
            self.ears.start()
        except Exception as e:
            return self.say('', f"Can't hear the mic: {e}")
        if self.box:
            self.box.show(f"🎧 {self.game['name'] if self.game else 'Listening'}…", '', stay=True)
        threading.Thread(target=lambda: setattr(self, 'frames', self.screen.now() if self.cfg['screen'] else []), daemon=True).start()
        threading.Thread(target=self.warm.prime, args=(self.cfg['model'], self.cfg['spoilers']), daemon=True).start()

    def cancel(self):
        self.ears.stop()
        self.warm.drop()
        if self.box:
            self.box.hide()

    def up(self):
        gen = self.gen
        audio = self.ears.stop()
        if time.time() - self.down_at < 0.35:   # a tap: that just stopped the voice
            self.warm.drop()
            return self.box and self.box.hide()
        hint = ', '.join(([self.game['name']] if self.game else []) + notes.names(self.game))
        q = self.ears.text(audio, hint)
        if gen != self.gen:
            return
        if not q:
            self.warm.drop()
            return self.say('', "Didn't catch that.")
        self.handle(q, gen)

    def handle(self, q, gen):
        if self.box:
            self.box.show(q, '…', stay=True)
        c = commands.parse(q)
        if c:
            self.warm.drop()
            return self.command(q, *c)
        self.answer(q, gen)

    def command(self, q, action, arg):
        g = self.game
        if action == 'stop':
            self.voice.stop()
            return self.box and self.box.hide()
        if action == 'repeat':
            return self.say(q, self.last or 'Nothing to repeat yet.')
        if action == 'clip':
            if not self.cfg['clipKeys']:
                return self.say(q, 'No clip key set. Put your Steam clip key in the config as clipKeys.')
            import hotkey
            hotkey.press(self.cfg['clipKeys'])
            log({'game': g and g['name'], 'q': q, 'a': 'clipped'})
            return self.box and self.box.show(q, '🎬 Clipped.')   # silent: a voice line would end up in the clip
        if action == 'playing':
            g = games.find(arg, games.index())
            exe, _ = games.win.front()
            games.pin(g, '' if games.LAUNCHERS.search(exe or '') else exe)
            self.game = g
            return self.say(q, f"Got it, {g['name']}.")
        if action == 'auto':
            games.unpin()
            self.game, _ = games.current()
            return self.say(q, f"Detecting games again. Now: {self.game['name']}." if self.game else 'Detecting games again.')
        if action == 'note':
            if not g:
                return self.say(q, "Which game? Say I'm playing, then the name.")
            notes.add(g, arg)
            return self.say(q, 'Noted.')
        if action == 'spoil':
            if not self.last_q:
                self.spoil_next = True
                return self.say(q, 'Spoilers on for the next question.')
            self.spoil_next = True
            return self.answer(self.last_q, self.gen)

    def answer(self, q, gen):
        started = time.time()
        spoilers = self.cfg['spoilers'] or self.spoil_next
        self.spoil_next = False
        model = self.cfg['deepModel'] if brain.DEEP.search(q) else self.cfg['model']
        p = self.warm.take(model, spoilers)
        if not p:
            return self.say(q, 'Claude Code is not installed. Install it and sign in, then ask again.')
        import capture
        shots = capture.Screen.files(self.frames, q) if self.cfg['screen'] and capture.wants(q) else []
        if capture.wants(q) and self.cfg['screen'] and not shots:
            self.voice.say("I couldn't see the screen, so going by your words.")
        now = time.time()
        self.turns = [t for t in self.turns if now - t['t'] < TURN_SECS][-3:]
        wiki = '' if shots else lookup.wiki(q, self.game and self.game['name'])   # a screenshot names the thing; the model searches then
        text = brain.request(q, self.game, notes.read(self.game), self.turns, wiki)
        spoken = []

        def streamed(s):   # speak each sentence as it completes; the last, maybe partial, waits
            if gen != self.gen:
                return
            parts = voice.split(s)[:-1]
            if parts[:len(spoken)] != spoken:
                return   # a new message began (text before a search): wait for the result
            for part in parts[len(spoken):]:
                spoken.append(part)
                self.voice.say(part)
            if self.box:
                self.box.show(q, s, stay=True)
        try:
            a, usd = brain.ask(p, text, shots, streamed)
        finally:
            for path, _ in shots:
                try:
                    os.remove(path)
                except OSError:
                    pass
        if gen != self.gen:
            return
        rest = voice.split(a)
        if rest[:len(spoken)] == spoken:
            rest = rest[len(spoken):]
        else:
            self.voice.stop()   # what was spoken was not the answer after all
        self.voice.say(' '.join(rest))
        if self.box:
            self.box.show(q, a)
        self.last, self.last_q = a, q
        self.turns.append({'t': time.time(), 'q': q, 'a': a})
        log({'game': self.game and self.game['name'], 'q': q, 'a': a, 'usd': round(usd, 5), 'secs': round(time.time() - started, 1),
             'model': model, 'spoilers': spoilers, 'shots': len(shots)})


def tray(app, box):
    import pystray
    from PIL import Image, ImageDraw
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((6, 10, 58, 54), 8, fill=(196, 160, 82))
    d.rectangle((31, 12, 33, 52), fill=(22, 22, 28))
    d.line((14, 22, 26, 22), fill=(22, 22, 28), width=3)
    d.line((38, 22, 50, 22), fill=(22, 22, 28), width=3)

    def pin_to(g):
        def do(*_):
            games.pin(g)
            app.game = g
        return do

    def auto(*_):
        games.unpin()
        app.game, _ = games.current()

    def pick_list():
        gs = sorted({g['name']: g for g in games.index()}.values(), key=lambda g: g['name'].lower())
        return [pystray.MenuItem('Auto-detect', auto, checked=lambda _: games.pinned() is None), pystray.Menu.SEPARATOR] + \
               [pystray.MenuItem(g['name'], pin_to(g), checked=lambda _, n=g['name']: bool(games.pinned()) and games.pinned()['game']['name'] == n)
                for g in gs] + [pystray.Menu.SEPARATOR, pystray.MenuItem('Rescan installed games', lambda *_: games.build())]

    def flip(k):
        def do(*_):
            app.cfg[k] = not app.cfg[k]
            config.save(app.cfg)
        return do

    def quit_(icon, _):
        icon.stop()
        app.warm.drop()
        box.quit()

    menu = pystray.Menu(
        pystray.MenuItem(lambda _: f"Playing: {app.game['name'] if app.game else 'nothing detected'}", None, enabled=False),
        pystray.MenuItem('Pick the game', pystray.Menu(pick_list)),
        pystray.MenuItem('Spoilers', flip('spoilers'), checked=lambda _: app.cfg['spoilers']),
        pystray.MenuItem('Show answers in a box', flip('box'), checked=lambda _: app.cfg['box']),
        pystray.MenuItem('Use the screen', flip('screen'), checked=lambda _: app.cfg['screen']),
        pystray.MenuItem("This game's notes", lambda *_: app.game and (notes.add(app.game, 'notes opened') if not os.path.exists(notes.path(app.game)) else None,
                                                                     os.startfile(notes.path(app.game))), enabled=lambda _: bool(app.game)),
        pystray.MenuItem('Settings file', lambda *_: (config.save(app.cfg), os.startfile(config.FILE))),
        pystray.MenuItem('Voice samples', lambda *_: os.startfile(os.path.join(config.DIR, 'voices')) if os.path.isdir(os.path.join(config.DIR, 'voices')) else None),
        pystray.MenuItem('Ask log', lambda *_: os.path.exists(LOG) and os.startfile(LOG)),
        pystray.MenuItem('Quit', quit_))
    icon = pystray.Icon('Lorekeeper', img, 'Lorekeeper', menu)
    icon.run_detached()
    return icon


def main():
    args = sys.argv[1:]
    cfg = config.load()
    if args[:1] == ['--games']:
        return print('\n'.join(f"{g['name']}  [{g['source']}]  {g['dir']}" for g in games.build()) or 'no games found')
    if args[:1] == ['--voices']:   # sample mp3s to choose edgeVoice and pitch by ear
        folder = os.path.join(config.DIR, 'voices')
        voice.samples(folder, VOICES)
        return print(folder)
    if args[:1] == ['--ask']:
        q = ' '.join(args[1:])
        g, exe = games.current()
        print(f"[{g['name'] if g else 'no game'}]  {exe}")
        p = brain.start(cfg['deepModel'] if brain.DEEP.search(q) else cfg['model'], cfg['spoilers'])
        if not p:
            return print('Claude Code not found')
        t = time.time()
        wiki = lookup.wiki(q, g and g['name'])
        print(f'(wiki {len(wiki)} chars in {time.time() - t:.1f}s)')
        a, usd = brain.ask(p, brain.request(q, g, notes.read(g), [], wiki))
        return print(f'{a}\n(${usd:.4f}, {time.time() - t:.1f}s)')
    import box as boxmod, hotkey
    if not brain.claude_ok():
        print('Claude Code (claude) is not on PATH: install it and sign in first.', file=sys.stderr)
    b = boxmod.Box(cfg['boxSeconds'])
    app = App(cfg, b)
    hk = hotkey.Hotkey(cfg['hotkey'], app.down, app.up, app.cancel)
    threading.Thread(target=hk.run, daemon=True).start()
    tray(app, b)
    b.show('Lorekeeper is ready', f"Hold {cfg['hotkey'].upper()} and ask." + (f" Playing {app.game['name']}." if app.game else ''))
    b.run()


if __name__ == '__main__':
    main()
