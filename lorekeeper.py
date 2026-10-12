#!/usr/bin/env python3
"""Lorekeeper: hold Ctrl+Alt+Space in a game, ask out loud, let go, hear the answer.

It knows which game is in front (Steam, Epic, GOG installs; or pin one from the tray / "I'm playing X"), looks the
answer up on the game's wiki through `claude -p` on your Claude plan, and reads it aloud. Progress notes per game keep
answers spoiler-safe ("I just beat Margit"); "spoil it" re-asks without the guard. "Clip it" presses your clip key.
  lorekeeper.py                 run (tray icon)
  lorekeeper.py --ask "<q>"     one question for the game in front, typed, printed (no voice)
  lorekeeper.py --games         the installed games it knows, rebuilt
  lorekeeper.py --voices        sample wavs of the voices, to choose kokoroVoice
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
import brain, capture, commands, config, games, gear, listen, lookup, notes, voice  # noqa: E402

LOG = os.path.join(config.DIR, 'log.jsonl')
TURN_SECS = 600

def _rm(path):
    try:
        os.remove(path)
    except OSError:
        pass


def log(row):
    os.makedirs(config.DIR, exist_ok=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps({'at': time.strftime('%Y-%m-%d %H:%M:%S'), **row}) + '\n')


class App:
    def __init__(self, cfg, box=None):
        import ears, capture
        self.cfg, self._box = cfg, box
        self.ears = ears.Ears(cfg['whisper'], cfg['whisperDevice'])
        self.voice = voice.Voice(cfg['voice'], cfg['edgeVoice'], cfg['rate'], cfg['pitch'], cfg['kokoroVoice'], config.MODELS)
        self.warm = brain.Warm()
        self.screen = capture.Screen(active=lambda: bool(self.game))
        self.game, self.gen, self.frames = None, 0, []
        self.turns, self.last, self.last_q, self.spoil_next = [], '', '', False
        self.down_at, self._spoke_at, self.hk = 0, 0, None
        self.listener = listen.Listener(self.ears, self.heard, self.listen_muted, cfg['followUpSeconds'], self.woke, self.hint)
        if cfg['listen']:
            self.set_listen(True, quiet=True)
        self._games, self._pin = games.index(), games.pinned()   # in memory: the hook asks in_game() on every press
        threading.Thread(target=self._watch_game, daemon=True).start()

    def in_game(self):
        """Is a game in front right now? No file reads: it runs inside the keyboard hook."""
        if self.cfg['hotkeyEverywhere']:
            return True
        exe, title = games.win.front()
        if not exe or games.LAUNCHERS.search(exe):
            return False
        return bool(self._pin) or bool(games.match(exe, title, self._games))

    def _watch_game(self):
        while True:   # cheap: one window call and a list scan; keeps the tray and the screen buffer current
            try:
                g, exe = games.current()
                self._games, self._pin = games.index(), games.pinned()
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
        if self.listener.on:
            self.after_speaking()

    def hint(self):
        return ', '.join(([self.game['name']] if self.game else []) + notes.names(self.game))

    def after_speaking(self):
        """Once the answer has been said, a follow-up needs no wake word for a few seconds."""
        def wait():
            time.sleep(0.3)
            while self.voice.busy():
                time.sleep(0.1)
            self.listener.follow_up()
        threading.Thread(target=wait, daemon=True).start()

    # listen mode
    def set_listen(self, on, quiet=False):
        try:
            self.listener.start() if on else self.listener.stop()
        except Exception as e:
            return self.say('', f"Can't hear the mic: {e}")
        self.cfg['listen'] = on
        config.save(self.cfg)
        if not quiet:
            self.say('Listen mode', 'Listening. Say Lorekeeper, then your question.' if on else 'Stopped listening.')

    def toggle_listen(self):
        self.set_listen(not self.listener.on)

    def listen_muted(self):
        """Skip the mic: it would hear Lorekeeper's own voice, the hotkey is in use, or no game is in front."""
        now = time.time()
        if self.voice.busy():
            self._spoke_at = now
            return True
        return now - self._spoke_at < 0.5 or bool(self.hk and self.hk.held) or not self.in_game()

    def woke(self):
        self.voice.say('Yes?')
        if self.box:
            self.box.show('👂 Listening…', '', stay=True)

    def heard(self, q):
        self.gen += 1
        g, _ = games.current()
        self.game = g or self.game
        self.frames = self.screen.now() if self.cfg['screen'] else []
        self.handle(q, self.gen)

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
        q = self.ears.text(audio, self.hint())
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
        if action in ('listen_on', 'listen_off'):
            return self.set_listen(action == 'listen_on')
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
        if action.startswith('gear') or action == 'snap':
            if not g:
                return self.say(q, "Which game? Say I'm playing, then the name.")
            return self.gear_command(q, action, arg, g)
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

    def gear_command(self, q, action, arg, g):
        if action == 'gear_list':
            return self.say(q, gear.summary(g))
        if action == 'gear_forget':
            where = gear.slot(arg)
            return self.say(q, f'Forgot your {where}.' if gear.forget(g, where) else f'No {where} was saved.')
        if not self.frames:
            return self.say(q, "I can't see the screen, so I can't save it.")
        if action == 'snap':
            capture.save_shot(notes.FOLDER, g, self.frames[-1][1], arg)
            return self.say(q, f'Saved the screen as {arg}.' if arg else 'Saved the screen.')
        where = gear.slot(arg)   # gear_save: read the hovered tooltip
        if self.box:
            self.box.show(q, f'Reading the item for your {where}…', stay=True)
        shots = capture.Screen.files(self.frames[-1:], '')
        try:
            item = brain.extract(shots, self.cfg['model'])
        finally:
            for path, _ in shots:
                _rm(path)
        if item.get('error') or not item.get('name'):
            return self.say(q, "I couldn't read an item there. Hover over it so its tooltip shows, then say it again.")
        gear.save(g, where, item)
        log({'game': g['name'], 'q': q, 'a': f'saved {where}', 'item': item})
        return self.say(q, f"Saved {item['name']} as your {where}.")

    def answer(self, q, gen):
        started = time.time()
        spoilers = self.cfg['spoilers'] or self.spoil_next
        self.spoil_next = False
        shots = capture.Screen.files(self.frames, q) if self.cfg['screen'] and capture.wants(q) else []
        saved = capture.saved_for(notes.FOLDER, self.game, q)   # on disk for good: never deleted below
        kit = gear.text(self.game) if gear.wants(q) else ''
        model = self.cfg['deepModel'] if brain.DEEP.search(q) or (kit or shots) and gear.wants(q) else self.cfg['model']   # gear math: the bigger model
        p = self.warm.take(model, spoilers)
        if not p:
            return self.say(q, 'Claude Code is not installed. Install it and sign in, then ask again.')
        if capture.wants(q) and self.cfg['screen'] and not shots and not saved:
            self.voice.say("I couldn't see the screen, so going by your words.")
        now = time.time()
        self.turns = [t for t in self.turns if now - t['t'] < TURN_SECS][-3:]
        wiki = '' if shots or saved or kit else lookup.wiki(q, self.game and self.game['name'])   # a screenshot names the thing; the model searches then
        text = brain.request(q, self.game, notes.read(self.game), self.turns, wiki, kit)
        spoken = []

        def streamed(s):   # speak each sentence as it completes; the last, maybe partial, waits
            if gen != self.gen:
                return
            s = brain.spoken(s)   # the saved note and any Sources list are never spoken
            parts = voice.split(s)[:-1]
            if parts[:len(spoken)] != spoken:
                return   # a new message began (text before a search): wait for the result
            for part in parts[len(spoken):]:
                spoken.append(part)
                self.voice.say(part)
            if self.box:
                self.box.show(q, s, stay=True)
        try:
            a, usd = brain.ask(p, text, saved + shots, streamed)
        finally:
            for path, _ in shots:
                _rm(path)
        a, learned = brain.split_note(a)
        if learned and self.game:
            notes.add(self.game, learned + ' (learned)')
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
        if self.listener.on:
            self.after_speaking()
        self.last, self.last_q = a, q
        self.turns.append({'t': time.time(), 'q': q, 'a': a})
        log({'game': self.game and self.game['name'], 'q': q, 'a': a, 'usd': round(usd, 5), 'secs': round(time.time() - started, 1),
             'model': model, 'spoilers': spoilers, 'shots': len(shots), 'saved': len(saved), 'gear': bool(kit), 'learned': learned})


