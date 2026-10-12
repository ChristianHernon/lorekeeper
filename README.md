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

## How it works
- **Ears:** Whisper (faster-whisper) runs on your PC, so audio never leaves it. It's hinted with the game's name and the names in your notes, so it spells "Malenia" right.
- **Game:** the exe of the window in front, matched against the games Steam, Epic and GOG installed. For an emulator, or if it guesses wrong, say *"I'm playing Chrono Trigger"* or pick from the tray menu.
- **Answer:** the game's wiki pages are fetched first (wiki.gg and Fandom page source, which includes infobox quotes), then `claude -p` on your Claude plan answers from them, or searches if they don't cover it. That's about 3–4 s and about 0.1¢ per ask with Haiku. Say *"in detail"* or *"tell me more"* to use Sonnet.
- **Voice:** [Kokoro](https://github.com/thewh1teagle/kokoro-onnx), a neural voice that runs on your PC. The default is a lower blend of a British woman's voice. Answers are spoken a sentence at a time as they arrive. Tap the hotkey to stop it.
- **Box:** a small box shows the question and answer, on a second monitor if you have one. Click it to copy.
- **Screen:** while a game is in front, one frame a second is kept in memory (last 5). Only questions like "this" or "just got" send frames; "just" sends the last few, so a faded pickup banner still counts.

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
| `clipKeys` | *(empty)* | key "clip it" presses, e.g. your Steam Game Recording clip key, or `win+alt+g` (Game Bar) |
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
