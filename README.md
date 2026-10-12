# Lorekeeper

Hold **Ctrl+Alt+Space** in a game (or any key or mouse side button you set), ask out loud, let go. Lorekeeper knows which game you're in, looks the answer up on that game's wiki, and reads it to you, without spoilers.

| Game | You say | You hear |
|---|---|---|
| Enter the Gungeon | *"What does the Gilded Hydra do?"* | What it does, then its flavor text: "Heads Up!" |
| Enter the Gungeon | *"What synergy did I just get?"* | Reads the banner from the last few seconds of your screen, then looks it up. |
| Elden Ring | *"Who is Ranni?"* | The lore, up to where you are. |
| Elden Ring | *"I just beat Margit."* | "Noted." Answers now treat that as how far you've got. |
| Elden Ring | *"Where do I go next?"* | The next step only. |
| Elden Ring | *"Spoil it."* | The last question again, with nothing held back. |
| Any game | *"Clip it."* | Presses your clip key (Steam Game Recording or Game Bar). |

## Listen mode
Rather not hold a key? Press **Ctrl+Alt+L** (or tray → **Listen mode**, or say *"start listening"*). Then start a question with **"Lorekeeper, …"**. For 8 seconds after an answer, ask a follow-up without the name. Say just *"Lorekeeper"* and it answers "Yes?" and waits for the question.

The mic stays open, but Whisper only runs when someone's talking, so it's close to free while you're quiet. It ignores everything while Lorekeeper is speaking (so it doesn't hear itself through speakers), while you hold the hotkey, and when no game is in front. Chatting with friends is ignored unless you say the name. Press Ctrl+Alt+L again or say *"stop listening"* to turn it off.

## Gear (Diablo and friends)
Hover an item so its tooltip shows and say *"save this as my helm"*. Lorekeeper reads every stat into that game's gear file. Later:
- *"Is this better than my helm?"* gives the verdict first, then the two or three numbers that decide it, for your build. It uses Sonnet for gear math.
- *"What's my gear?"* lists what's saved. *"Forget my second ring"* removes one.

Slots understand the usual words (helmet/head, chest piece, off hand, second ring…). It works with any game that shows item tooltips.

## Memory
- **Screen:** the last 5 seconds at one frame a second, plus the last 10 minutes at one frame every 10 seconds, all in memory. *"What did that sign say two minutes ago?"* and *"what was that chest earlier?"* send those frames.
- **Saved screens:** *"Remember this as the vault code"* keeps it on disk for that game. *"What was the vault code?"* brings it back.
- **Notes that learn:** besides *"I just beat Margit"* and *"note: …"*, Lorekeeper writes down lasting things your questions reveal: your class, build, act, story choices. Answers fit your run, and the spoiler line moves with you. Everything per game lives in `%APPDATA%\Lorekeeper\games\` as plain files: `<game>.md` (notes), `<game>.gear.json`, `<game>/saved/`.

## How it works
- **Ears:** Whisper (faster-whisper) runs on your PC, so audio never leaves it. It's hinted with the game's name and the names in your notes, so it spells "Malenia" right.
- **Game:** the exe of the window in front, matched against the games Steam, Epic and GOG installed. For an emulator, or if it guesses wrong, say *"I'm playing Chrono Trigger"* or pick from the tray menu.
- **Answer:** the game's wiki pages are fetched first (wiki.gg and Fandom page source, which includes infobox quotes), then `claude -p` on your Claude plan answers from them, or searches if they don't cover it. That's about 3–4 s and about 0.1¢ per ask with Haiku. Say *"in detail"* or *"tell me more"* to use Sonnet.
- **Voice:** [Kokoro](https://github.com/thewh1teagle/kokoro-onnx), a neural voice that runs on your PC. The default is a lower blend of a British woman's voice. Answers are spoken a sentence at a time as they arrive. Tap the hotkey to stop it.
- **Box:** a small box shows the question and answer, on a second monitor if you have one. Click it to copy.

## Setup
Needs Windows, Python 3.10+, and [Claude Code](https://claude.com/claude-code) signed in to a Pro or Max plan.

```powershell
.\setup.ps1
```
Then start **Lorekeeper** from the Start menu (it lives in the tray).

## Settings
Tray → **Settings file** (`%APPDATA%\Lorekeeper\config.json`):

| Key | Default | |
|---|---|---|
| `hotkey` | `ctrl+alt+space` | hold to talk; set it from the tray (any key, combo, or `mouse4`/`mouse5`) |
| `hotkeyEverywhere` | `false` | off: the hotkey only works while a game is in front, so Atticus can share Ctrl+Alt+Space |
| `clipKeys` | `ctrl+f10` | key "clip it" presses. In Steam → Settings → Game Recording, set **"Save the last 30 seconds"** to Ctrl+F10. Or use `win+alt+g` for Game Bar |
| `listen` / `listenKey` | `false` / `ctrl+alt+l` | listen mode and its on/off key |
| `followUpSeconds` | `8` | how long after an answer a follow-up needs no "Lorekeeper" |
| `model` / `deepModel` | `haiku` / `sonnet` | |
| `whisper` | `base.en` | `small.en` hears names better, but is slower on CPU |
| `whisperDevice` | `cpu` | `cuda` with an NVIDIA GPU and the CUDA libraries |
| `voice` | `kokoro` | natural voice on your PC. `edge` = Microsoft online voices, `sapi` = Windows' robotic one |
| `kokoroVoice` | `bf_isabella:0.75,bm_george:0.25` | a voice or a blend; hear them all with tray → **Voice samples** (`lorekeeper.py --voices`) |
| `spoilers` | `false` | also in the tray |
| `screen` | `true` | send screenshots for "what is this" questions |

Notes per game: `%APPDATA%\Lorekeeper\games\<game>.md`, plain markdown you can edit. Ask log: `log.jsonl`.

## Gotchas
- **Game running as admin?** Windows keeps its keys from non-admin apps, so run Lorekeeper as admin too.
- **Exclusive fullscreen** covers the box on that screen, but the voice still works. Most games capture fine through DXGI. If one shows black, Lorekeeper says it couldn't see the screen and goes by your words.
- Anti-cheat: Lorekeeper only reads the screen and listens to one hotkey. "Clip it" sends one key press.

## Command line
```
python lorekeeper.py --ask "what does the casey do"   # typed, printed, for the game in front
python lorekeeper.py --games                          # installed games it knows
```
