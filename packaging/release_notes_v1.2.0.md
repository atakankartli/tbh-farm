Standalone Windows build — no Python required.

**New in v1.2.0:**
- **Torment difficulty** (above Hell) is fully supported: it appears in the Add Dungeon picker with all 27 stages, the navigator selects it in the portal dropdown, and Torment chips get their own color on the dashboard.
- **Remove any dungeon** from the dashboard: every chest card has a ✕ now. Stages you added are deleted; stages from `config.py` are disabled (re-add them from the picker to re-enable — the config file itself is never touched).
- **Macro on/off master switch** in the header: click the "macro" pill to pause everything — while paused the macro never moves your mouse (no navigation, no popup dismissal). Flip it back on from any device on your Wi-Fi.
- **Portal auto-open**: if the PORTAL panel is closed, the macro now finds the blue-sphere toolbar button by vision and clicks it, instead of failing with "is it open?". `TBH-TestVision.exe` reports where it sees the button.
- **Blue chest collection**: after a confirmed clear, the macro looks for the floating chest bubble over the game strip and clicks **blue (stage-boss) chests** — with a 3-click burst since single clicks sometimes don't register. Wooden/white chests are left alone to auto-open.

**Download `tbh-macro-windows-x64.zip` below**, extract it anywhere, and read `README.txt` inside.

Quick start:
1. Install Tesseract OCR (one-time): `winget install UB-Mannheim.TesseractOCR`
2. Edit `config.py` next to the exe (target stages, Tesseract path if non-default)
3. Run `TBH-TestVision.exe` — verifies portal detection without clicking anything
4. Run `TBH-Macro.exe` — farms blue chests and serves live timers at http://localhost:8765

Note: some antivirus tools are suspicious of PyInstaller exes that read the screen and move the mouse. If Defender complains, add a folder exclusion or build from source with `packaging/build.ps1`.
