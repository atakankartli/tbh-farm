Patch release.

- **Don't restart a run in progress**: if the game is already parked on the stage that came off cooldown, the macro no longer re-clicks its dungeon node (which restarted the run from scratch) — it skips navigation and just waits for the clear.
- **Clear-time learning hardened**: a PC sleep mid-wait could record an absurd clear time (observed: 3 hours). Measurements longer than the run timeout are discarded and stored values clamp to 30–600s.

Includes everything from v1.2.0/v1.2.1. Setup unchanged: extract, install Tesseract OCR once (`winget install UB-Mannheim.TesseractOCR`), edit `config.py`, run `TBH-TestVision.exe` then `TBH-Macro.exe`.
