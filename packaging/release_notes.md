Standalone Windows build — no Python required.

**Download `tbh-macro-windows-x64.zip` below**, extract it anywhere, and read `README.txt` inside.

Quick start:
1. Install Tesseract OCR (one-time): `winget install UB-Mannheim.TesseractOCR`
2. Edit `config.py` next to the exe (target stages, Tesseract path if non-default)
3. Run `TBH-TestVision.exe` — verifies portal detection without clicking anything
4. Run `TBH-Macro.exe` — farms blue chests and serves live timers at http://localhost:8765

What's in the box:
- `TBH-Macro.exe` — the farm loop (vision-based navigation, save-file clear detection, self-tracked 12-min chest cooldowns, auto stash, web dashboard)
- `TBH-TestVision.exe` — detection sanity check, writes `_vision_debug.png`
- `config.py` — all settings, plain text, edit freely
- Cooldown state persists in `_internal/` across restarts

Note: some antivirus tools are suspicious of PyInstaller exes that read the screen and move the mouse. If Defender complains, add a folder exclusion or build from source with `packaging/build.ps1`.
