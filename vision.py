"""Find portal UI elements (difficulty dropdown, act tabs, dungeon nodes) in a
window capture instead of relying on manually calibrated coordinates.

All returned coordinates are window-relative pixels of the captured image;
convert to screen with rect.left + x, rect.top + y.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import cv2
import mss
import numpy as np
import pytesseract

import config
from windows import WindowRect


@dataclass(frozen=True)
class Word:
  text: str
  x: int  # bbox left (window px)
  y: int  # bbox top
  w: int
  h: int
  conf: int

  @property
  def cx(self) -> int:
    return self.x + self.w // 2

  @property
  def cy(self) -> int:
    return self.y + self.h // 2


@dataclass(frozen=True)
class Node:
  cx: int
  cy: int
  stage: int  # 0 = unknown
  label_text: str = ""


def _configure_tesseract() -> None:
  if config.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD


def capture_window(rect: WindowRect) -> np.ndarray:
  with mss.mss() as sct:
    shot = sct.grab(
      {"left": rect.left, "top": rect.top, "width": rect.width, "height": rect.height}
    )
  return cv2.cvtColor(np.array(shot), cv2.COLOR_BGRA2BGR)


def ocr_words(
  image_bgr: np.ndarray, *, thresh: int = 140, scale: int = 4, dark_text: bool = False
) -> list[Word]:
  """Single-threshold OCR pass. dark_text=False reads bright text on dark
  backgrounds; dark_text=True reads dark text on light backgrounds."""
  _configure_tesseract()
  gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
  up = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
  mode = cv2.THRESH_BINARY if dark_text else cv2.THRESH_BINARY_INV
  _, th = cv2.threshold(up, thresh, 255, mode)
  data = pytesseract.image_to_data(th, config="--psm 11", output_type=pytesseract.Output.DICT)

  words: list[Word] = []
  for i, raw in enumerate(data["text"]):
    text = raw.strip()
    if not text:
      continue
    conf = int(float(data["conf"][i]))
    if conf < 25:
      continue
    words.append(
      Word(
        text=text,
        x=data["left"][i] // scale,
        y=data["top"][i] // scale,
        w=data["width"][i] // scale,
        h=data["height"][i] // scale,
        conf=conf,
      )
    )
  return words


def ocr_words_multi(image_bgr: np.ndarray, *, scale: int = 4) -> list[Word]:
  """Merged OCR over several thresholds/polarities. UI text styling varies
  with state (selected tabs: white on bright orange; unselected: dark brown
  on bronze; dropdown: cream on dark) — no single threshold reads them all."""
  merged: list[Word] = []
  for thresh, dark in ((140, False), (170, False), (120, True)):
    for word in ocr_words(image_bgr, thresh=thresh, scale=scale, dark_text=dark):
      duplicate = next(
        (
          i for i, seen in enumerate(merged)
          if seen.text.lower() == word.text.lower()
          and abs(seen.cx - word.cx) <= 8
          and abs(seen.cy - word.cy) <= 8
        ),
        None,
      )
      if duplicate is None:
        merged.append(word)
      elif word.conf > merged[duplicate].conf:
        merged[duplicate] = word
  return merged


# -------------------------------------------------------------- portal panel

# Panels are fixed-size pixel-art UI; offsets are relative to the title text
# found by OCR (measured on reference.image.png).
PANEL_HALF_WIDTH = 220
PANEL_TOP_MARGIN = 30
PANEL_HEIGHT = 630

STASH_HALF_WIDTH = 210
STASH_TOP_MARGIN = 30
STASH_HEIGHT = 660

# OCR garbles the pixel-art STASH title (e.g. 'STHSH'); the 'Stash All' button
# is mixed case, so requiring uppercase keeps them apart.
_STASH_TITLE_RE = re.compile(r"^ST[A-Z]{0,3}SH$")


@dataclass(frozen=True)
class PanelRegion:
  x0: int
  y0: int
  x1: int
  y1: int

  def crop(self, image: np.ndarray) -> np.ndarray:
    return image[self.y0:self.y1, self.x0:self.x1]


def _find_panel(
  image_bgr: np.ndarray, title_match, what: str, half_width: int, top_margin: int, height: int
) -> PanelRegion:
  img_h, img_w = image_bgr.shape[:2]
  # scale=2 is enough for the large title text and much faster on a full capture
  words = ocr_words(image_bgr, scale=2)
  titles = [w for w in words if title_match(w.text)]
  if not titles:
    raise RuntimeError(f"{what} panel not found in game window (is it open?)")
  title = max(titles, key=lambda w: w.conf)
  return PanelRegion(
    x0=max(title.cx - half_width, 0),
    y0=max(title.y - top_margin, 0),
    x1=min(title.cx + half_width, img_w),
    y1=min(title.y + height, img_h),
  )


def find_portal_panel(image_bgr: np.ndarray) -> PanelRegion:
  return _find_panel(
    image_bgr, lambda t: t.upper() == "PORTAL", "PORTAL",
    PANEL_HALF_WIDTH, PANEL_TOP_MARGIN, PANEL_HEIGHT,
  )


def find_stash_panel(image_bgr: np.ndarray) -> PanelRegion:
  return _find_panel(
    image_bgr, lambda t: bool(_STASH_TITLE_RE.match(t)), "STASH",
    STASH_HALF_WIDTH, STASH_TOP_MARGIN, STASH_HEIGHT,
  )


def find_portal_orb(image_bgr: np.ndarray) -> tuple[int, int] | None:
  """The portal-open button on the always-visible toolbar: a blue crystal
  sphere set in an orange octagonal bezel. Distinguished from blue item
  sprites by circularity and from the in-world portal (gray rocks around it)
  by the bezel: the ring around the blob must be mostly orange/bronze."""
  img_h, img_w = image_bgr.shape[:2]
  hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
  blue = cv2.inRange(hsv, (95, 120, 120), (130, 255, 255))
  orange = cv2.inRange(hsv, (8, 110, 90), (28, 255, 255))
  blue = cv2.morphologyEx(blue, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
  contours, _ = cv2.findContours(blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

  best: tuple[float, int, int] | None = None
  for contour in contours:
    area = cv2.contourArea(contour)
    if area < 150:
      continue
    x, y, w, h = cv2.boundingRect(contour)
    circularity = 4 * np.pi * area / max(cv2.arcLength(contour, True), 1) ** 2
    if circularity < 0.35 or not 0.5 <= w / max(h, 1) <= 1.6 or area / (w * h) < 0.4:
      continue
    cx, cy, r = x + w // 2, y + h // 2, max(w, h)
    x0, y0 = max(cx - r, 0), max(cy - r, 0)
    x1, y1 = min(cx + r, img_w), min(cy + r, img_h)
    ring = orange[y0:y1, x0:x1] > 0
    blob = blue[y0:y1, x0:x1] > 0
    bezel = (ring & ~blob).sum() / max((~blob).sum(), 1)
    if bezel < 0.25:
      continue
    score = bezel * area
    if best is None or score > best[0]:
      best = (score, cx, cy)
  return (best[1], best[2]) if best else None


# ------------------------------------------------------------- chest bubbles

@dataclass(frozen=True)
class ChestBubble:
  cx: int
  cy: int
  blue_fraction: float  # of the chest sprite's pixels; ~0 for wooden/white chests

  @property
  def is_blue(self) -> bool:
    return self.blue_fraction >= 0.25


def find_chest_bubbles(image_bgr: np.ndarray, *, min_y: int = 0) -> list[ChestBubble]:
  """Unopened chests float in a speech bubble above the game strip — white for
  normal chests, light-blue-tinted for stage-boss ones (measured: bubble bg
  HSV val>190 sat<75 in both). Detect the bubble, then classify the chest
  sprite inside by color so the caller can click blue (stage-boss) chests and
  leave the rest alone. The cyan water backdrop has high saturation and the
  rocks low value, so neither reads as bubble background."""
  crop = image_bgr[min_y:, :]
  hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
  sat, val = hsv[:, :, 1], hsv[:, :, 2]
  bg_like = ((val > 190) & (sat < 75)).astype(np.uint8) * 255
  bg_like = cv2.morphologyEx(bg_like, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))

  bubbles: list[ChestBubble] = []
  contours, _ = cv2.findContours(bg_like, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
  for contour in contours:
    area = cv2.contourArea(contour)
    if area < 1200:
      continue
    x, y, w, h = cv2.boundingRect(contour)
    # loose shape gates (bubbles can merge with bright rocks in the backdrop);
    # the blue-fraction classification below provides the precision
    if area / (w * h) < 0.55 or not 0.7 <= w / max(h, 1) <= 2.4:
      continue
    # chest sprite = saturated/dark pixels inside the bubble (bg + gray item
    # slots are bright and unsaturated)
    inner_hsv = hsv[y + 6:y + max(int(h * 0.8), 7), x + 6:max(x + w - 6, x + 7)]
    if inner_hsv.size == 0:
      continue
    isat, ival = inner_hsv[:, :, 1], inner_hsv[:, :, 2]
    sprite = ~((ival > 190) & (isat < 75))
    if sprite.sum() < 80:
      continue
    # hue >= 100 excludes the cyan water backdrop (measured hue 80-99)
    blue = (inner_hsv[:, :, 0] >= 100) & (inner_hsv[:, :, 0] <= 135) & (isat >= 90)
    fraction = float((blue & sprite).sum()) / max(int(sprite.sum()), 1)
    bubbles.append(ChestBubble(cx=x + w // 2, cy=min_y + y + h // 2, blue_fraction=fraction))
  return bubbles


# -------------------------------------------------------------- stash panel

STASH_TAB_SPACING = 64  # page tabs are evenly spaced; OCR'd digits anchor the row


def find_stash_tabs(words: list[Word], pages: int = 5) -> dict[int, tuple[int, int]]:
  """Page tab positions. OCR rarely reads every dim tab digit, so detected
  digits anchor an evenly-spaced row and the rest are extrapolated."""
  digits = [
    w for w in words
    if w.y < 150 and w.text.isdigit() and len(w.text) == 1 and 1 <= int(w.text) <= pages
    and w.h >= 8
  ]
  if not digits:
    raise RuntimeError("No stash page-tab digits found")

  # Cluster into rows; use the row with the most digits
  rows: list[list[Word]] = []
  for d in sorted(digits, key=lambda w: w.y):
    for row in rows:
      if abs(row[0].cy - d.cy) <= 8:
        row.append(d)
        break
    else:
      rows.append([d])
  row = max(rows, key=len)

  # Spacing from detected pairs when possible, else the measured constant
  spacings = []
  for a in row:
    for b in row:
      da, db = int(a.text), int(b.text)
      if db > da:
        spacings.append((b.cx - a.cx) / (db - da))
  spacing = sorted(spacings)[len(spacings) // 2] if spacings else STASH_TAB_SPACING

  anchor = row[0]
  anchor_page = int(anchor.text)
  row_y = int(sum(w.cy for w in row) / len(row))
  return {
    page: (int(anchor.cx + spacing * (page - anchor_page)), row_y)
    for page in range(1, pages + 1)
  }


def find_stash_all_button(words: list[Word]) -> tuple[int, int]:
  for word in words:
    if word.text.lower() != "stash":
      continue
    for other in words:
      if other.text.lower() != "all":
        continue
      if abs(other.cy - word.cy) <= word.h and 0 <= other.x - (word.x + word.w) <= word.h * 3:
        return ((word.x + other.x + other.w) // 2, word.cy)
  raise RuntimeError("'Stash All' button not found")


# ---------------------------------------------------------------- difficulty

_DIFFICULTY_PREFIXES = (
  ("NIGHT", "NIGHTMARE"), ("TOR", "TORMENT"), ("HEL", "HELL"), ("NOR", "NORMAL"),
)


def _match_difficulty(text: str) -> str | None:
  upper = re.sub(r"[^A-Z]", "", text.upper())
  for prefix, label in _DIFFICULTY_PREFIXES:
    if upper.startswith(prefix):
      return label
  return None


def find_difficulty_words(words: list[Word]) -> list[tuple[str, Word]]:
  """All difficulty words visible (closed dropdown shows one; open shows the list)."""
  found = []
  for word in words:
    label = _match_difficulty(word.text)
    if label:
      found.append((label, word))
  return found


def read_current_difficulty(words: list[Word]) -> tuple[str, Word]:
  """Closed-dropdown state: the single difficulty word is the current selection."""
  found = find_difficulty_words(words)
  if not found:
    raise RuntimeError("Could not read difficulty dropdown (no Hell/Nightmare/Normal text found)")
  # Closed state has exactly one; if several (dropdown already open), take the topmost.
  found.sort(key=lambda item: item[1].y)
  return found[0]


def find_difficulty_option(words: list[Word], difficulty: str) -> Word:
  """Open-dropdown state: pick the *lowest* match (options render below the button)."""
  matches = [w for label, w in find_difficulty_words(words) if label == difficulty]
  if not matches:
    raise RuntimeError(f"Dropdown open but no '{difficulty}' option found")
  return max(matches, key=lambda w: w.y)


# ----------------------------------------------------------------- act tabs

def find_act_tabs(words: list[Word]) -> dict[int, Word]:
  """The tab row has all acts side by side; the map banner repeats the selected
  act lower down, so group 'Act N' hits by row and keep the biggest/topmost row."""
  hits: list[tuple[int, Word]] = []
  for word in words:
    if word.text.upper() != "ACT":
      continue
    # number can be glued ("Act3") or the next word to the right on the same row
    for other in words:
      if other is word:
        continue
      if not other.text.isdigit():
        continue
      if abs(other.cy - word.cy) > word.h:
        continue
      if 0 <= other.x - (word.x + word.w) <= word.h * 2:
        hits.append((int(other.text), Word(
          text=f"Act {other.text}",
          x=word.x, y=min(word.y, other.y),
          w=other.x + other.w - word.x,
          h=max(word.h, other.h),
          conf=min(word.conf, other.conf),
        )))
        break

  glued = re.compile(r"^ACT\s*(\d)$", re.IGNORECASE)
  for word in words:
    m = glued.match(word.text)
    if m:
      hits.append((int(m.group(1)), word))

  if not hits:
    raise RuntimeError("No 'Act N' tabs found in portal capture")

  # Group hits into rows by vertical proximity
  rows: list[list[tuple[int, Word]]] = []
  for hit in sorted(hits, key=lambda h: h[1].y):
    for row in rows:
      if abs(row[0][1].cy - hit[1].cy) <= 12:
        row.append(hit)
        break
    else:
      rows.append([hit])

  # Tab row: most distinct acts; tie broken by topmost
  rows.sort(key=lambda row: (-len({act for act, _ in row}), row[0][1].y))
  return {act: word for act, word in rows[0]}


# ------------------------------------------------------------- dungeon nodes

_NODE_LABEL_RE = re.compile(r"(\d)\s*-\s*(\d)")


def _green_mask(image_bgr: np.ndarray) -> np.ndarray:
  b, g, r = cv2.split(image_bgr.astype(np.int16))
  return (((g > 140) & (g - r > 60) & (g - b > 60)).astype(np.uint8)) * 255


def _node_circle_mask(image_bgr: np.ndarray) -> np.ndarray:
  """Unlocked node interiors are near-pure white; the current node has a green ring."""
  b, g, r = cv2.split(image_bgr.astype(np.int16))
  white = (b > 225) & (g > 225) & (r > 225)
  return (white.astype(np.uint8)) * 255 | _green_mask(image_bgr)


def _node_text_mask(image_bgr: np.ndarray) -> np.ndarray:
  """Node labels: antialiased bluish-white (not tan terrain) or green pixels."""
  b, g, r = cv2.split(image_bgr.astype(np.int16))
  whiteish = (b > 130) & (g > 140) & (b * 4 > r * 3)
  return (whiteish.astype(np.uint8)) * 255 | _green_mask(image_bgr)


def _find_node_circles(mask: np.ndarray, min_y: int) -> list[tuple[int, int]]:
  closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
  contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
  centers: list[tuple[int, int]] = []
  for contour in contours:
    area = cv2.contourArea(contour)
    if area < 120:
      continue
    x, y, w, h = cv2.boundingRect(contour)
    if y < min_y or w < 14:
      continue
    if not 0.6 < w / max(h, 1) < 1.7:
      continue
    if area / (w * h) < 0.5:
      continue
    centers.append((x + w // 2, y + h // 2))
  return centers


def _ocr_node_label(image_bgr: np.ndarray, mask: np.ndarray, cx: int, cy: int) -> str:
  height, width = mask.shape[:2]
  x0, x1 = min(cx + 10, width), min(cx + 80, width)
  y0, y1 = max(cy - 14, 0), min(cy + 16, height)
  roi = mask[y0:y1, x0:x1]
  if roi.size == 0:
    return ""
  up = cv2.resize(roi, None, fx=6, fy=6, interpolation=cv2.INTER_NEAREST)
  up = cv2.morphologyEx(up, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
  up = cv2.GaussianBlur(up, (3, 3), 0)
  _, th = cv2.threshold(up, 80, 255, cv2.THRESH_BINARY_INV)
  return pytesseract.image_to_string(
    th, config="--psm 7 -c tessedit_char_whitelist=0123456789-[]"
  ).strip()


def find_dungeon_nodes(image_bgr: np.ndarray, act: int, *, map_top: int = 0) -> list[Node]:
  """Detect unlocked node circles and resolve their stage numbers.

  OCR reads whatever labels it can; circle order anchors the rest (the path
  climbs bottom -> top with consecutive stage numbers, so one readable label
  fixes every other circle, including labels hidden behind the flag marker).
  """
  _configure_tesseract()
  mask = _node_text_mask(image_bgr)
  centers = _find_node_circles(_node_circle_mask(image_bgr), map_top)
  if not centers:
    raise RuntimeError("No dungeon node circles found on the map")

  centers.sort(key=lambda c: -c[1])  # bottom first = lowest stage

  labels: list[str] = []
  offsets: list[int] = []  # stage_number - circle_index
  for index, (cx, cy) in enumerate(centers):
    text = _ocr_node_label(image_bgr, mask, cx, cy)
    labels.append(text)
    match = _NODE_LABEL_RE.search(text)
    # Only the stage digit matters: the act is fixed by the selected tab, and
    # OCR misreads the act digit anyway (e.g. '[2-3]' -> '[4-3]').
    if match and 1 <= int(match.group(2)) <= 9:
      offsets.append(int(match.group(2)) - index)

  if not offsets:
    raise RuntimeError(
      f"Found {len(centers)} node circles but could not read any 'act-stage' label "
      f"(OCR saw: {labels})"
    )

  # Majority vote in case one label was misread
  offset = max(set(offsets), key=offsets.count)

  return [
    Node(cx=cx, cy=cy, stage=offset + index, label_text=labels[index])
    for index, (cx, cy) in enumerate(centers)
  ]


def find_stage_node(image_bgr: np.ndarray, act: int, stage: int, *, map_top: int = 0) -> Node:
  nodes = find_dungeon_nodes(image_bgr, act, map_top=map_top)
  for node in nodes:
    if node.stage == stage:
      return node
  visible = ", ".join(f"{act}-{n.stage}" for n in nodes)
  raise RuntimeError(f"Stage {act}-{stage} not visible on map (visible: {visible})")
