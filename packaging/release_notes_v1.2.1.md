Patch release — fixes the "No dungeon node circles found on the map" loop.

If you target a stage in an act that's still chained shut in-game (e.g. a Torment act you haven't unlocked), the map really has no dungeon nodes — v1.2.0 would retry forever. Now:

- The navigator recognizes the chained/padlocked map and reports the act as locked instead of a vision failure.
- The locked stage is automatically removed from your farm targets (the dashboard shows why), so the rest of the farm keeps running. Re-add it from the Add Dungeon picker once you unlock the act.
- Adding a stage beyond your save's progression is rejected up front with the highest currently-unlocked stage in the message.

Everything from v1.2.0 (Torment support, blue-chest pickup, remove-any-dungeon, macro pause switch, portal auto-open) is included. Setup is unchanged: extract, install Tesseract OCR once (`winget install UB-Mannheim.TesseractOCR`), edit `config.py`, run `TBH-TestVision.exe` then `TBH-Macro.exe`.
