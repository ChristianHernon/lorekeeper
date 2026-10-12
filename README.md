# Lorekeeper

Hold **Ctrl+Alt+G** in a game, ask out loud, let go. Lorekeeper knows which game you're in, looks the answer up on that game's wiki, and reads it to you, without spoilers.

| You say | You hear |
|---|---|
| *"What does the Gilded Hydra do?"* | What it does, then its flavor text: "Heads Up!" |
| *"What synergy did I just get?"* | Reads the banner from the last few seconds of your screen, then looks it up. |
| *"Who is Ranni?"* | The lore, up to where you are. |
| *"I just beat Margit."* | "Noted." Answers now treat that as how far you've got. |
| *"Where do I go next?"* | The next step only. |
| *"Spoil it."* | The last question again, with nothing held back. |
| *"Clip it."* | Presses your clip key (Steam Game Recording or Game Bar). |

## How it works
- **Ears:** Whisper (faster-whisper) runs on your PC, so audio never leaves it. It's hinted with the game's name and the names in your notes, so it spells "Malenia" right.
- **Game:** the exe of the window in front, matched against the games Steam, Epic and GOG installed. For an emulator, or if it guesses wrong, say *"I'm playing Chrono Trigger"* or pick from the tray menu.
- **Answer:** the game's wiki pages are fetched first (wiki.gg and Fandom page source, which includes infobox quotes), then `claude -p` on your Claude plan answers from them, or searches if they don't cover it. That's about 3–4 s and about 0.1¢ per ask with Haiku. Say *"in detail"* or *"tell me more"* to use Sonnet.
- **Voice:** the answer is spoken a sentence at a time as it arrives. Tap the hotkey to stop it.
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
| `hotkey` | `ctrl+alt+g` | hold to talk |
| `clipKeys` | *(empty)* | key "clip it" presses, e.g. your Steam Game Recording clip key, or `win+alt+g` (Game Bar) |
| `model` / `deepModel` | `haiku` / `sonnet` | |
| `whisper` | `base.en` | `small.en` hears names better, but is slower on CPU |
| `whisperDevice` | `cpu` | `cuda` with an NVIDIA GPU and the CUDA libraries |
| `voice` | `sapi` | `edge` for Microsoft's neural voices (online); set the voice with `edgeVoice` |
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
