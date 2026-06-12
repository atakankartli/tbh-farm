# TBH Blue-Chest Farm

A vision-based farming macro for [TBH: Task Bar Hero](https://store.steampowered.com/app/3678970/). It rotates through your chosen dungeons on their 12-minute blue-chest cooldowns: navigates the portal by reading the screen (OCR + shape detection, no fixed coordinates), waits until the game's own log records the chest drop, stashes the loot, and moves on — with a live web dashboard to watch and control it from any device on your Wi-Fi.

## Download

No Python needed: grab `tbh-macro-windows-x64.zip` from the [latest release](https://github.com/atakankartli/tbh-farm/releases/latest), extract it anywhere, and read the `README.txt` inside.

The only prerequisite is Tesseract OCR (one-time):

```
winget install UB-Mannheim.TesseractOCR
```

Then edit `config.py` next to the exe, run `TBH-TestVision.exe` to verify detection (it clicks nothing), and start `TBH-Macro.exe`. The macro starts **paused** — flip the "macro" pill on the dashboard at http://localhost:8765 when you're ready to hand over the mouse.

## What it does

- **Tracks blue-chest cooldowns itself** — each stage's 12-minute timer is stamped from real drops and persists across restarts.
- **Verified drops, no guesswork** — the game writes `GetBoxCount ... ItemKey : 920<level>1` to its `Player.log` the instant a stage-boss (blue) chest drops. The macro stamps a cooldown only when that line appears for the target stage's chest level; cleared runs by themselves prove nothing and it just keeps waiting through chained runs.
- **Vision-based navigation** — finds the PORTAL panel, difficulty dropdown (Normal/Nightmare/Hell/Torment), act tabs and dungeon nodes by OCR and shape detection at any window position or size. Opens the portal via the blue-sphere toolbar button if it's closed, scrolls the map to off-screen stages, recognizes locked (chained) acts, and clicks unopened blue chest bubbles (white ones are left to auto-open).
- **Web dashboard** (`http://localhost:8765`, reachable from your phone) — live cooldown rings, party/stash stats from the decrypted save, recent drop history, add/remove farm dungeons at runtime, and master switches for the macro and auto-stash. Optionally publishes a read-only mirror to GitHub Pages.
- **Stays out of your way** — macro and auto-stash are off by default, a dashboard pill pauses everything instantly, and the cursor parks on empty background after every click.

## How it works

| Source | Used for |
|--------|----------|
| Screen capture + Tesseract OCR / OpenCV | Finding and clicking portal UI (panels, dropdown, tabs, map nodes, chest bubbles) |
| `Player.log` (Unity log, next to the save) | Real-time, authoritative blue-chest drop events |
| `SaveFile_Live.es3` (decrypted ES3 save) | Dashboard stats (gold, party, stash), current-stage detection so an in-progress run is never restarted |

Save decryption and several game-data details build on the reverse-engineering work in [shigake/tbh-copilot](https://github.com/shigake/tbh-copilot).

## Running from source

```
git clone https://github.com/atakankartli/tbh-farm.git
cd tbh-farm
pip install -r requirements.txt
copy config.example.py config.py   # then edit it
python test_vision.py              # verify detection, no clicks
python main.py                     # run the farm
```

Build the standalone zip yourself with `powershell -ExecutionPolicy Bypass -File packaging\build.ps1` (PyInstaller).

## Configuration

Everything lives in `config.py` (plain Python, shipped next to the exe). The essentials:

- `TARGET_STAGES` — seed list of dungeons to farm (you can also add/remove from the dashboard at runtime)
- `TESSERACT_CMD` — path to tesseract.exe if not in the default location
- `WEBGUI_HOST` / `WEBGUI_PORT` — dashboard binding (`0.0.0.0` = phone access on your Wi-Fi)
- `PUBLISH_ENABLED` — optional encrypted GitHub Pages mirror of the dashboard

## Notes

- Windows 10/11 only; multi-monitor and per-monitor DPI scaling are supported.
- Some antivirus tools flag PyInstaller exes that read the screen and move the mouse (which this deliberately does). Add a folder exclusion or build from source.
- The macro moves your real mouse cursor while navigating — run it on a machine you're not actively using, and use the dashboard pill to pause it anytime.
- Personal project, no affiliation with TesseractStudio. Use at your own risk.
