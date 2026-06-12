"""Edit these values for your setup."""

import os

# Tracker overlay app (tab bar shows TBH | Runs | Tracker | Settings)
TRACKER_WINDOW_TITLE = "TBH"
# Game UI panels to ignore when finding the tracker window
TRACKER_EXCLUDE_TITLES = ("PORTAL", "HERO", "STASH", "SKILL", "CURSOR", "PYTHON")

# Pick highest character level first when multiple stages are READY
PRIORITIZE_BY_LEVEL = True

# Only farm these stages (same-level chests give the same loot, so one stage
# per chest tier is enough). Format: ("act-stage:DIFFICULTY", chest level).
# Priority = highest level first, then list order.
TARGET_STAGES = (
    ("2-5:HELL", 65),
    ("3-5:NIGHTMARE", 50),
    ("2-3:NORMAL", 50),
    ("1-9:NIGHTMARE", 40),
)

# Blue chests (stage boss) drop on boss kill if this many minutes have passed
# since the dungeon's previous blue drop (verified from drop history).
CHEST_COOLDOWN_MIN = 12

# Self-tracking (no tbh-meter). We stamp drops ourselves and read the save to
# confirm clears. Set True to also fold in tbh-meter's drop log if you run it.
USE_METER_DROPS = False
SAVE_POLL_SEC = 15          # how often runwatch re-reads the save

# A blue chest only drops when a full run completes (boss kill). Gold accrues
# all run long, so we gate on ELAPSED TIME >= the stage's clear time (×margin),
# which guarantees a clear happened; gold-rise is just a "still farming" check.
# Clear times measured from run history (median seconds).
CLEAR_TIME_SEC = {
    "2-5:HELL": 221,
    "3-5:NIGHTMARE": 182,
    "1-9:NIGHTMARE": 164,
    "2-3:NORMAL": 74,
}
CLEAR_TIME_DEFAULT = 300    # for stages with no measured time
CLEAR_TIME_MARGIN = 1.30    # wait this multiple of clear time to be sure
GOLD_SANITY_FLOOR = 3000    # min gold-earned rise proving the game is farming
FALLBACK_CLEAR_SEC = 300    # if the save can't be read, assume cleared after this

# Direct save reading (savefile.py) — decrypts TaskBarHero's ES3 save with no
# OCR/tbh-meter. Password extracted from the game binary by shigake/tbh-copilot.
ES3_PASSWORD = "emuMqG3bLYJ938ZDCfieWJ"
SAVE_FILE = os.path.expanduser(
    r"~\AppData\LocalLow\TesseractStudio\TaskBarHero\SaveFile_Live.es3"
)

# OPTIONAL tbh-meter interop. Not needed for normal operation (we self-track).
# Only used by `--warm` / USE_METER_DROPS to seed cooldowns from its history.
TBH_METER_SETTINGS = os.path.expanduser(r"~\AppData\Roaming\tbh-meter\settings.json")

# Local web GUI with drop timers + farm status
WEBGUI_PORT = 8765
# "0.0.0.0" = reachable from other devices on your Wi-Fi (open the printed
# phone URL). "127.0.0.1" = this PC only.
WEBGUI_HOST = "0.0.0.0"
# True = also open a free public Cloudflare tunnel URL on start (needs
# cloudflared installed: winget install Cloudflare.cloudflared).
WEBGUI_TUNNEL = False

# Public GitHub Pages site (publish.py). One-time: `gh auth login` then
# `python publish.py --setup`. The PC pushes state.json on an interval; the
# Pages dashboard fetches it. Set PUBLISH_ENABLED=True to publish from main.py.
PUBLISH_ENABLED = False
GITHUB_USER = "atakankartli"
GITHUB_REPO = "tbh-farm"                       # public repo -> atakankartli.github.io/tbh-farm
PUBLISH_DIR = os.path.expanduser(r"~\tbh-farm-site")   # gh-pages working copy
PUBLISH_INTERVAL = 90                           # seconds between pushes
# Published state.json is AES-encrypted with this password; the page prompts
# for it and decrypts in the browser (GitHub Pages can't password-protect).
SITE_PASSWORD = "CHANGEME"

# Game window title. PORTAL/HERO/STASH are panels INSIDE this window;
# vision.py finds the PORTAL panel in the capture by its title text.
GAME_WINDOW_TITLE = "TaskBarHero"

# Multi-monitor: absolute screen positions (negative X OK on left-side monitors)
USE_ABSOLUTE_COORDS = True

# Tesseract OCR install path (Windows). Leave None if tesseract is on PATH.
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Seconds between cooldown checks
POLL_INTERVAL = 5

# Give up waiting for a navigated run to clear after this many seconds
RUN_TIMEOUT_SEC = 900

# Stash page tabs to sweep with 'Stash All' after a run (pages can be full)
STASH_PAGES = 5

# How often to look for the game's error popup ('Confirm' button) in seconds
ERROR_CHECK_SEC = 30

# All difficulties the tracker can show (longer names first for OCR matching)
DIFFICULTIES = ("NIGHTMARE", "HELL", "NORMAL")

# Tracker label -> portal dropdown option label
DIFFICULTY_LABELS = {
    "HELL": "Hell",
    "NIGHTMARE": "Nightmare",
    "NORMAL": "Normal",
}

# Vision-based navigation: the PORTAL window is captured and the dropdown,
# act tabs, and dungeon nodes are located by OCR/shape detection each time.
VISION_STEP_DELAY = 0.3       # wait after a click before recapturing
VISION_DROPDOWN_DELAY = 0.5   # wait for the difficulty dropdown to open

# LEGACY (manual coords, used only by calibrate_*/record_combo tools).
PORTAL_UI = {
    "difficulty_dropdown": (-715, 1265),
    "difficulty_options": {
        "HELL": (-703, 1361),
        "NIGHTMARE": (-695, 1336),
        "NORMAL": (-694, 1305),
    },
    "act_tabs": {
        1: (-902, 1322),
        2: (-796, 1324),
        3: (-703, 1327),
    },
    "step_delay": 0.25,
    "dropdown_open_delay": 0.4,
}
