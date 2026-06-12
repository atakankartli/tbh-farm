Standalone Windows build — no Python required.

**New in v1.1.0 — control the farm from the dashboard:**
- **Add Dungeon** button in the Chest Timers section: pick difficulty + stage (with names and levels from the game data), and the macro starts farming it on its next poll — no restart, no config editing. Runtime-added dungeons show a ✕ to remove them; chest level auto-fills from the stage. Stored in `_internal/macro_targets.json`, so they survive restarts.
- **Stash toggle** pill in the header: click to turn the post-run "Stash All" sweep on/off (default: on, persisted in `_internal/macro_settings.json`). Takes effect from the next cleared run.
- The published GitHub Pages mirror stays read-only — editing is only available on the local dashboard.

**Download `tbh-macro-windows-x64.zip` below**, extract it anywhere, and read `README.txt` inside.

Quick start:
1. Install Tesseract OCR (one-time): `winget install UB-Mannheim.TesseractOCR`
2. Edit `config.py` next to the exe (target stages, Tesseract path if non-default)
3. Run `TBH-TestVision.exe` — verifies portal detection without clicking anything
4. Run `TBH-Macro.exe` — farms blue chests and serves live timers at http://localhost:8765

Note: some antivirus tools are suspicious of PyInstaller exes that read the screen and move the mouse. If Defender complains, add a folder exclusion or build from source with `packaging/build.ps1`.