def tray(app, box):
    import hotkey, pystray
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
            app.game, app._pin = g, games.pinned()
        return do

    def auto(*_):
        games.unpin()
        app._pin = None
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

    def set_hotkey(*_):
        box.show('Set the hotkey', 'Press the key, combo or mouse side button you want. Esc to cancel.', stay=True)

        def done(combo):
            if combo:
                app.cfg['hotkey'] = combo
                config.save(app.cfg)
            box.show('Hotkey', f"Hold {hotkey.pretty(app.hk.combo)} and ask." if combo else 'Unchanged.')
        app.hk.record(done)

    def set_listen_key(*_):
        box.show('Set the listen key', 'Press the key or combo that turns listen mode on and off. Esc to cancel.', stay=True)

        def done(combo):
            if combo:
                app.cfg['listenKey'] = combo
                config.save(app.cfg)
            box.show('Listen key', f"{hotkey.pretty(app.lk.combo)} turns listen mode on and off." if combo else 'Unchanged.')
        app.lk.record(done)

    menu = pystray.Menu(
        pystray.MenuItem(lambda _: f"Playing: {app.game['name'] if app.game else 'nothing detected'}", None, enabled=False),
        pystray.MenuItem('Pick the game', pystray.Menu(pick_list)),
        pystray.MenuItem(lambda _: f'Hotkey: {hotkey.pretty(app.hk.combo)}  (change…)', set_hotkey),
        pystray.MenuItem('Listen mode (say "Lorekeeper, …")', lambda *_: app.toggle_listen(), checked=lambda _: app.listener.on),
        pystray.MenuItem(lambda _: f'Listen key: {hotkey.pretty(app.lk.combo)}  (change…)', set_listen_key),
        pystray.MenuItem('Hotkey works outside games too', flip('hotkeyEverywhere'), checked=lambda _: app.cfg['hotkeyEverywhere']),
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
    if args[:1] == ['--voices']:   # sample wavs to choose kokoroVoice by ear
        folder = os.path.join(config.DIR, 'voices')
        voice.samples(folder, config.MODELS)
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
        a, usd = brain.ask(p, brain.request(q, g, notes.read(g), [], wiki, gear.text(g) if gear.wants(q) else ''))
        a, learned = brain.split_note(a)
        if learned and g:
            notes.add(g, learned + ' (learned)')
        return print(f'{a}\n(${usd:.4f}, {time.time() - t:.1f}s)' + (f'\n[noted: {learned}]' if learned else ''))
    import box as boxmod, hotkey
    if not brain.claude_ok():
        print('Claude Code (claude) is not on PATH: install it and sign in first.', file=sys.stderr)
    b = boxmod.Box(cfg['boxSeconds'])
    app = App(cfg, b)
    try:
        hk = hotkey.Hotkey(cfg['hotkey'], app.down, app.up, app.cancel, app.in_game)
    except ValueError:
        hk = hotkey.Hotkey(config.DEFAULTS['hotkey'], app.down, app.up, app.cancel, app.in_game)
    app.hk = hk
    threading.Thread(target=hk.run, daemon=True).start()
    try:
        lk = hotkey.Hotkey(cfg['listenKey'], app.toggle_listen, lambda: None)
    except ValueError:
        lk = hotkey.Hotkey(config.DEFAULTS['listenKey'], app.toggle_listen, lambda: None)
    app.lk = lk
    threading.Thread(target=lk.run, daemon=True).start()
    tray(app, b)
    b.show('Lorekeeper is ready', f"Hold {hotkey.pretty(hk.combo)} in a game and ask." + (f" Playing {app.game['name']}." if app.game else ''))
    b.run()


if __name__ == '__main__':
    main()
