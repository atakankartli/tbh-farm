TBH Blue-Chest Macro — Windows release
======================================

Farms TaskBarHero blue chests on a 12-minute cooldown: navigates the portal
by screen vision, confirms clears from the save file, stashes loot, and
serves a timer dashboard at http://localhost:8765.

No Python needed — everything is bundled in this folder.

REQUIREMENTS
------------
1. Windows 10/11, TaskBarHero running and visible.
2. Tesseract OCR (the only thing you must install yourself):
       winget install UB-Mannheim.TesseractOCR
   Default install path is C:\Program Files\Tesseract-OCR\tesseract.exe —
   if you installed it elsewhere, set TESSERACT_CMD in config.py.

SETUP
-----
1. Extract this zip anywhere (e.g. C:\tbh-macro). Don't run it from inside
   the zip.
2. Open config.py in any text editor and adjust:
       TARGET_STAGES   — the stages you want to farm
       TESSERACT_CMD   — path to tesseract.exe if not the default
   The rest of the defaults usually work as-is.
3. Verify detection first (takes a screenshot, clicks nothing):
       TBH-TestVision.exe
   It should report the PORTAL panel and dungeon nodes it found, and writes
   _vision_debug.png so you can see what it detected.
4. Run the farm:
       TBH-Macro.exe
   Open http://localhost:8765 — the macro starts PAUSED (it won't touch your
   mouse): click the "macro" pill in the dashboard header to turn it on.
   The "stash" pill (auto Stash All after runs) is also off by default.
   Ctrl+C in the console stops it.

NOTES
-----
- Drop history / cooldown state is saved in the _internal folder, so
  restarting the exe does not reset timers.
- Some antivirus tools flag freshly built PyInstaller exes as suspicious
  (this macro also reads the screen and moves the mouse, which looks
  bot-like because it is one). If Windows Defender quarantines it, add an
  exclusion for the folder — or build it yourself from source:
  https://github.com/atakankartli/tbh-farm
- The macro moves your real mouse cursor while navigating; it's meant to run
  on a machine (or monitor) you're not actively using.
