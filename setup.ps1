# TBH macro one-time setup (run in PowerShell)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== TBH Macro Setup ===" -ForegroundColor Cyan

Write-Host "`n[1/3] Python packages..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Write-Host "`n[2/3] Tesseract OCR..."
$tesseract = "C:\Program Files\Tesseract-OCR\tesseract.exe"
if (Test-Path $tesseract) {
  Write-Host "  Tesseract already installed at $tesseract" -ForegroundColor Green
} else {
  Write-Host "  Installing Tesseract via winget..."
  try {
    winget install --id UB-Mannheim.TesseractOCR -e --accept-source-agreements --accept-package-agreements
  } catch {
    Write-Host "  winget install failed. Install manually:" -ForegroundColor Yellow
    Write-Host "  https://github.com/UB-Mannheim/tesseract/wiki"
  }
}

Write-Host "`n[3/3] Verify imports..."
python -c "import cv2, mss, pyautogui, pytesseract, keyboard; print('  All imports OK')"

Write-Host "`n=== Done ===" -ForegroundColor Green
Write-Host @"

Next steps:
  1. Edit config.py window titles if needed
  2. Verify tracker OCR:           python test_tracker.py
  3. Verify portal vision (open PORTAL in game, no clicks):
       python test_vision.py       # prints detections + saves _vision_debug.png
  4. Run macro:                    python main.py
  (No calibration needed — the PORTAL window is captured and read each time.)

"@
