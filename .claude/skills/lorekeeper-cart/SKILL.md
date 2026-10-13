---
name: lorekeeper-cart
description: Build or fix a Lorekeeper cartridge (cart) for a game, meaning its entry in assets/cartridges.json: the wiki to take icons from, the icon sets a player can't name from the art, and where on screen each sits (HUD regions). Use when the user says "make a cart for <game>", "add <game> to Lorekeeper", "Lorekeeper can't read my <perks/items>", or asks to fix a game's HUD regions or icon reading.
---

# Build a Lorekeeper cart

A cart tells Lorekeeper, for one game:
- which wiki to download icons from
- which icon sets to look for (perks, add-ons, status effects...)
- each set's shape (`diamond`, `square`, `ring`)
- **where on screen** each set sits

At question time, Lorekeeper slides every icon's art over those regions and names what it finds exactly (`icons.py`, `find()`).

**Verify on real frames before calling anything done.** The user has been burned by features that only worked in theory. A cart is done when `eval_cart.py` shows everything found, 0 junk, on frames the user captured.

Run everything from the repo root with the repo's Python (`.venv\Scripts\python.exe`, or `./.venv/Scripts/python.exe` from WSL). Tools are in `tools/cart/`.

## 0. Can this game have a cart today?

Check both before starting:
- **Wiki host** must be `*.wiki.gg` or `*.fandom.com` (`icons.HOST`). Other wikis (bg3.wiki, for example) are rejected by the app; tell the user it needs an app change.
- **Icons must share a file-name prefix** on the wiki (`IconPerks_hexRuin.png`, `IconAddon_...`). A set is fetched by prefix. If the icons are named only by the thing ("AC-15.png", as on the Gungeon wiki), the app can't fetch that set yet; say so instead of forcing it.

Worth a cart: things a player sees **only as icons**, with no text label (perks, add-ons, charms, status effects). Skip anything the game labels with text: the AI model reads that from the screenshot already.

## 1. Wiki and icon sets (no user input needed)

```
python tools/cart/wiki_probe.py <host>
```
This prints image categories with the file prefix they share, plus the biggest content categories. `--twins <Prefix_>` lists icons whose file name differs from their page title (useful to know; the app already prefers page titles).

Pick the sets. For each one: `kind` (lowercase words, the name used in answers, e.g. `perks`), `prefix` (e.g. `IconPerks_`) and `shape`.
- **Shape** is what the slot looks like on screen: diamond (a square turned 45°), square, or ring (a circle round the art).
- Add `"needs": "<kind>"` when a set only appears with another set. DbD add-ons need their item; without that rule, menu icons get read as add-ons.
- Add the game's question words to `asks` (e.g. `loadout`, `build`), so "what's my build" reads the icons.

## 2. HUD regions (needs the user)

Ask the user for screenshots at their **native resolution**, and ask what HUD and UI scale they play at:
1. in a match, at a busy moment (buffs and statuses showing)
2. the lobby or loadout screen, if icons show there
3. a second match on a different map, to measure how much the HUD drifts between matches (DbD drifted about 36 px)

Lorekeeper's own grabs are fine. Or have them press Print Screen and save as PNG.

For each set, find the box round all its slots and one slot's width in pixels by looking at the image (crop and zoom; never guess). Then:
```
python tools/cart/measure.py shot.png --set perks --box X0 Y0 X1 Y1 --slot 119 [--pad 0.03] [--screen lobby]
```
It prints the region JSON and saves `measure_<set>.png` with the box drawn. **Open that image and check it.**
- `--slot` is the slot's full width; for a diamond, measure corner to corner.
- Regions are in **screen heights from a corner** (`anchor` tl|tr|bl|br), so other resolutions and ultrawide screens work if the game keeps its HUD in the corners.
- Keep boxes tight against other things of the same shape nearby. In DbD: the item's charge arc beside the item, and the generator counter above it.
- A set can have several regions:
  - one per `screen` (`hud`, `lobby`...). Only the screen with the most finds counts, which stops strays.
  - a separate row of smaller slots, with its own `size`
- Optional per region:
  - `"tints": [{"hue": [160, 210], "kind": "perk buffs on you"}]`: in that region, only slots of that colour count, and they're reported as that kind. Use it only for a row that really means buffs/debuffs. A colour on an equipped icon can just be a cooldown sweep.
  - `"sure": 0.91`: a stricter match threshold, when eval shows junk scoring close to the real icons.

## 3. Write the cart

Add or edit the game in `assets/cartridges.json`, then copy it to `docs/cartridges.json` (they must be identical). The game's key is its exact name as Lorekeeper detects it: the Steam/Epic/GOG title.

Use the Dead by Daylight entry as the worked example.

```
python tools/cart/check.py
```
This must print `ok`. It runs the app's own validation (`icons.valid`) and says what would be dropped and why.

## 4. Prove it on frames

1. Get frames: the user's screenshots, or a recording (every few seconds through a match). Include menus and loading screens: they must read as nothing.
2. Label 15–25 of them in `labels.json`, by looking at each one:
   ```json
   {"frame1.png": {"perks": ["Dark Sense", "Lithe"], "item": ["Commodious Toolbox"]}, "menu.png": {}}
   ```
   `"A|B"` accepts either name, for art the wiki has under two names.
3. Run:
   ```
   python tools/cart/eval_cart.py "<Game Name>" labels.json <frames folder>
   ```
   The first run downloads the icons (perks took ~13 s). It prints, per frame, what was missed or junk, then found/total and junk per set, and seconds per frame.
4. **Target: everything found, 0 junk, under 2 s a frame.** If the cart falls short, fix the cart: regions, sizes, `needs`, `sure`, shape. Change the thresholds in `icons.py` only if the same problem shows in more than one game, and run `python -m pytest -q tests` after.
5. If more frames exist, run them all, not just the labelled ones. On DbD, a 25-frame sample looked perfect, but the full 293 frames still turned up 4 kinds of junk. A name that shows up where it shouldn't is junk, even if the frame wasn't labelled.
6. The frames are the user's screen. Delete them when done, unless the user says to keep them.

## 5. Hand it over

- A cart change needs **no app release**. Installed apps fetch the site's `cartridges.json` at startup.
- Don't deploy the site yourself, and don't push to `main` unless this is the repo owner's own session and they say so. Otherwise:
  1. Commit "Cart: <game>" on a branch `cart/<slug>` (`assets/` and `docs/cartridges.json`).
  2. Push to the user's fork and open a pull request to FindlayHi/lorekeeper.
  3. Put the eval numbers (found/total and junk per set, frames tried, resolution and HUD scale) in the PR body.
- The repo owner reviews, merges and deploys the site.
- Test an unmerged cart with `eval_cart.py`, which reads `assets/cartridges.json` directly. The running app fetches the site's carts at startup and uses those, so it only sees the new cart once the site is deployed.
