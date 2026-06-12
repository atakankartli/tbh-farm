Patch release — fixes "Could not set difficulty to TORMENT after 5 attempts".

After clicking a difficulty option, the mouse cursor was left hovering over the dropdown, hiding the selected label from the vision system — so the macro couldn't tell the difficulty was already set and kept re-clicking. Now:

- Every click and drag parks the cursor on empty game background before the next screen capture, so it can never occlude UI text.
- Captures where the dropdown button (and any stray OCR duplicates) already read the target difficulty are recognized as "already set".

Includes everything from v1.2.0–v1.2.2. Setup unchanged: extract, install Tesseract OCR once (`winget install UB-Mannheim.TesseractOCR`), edit `config.py`, run `TBH-TestVision.exe` then `TBH-Macro.exe`.
