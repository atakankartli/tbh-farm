from __future__ import annotations

import re
from dataclasses import dataclass

import cv2
import mss
import numpy as np
import pytesseract

import config
from windows import WindowRect, find_tracker_window


@dataclass(frozen=True)
class ReadyStage:
  label: str  # e.g. "2-5"
  act: int
  stage: int
  difficulty: str  # HELL / NIGHTMARE / NORMAL
  level: int = 0


# Main row: "Stage 2-5 HELL ... READY" (ignore sub-rows like "3-9 NO 20%")
_STAGE_ROW_RE = re.compile(
  r"Stage\s*(\d+)\s*[-–]\s*(\d+)",
  re.IGNORECASE,
)
_READY_RE = re.compile(r"READY", re.IGNORECASE)

# OCR often garbles difficulty text on the Stage line ('Ni@rmare', 'NELL',
# 'MISHTMARE'...). Match the most distinctive fragment of each word; order
# matters (check NIGHTMARE before HELL: garbled forms can contain 'ELL'-like
# noise, but 'MARE' appears only in Nightmare).
_DIFFICULTY_PATTERNS: tuple[tuple[str, str], ...] = (
  (r"MARE|NIGHT|NI\W?[GR]", "NIGHTMARE"),
  (r"[HNM]EL{1,2}\b|\bELL\b|\bHE\b(?!\s*\d)", "HELL"),
  (r"NORMAL|MORMAL|[NM]OR[MN]|\bNO\b(?!\s*\d)", "NORMAL"),
)

# OCR garbles Lv30 -> Lv3e, Lv65 -> Lves, etc.
_LEVEL_OCR_MAP = str.maketrans({
  "o": "0", "O": "0",
  "e": "0", "E": "0",
  "s": "5", "S": "5",
  "a": "4", "A": "4",
  "v": "6", "V": "6",
  "b": "8", "B": "8",
  "l": "1", "L": "1",
  "i": "1", "I": "1",
  "z": "2", "Z": "2",
})


def _configure_tesseract() -> None:
  if config.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD


def capture_tracker(tracker_rect: WindowRect) -> np.ndarray:
  with mss.mss() as sct:
    shot = sct.grab(
      {
        "left": tracker_rect.left,
        "top": tracker_rect.top,
        "width": tracker_rect.width,
        "height": tracker_rect.height,
      }
    )
  bgr = cv2.cvtColor(np.array(shot), cv2.COLOR_BGRA2BGR)
  return bgr


def _ocr_lines(image_bgr: np.ndarray) -> list[str]:
  gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
  gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
  _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
  text = pytesseract.image_to_string(thresh, config="--psm 6")
  return [line.strip() for line in text.splitlines() if line.strip()]


def _parse_difficulty(text: str) -> str:
  upper = text.upper()
  for pattern, difficulty in _DIFFICULTY_PATTERNS:
    if re.search(pattern, upper):
      return difficulty
  return "NORMAL"


def _parse_chest_level(line: str) -> int:
  """
  Parse chest level from the line under the stage row, e.g. 'Lv30', 'Lv3e', 'Lves'.
  Level badge sits under the blue chest icon on the left.
  """
  first = line.split()[0] if line.split() else line
  if not first.lower().startswith("lv"):
    m = re.search(r"\bLv\s*(\S+)", line, re.IGNORECASE)
    if not m:
      return 0
    first = "Lv" + m.group(1)

  def _decode(body: str) -> int:
    if not body:
      return 0
    translated = body.translate(_LEVEL_OCR_MAP)
    digits = [c for c in translated if c.isdigit()]
    if len(digits) >= 2:
      return int(digits[0] + digits[-1])
    if len(digits) == 1:
      return int(digits[0] + "0")
    return 0

  val_short = _decode(first[2:])
  if 10 <= val_short <= 99:
    return val_short

  val_long = _decode(first[1:])
  if 10 <= val_long <= 99:
    return val_long

  return val_short or val_long


def parse_ready_stages(image_bgr: np.ndarray) -> list[ReadyStage]:
  """Parse main Stage rows only (not sub-stage detail lines)."""
  _configure_tesseract()
  lines = _ocr_lines(image_bgr)
  ready: list[ReadyStage] = []

  for i, line in enumerate(lines):
    if not _READY_RE.search(line):
      continue
    stage_match = _STAGE_ROW_RE.search(line)
    if not stage_match:
      continue

    act = int(stage_match.group(1))
    stage = int(stage_match.group(2))
    difficulty = _parse_difficulty(line)

    # Chest level is on the next line under the icon
    level = 0
    if i + 1 < len(lines):
      level = _parse_chest_level(lines[i + 1])

    ready.append(
      ReadyStage(
        label=f"{act}-{stage}",
        act=act,
        stage=stage,
        difficulty=difficulty,
        level=level,
      )
    )

  # De-dupe
  seen: set[tuple[str, str]] = set()
  unique: list[ReadyStage] = []
  for item in ready:
    token = (item.label, item.difficulty)
    if token in seen:
      continue
    seen.add(token)
    unique.append(item)

  if config.PRIORITIZE_BY_LEVEL:
    unique.sort(key=lambda s: s.level, reverse=True)

  return unique


def get_ready_stages() -> list[ReadyStage]:
  rect = find_tracker_window()
  frame = capture_tracker(rect)
  return parse_ready_stages(frame)


def debug_tracker() -> tuple[list[str], list[ReadyStage], WindowRect]:
  _configure_tesseract()
  rect = find_tracker_window()
  frame = capture_tracker(rect)
  lines = _ocr_lines(frame)
  ready = parse_ready_stages(frame)
  return lines, ready, rect
