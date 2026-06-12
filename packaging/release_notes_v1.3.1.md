Half the download size, and the macro now waits for the actual blue drop.

- **Wait for the drop, not the clear.** A cleared run means nothing by itself — the game chains runs on the stage, so the macro now stays put through dropless clears until `Player.log` records the `920<level>1` blue-chest drop, then stamps the cooldown. Timeout without a drop → nothing stamped, 3-minute backoff.
- **Download is ~40% smaller** (≈63 MB zip, was ≈100 MB): removed opencv's unused ffmpeg video codec and packages the bundler dragged in for nothing (pandas, lxml, pytz, Cython, Tcl/Tk).
- **Map scrolling fixed**: v1.3.0's faster drags broke the game's drag recognition, and the cursor was parked in the same frame as the drag release (the game polls the cursor, so releases could register at the park spot and fling the map). Drags are deliberate again, with a settle before parking, and one missed drag no longer flips the scroll direction.
- **Act tabs read reliably**: when OCR can't read every tab (selection styling / Torment theme), missing tabs are computed from the row geometry — the three tabs are evenly spaced, so one readable tab fixes all three.

Setup unchanged: extract, install Tesseract OCR once (`winget install UB-Mannheim.TesseractOCR`), edit `config.py`, run `TBH-TestVision.exe` then `TBH-Macro.exe`.
