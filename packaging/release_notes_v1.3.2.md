Safer defaults.

- **The macro starts PAUSED**: launching `TBH-Macro.exe` no longer touches your mouse until you click the "macro" pill on the dashboard (http://localhost:8765) to turn it on.
- **Auto-stash is also off by default** — enable it with the "stash" pill.
- If you've toggled these before, your saved settings are kept; the new defaults only apply to fresh installs.

Setup unchanged: extract, install Tesseract OCR once (`winget install UB-Mannheim.TesseractOCR`), edit `config.py`, run `TBH-TestVision.exe` then `TBH-Macro.exe`, and flip the macro pill on.
