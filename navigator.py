"""Vision-based portal navigation: capture the game window, locate the PORTAL
panel inside it, find the UI elements with OCR/shape detection, and click
them. No calibrated coordinates.
"""

from __future__ import annotations

import time

import numpy as np

import config
from tracker import ReadyStage
from vision import (
  PanelRegion,
  capture_window,
  find_act_tabs,
  find_chest_bubbles,
  find_difficulty_words,
  find_dungeon_nodes,
  find_portal_orb,
  find_portal_panel,
  find_stash_all_button,
  find_stash_panel,
  find_stash_tabs,
  map_is_locked,
  ocr_words,
  ocr_words_multi,
)
from win32_coords import click_screen, drag_screen
from windows import WindowRect, find_game_window

STEP_DELAY = getattr(config, "VISION_STEP_DELAY", 0.3)
DROPDOWN_DELAY = getattr(config, "VISION_DROPDOWN_DELAY", 0.5)
SCROLL_PX = 140  # map drag distance per scroll attempt


class StageLockedError(RuntimeError):
  """The act's map is chained shut in-game (e.g. a Torment act not yet
  unlocked) — retrying won't help until the player progresses."""


def _click_neutral(rect: WindowRect) -> None:
  """Click empty game background (below the panels) to dismiss any topmost
  shell popup overlapping the capture region."""
  print("    panel obscured? clicking neutral game area to dismiss popups")
  click_screen(rect.left + 500, rect.top + 800)
  time.sleep(0.5)


class Portal:
  """One navigation session: the panel is located once, then every capture
  re-grabs the window and crops the same region (the panel does not move
  between the few clicks of a route)."""

  def __init__(self) -> None:
    self.rect: WindowRect = find_game_window(activate=True).refresh()
    try:
      self.region: PanelRegion = find_portal_panel(capture_window(self.rect))
    except RuntimeError:
      # A topmost shell popup (e.g. tray flyout) can cover the panel; a click
      # on empty game background dismisses it.
      _click_neutral(self.rect)
      try:
        self.region = find_portal_panel(capture_window(self.rect))
      except RuntimeError:
        # Panel genuinely closed — open it via the blue-sphere toolbar button.
        self.region = self._open_portal()
    print(
      f"  Game window {self.rect.width}x{self.rect.height} @ ({self.rect.left}, {self.rect.top}); "
      f"portal panel at ({self.region.x0}, {self.region.y0})-({self.region.x1}, {self.region.y1})"
    )

  def _open_portal(self) -> PanelRegion:
    """Click the blue-sphere toolbar button that opens the PORTAL panel."""
    orb = find_portal_orb(capture_window(self.rect))
    if orb is None:
      raise RuntimeError("PORTAL panel not open and the blue-sphere portal button "
                         "was not found in the game window")
    print(f"    portal closed -> clicking blue-sphere button @ window({orb[0]}, {orb[1]})")
    click_screen(self.rect.left + orb[0], self.rect.top + orb[1])
    time.sleep(DROPDOWN_DELAY)
    return find_portal_panel(capture_window(self.rect))

  def capture(self) -> np.ndarray:
    return self.region.crop(capture_window(self.rect))

  def capture_words(self):
    image = self.capture()
    return image, ocr_words_multi(image)

  def click(self, x: int, y: int, label: str) -> None:
    """x, y are panel-relative."""
    screen_x = self.rect.left + self.region.x0 + x
    screen_y = self.rect.top + self.region.y0 + y
    print(f"    click {label} @ panel({x}, {y}) -> screen({screen_x}, {screen_y})")
    click_screen(screen_x, screen_y)

  def drag(self, x: int, y: int, dy: int, label: str) -> None:
    """Vertical drag from panel-relative (x, y)."""
    screen_x = self.rect.left + self.region.x0 + x
    screen_y = self.rect.top + self.region.y0 + y
    print(f"    drag {label}: panel({x}, {y}) by {dy:+d}px")
    drag_screen(screen_x, screen_y, screen_x, screen_y + dy)


def _ensure_difficulty(portal: Portal, difficulty: str) -> None:
  """Observe-act loop: each pass captures the panel and reacts to its state
  (dropdown closed / open / options still rendering) until the closed
  dropdown shows the target difficulty."""
  for _attempt in range(5):
    _, words = portal.capture_words()
    found = sorted(find_difficulty_words(words), key=lambda item: item[1].y)
    if not found:
      # mid-animation capture (dropdown closing/re-rendering) — re-observe
      time.sleep(0.4)
      continue

    current_label, button = found[0]      # topmost = the dropdown button itself
    options = found[1:]                   # anything below it = open option list

    if not options:  # dropdown closed
      if current_label == difficulty:
        print(f"    difficulty is {difficulty}")
        return
      portal.click(button.cx, button.cy, f"difficulty dropdown (showing {current_label})")
      time.sleep(DROPDOWN_DELAY)
      continue

    target = [w for label, w in options if label == difficulty]
    if target:
      portal.click(target[0].cx, target[0].cy, f"difficulty option {difficulty}")
      time.sleep(STEP_DELAY)
      continue  # next pass verifies the closed dropdown shows the target

    time.sleep(0.3)  # open but target not visible yet (render lag) — re-observe

  raise RuntimeError(f"Could not set difficulty to {difficulty} after 5 attempts")


def _find_node_scrolling(portal: Portal, act: int, stage: int, map_top: int):
  """Find the stage node, dragging the map when it is off-screen (e.g. x-1
  below or x-9 above the default view). Higher stages sit higher on the map,
  so revealing them means dragging the content down. If a drag changes
  nothing (wrong direction or map edge), the direction is inverted once."""
  panel_h = portal.region.y1 - portal.region.y0
  drag_x, drag_y = 70, (map_top + panel_h) // 2  # map area, clear of the node column
  direction = 1
  inverted = False
  last_seen: tuple[int, int] | None = None

  for attempt in range(8):
    image = portal.capture()
    try:
      nodes = {n.stage: n for n in find_dungeon_nodes(image, act, map_top=map_top)}
    except RuntimeError as exc:
      if map_is_locked(image, map_top=map_top):
        raise StageLockedError(f"act {act} is locked (map is chained shut)") from exc
      raise
    if stage in nodes:
      return nodes[stage]

    lo, hi = min(nodes), max(nodes)
    print(f"    stage {act}-{stage} not visible (map shows {act}-{lo}..{act}-{hi})")

    if (lo, hi) == last_seen:
      if inverted:
        raise RuntimeError(f"Stage {act}-{stage} not reachable by scrolling (stuck at {act}-{lo}..{act}-{hi})")
      direction, inverted = -direction, True
    last_seen = (lo, hi)

    dy = direction * (SCROLL_PX if stage > hi else -SCROLL_PX)
    portal.drag(drag_x, drag_y, dy, "scroll map")
    time.sleep(STEP_DELAY)

  raise RuntimeError(f"Stage {act}-{stage} not found after scrolling")


def go_to_stage(target: ReadyStage) -> None:
  portal = Portal()

  _ensure_difficulty(portal, target.difficulty)

  _, words = portal.capture_words()
  tabs = find_act_tabs(words)
  tab = tabs.get(target.act)
  if tab is None:
    raise RuntimeError(f"Act {target.act} tab not found (saw acts: {sorted(tabs)})")
  portal.click(tab.cx, tab.cy, f"act {target.act} tab")
  time.sleep(STEP_DELAY)

  map_top = max(t.y + t.h for t in tabs.values()) + 5
  node = _find_node_scrolling(portal, target.act, target.stage, map_top)
  portal.click(node.cx, node.cy, f"dungeon {target.act}-{target.stage}")
  time.sleep(STEP_DELAY)


def _find_confirm_button(words) -> "Word | None":
  for word in words:
    if word.text.strip().rstrip(".").lower() == "confirm" and word.conf >= 40:
      return word
  return None


def dismiss_error_dialog() -> bool:
  """The game sometimes shows an error popup with a Confirm button; click it.

  Detection runs without stealing focus; only when Confirm is seen does the
  game get activated and re-verified (the capture is a screen region, so an
  overlapping window could otherwise cause a false click)."""
  try:
    rect = find_game_window(activate=False).refresh()
    words = ocr_words(capture_window(rect), scale=2)
  except Exception:
    return False

  if _find_confirm_button(words) is None:
    return False

  rect = find_game_window(activate=True).refresh()
  time.sleep(0.2)
  confirm = _find_confirm_button(ocr_words(capture_window(rect), scale=2))
  if confirm is None:
    return False  # was an overlapping window, not the game

  print(f"  Error dialog detected -> clicking Confirm @ ({confirm.cx}, {confirm.cy})")
  click_screen(rect.left + confirm.cx, rect.top + confirm.cy)
  time.sleep(STEP_DELAY)
  return True


def collect_blue_chests(max_rounds: int = 3) -> int:
  """Click unopened BLUE (stage-boss) chest bubbles floating over the game
  strip; wooden/white chests are left to auto-open. Each bubble gets a burst
  of 3 clicks (single clicks sometimes don't register), then a re-capture
  confirms it's gone — up to max_rounds. Returns bubbles collected."""
  rect = find_game_window(activate=True).refresh()
  collected = 0
  for _ in range(max_rounds):
    bubbles = find_chest_bubbles(capture_window(rect), min_y=int(rect.height * 0.55))
    blue = [b for b in bubbles if b.is_blue]
    if not blue:
      break
    chest = blue[0]
    print(f"  Blue chest bubble @ window({chest.cx}, {chest.cy}) "
          f"(blue {chest.blue_fraction:.0%}) -> clicking")
    for _tap in range(3):
      click_screen(rect.left + chest.cx, rect.top + chest.cy)
      time.sleep(0.15)
    collected += 1
    time.sleep(STEP_DELAY)
  return collected


def stash_all(pages: int | None = None) -> None:
  """Click 'Stash All' on every stash page (a single page can be full)."""
  rect = find_game_window(activate=True).refresh()
  full = capture_window(rect)
  try:
    region = find_stash_panel(full)
  except RuntimeError:
    _click_neutral(rect)
    full = capture_window(rect)
    region = find_stash_panel(full)
  crop = region.crop(full)
  words = ocr_words_multi(crop)
  tabs = find_stash_tabs(words, pages or getattr(config, "STASH_PAGES", 5))
  button_x, button_y = find_stash_all_button(words)

  def click(x: int, y: int, label: str) -> None:
    screen_x, screen_y = rect.left + region.x0 + x, rect.top + region.y0 + y
    print(f"    click {label} @ stash({x}, {y}) -> screen({screen_x}, {screen_y})")
    click_screen(screen_x, screen_y)

  # The save (written ~1/min) lets us warn when the stash is genuinely full —
  # a full page silently drops loot. Every page still gets a Stash All click,
  # since an empty page is the best target, not one to skip.
  try:
    import savefile
    filled, unlocked, free = savefile.load().stash_occupancy()
    print(f"  Save: stash {filled}/{unlocked} filled, {free} free")
    if free == 0:
      print("  WARNING: stash is FULL per save — loot may be lost; expand/clear stash")
  except Exception as exc:
    print(f"  Save read failed ({exc}); proceeding")

  print(f"  Stashing on {len(tabs)} pages...")
  for page in sorted(tabs):
    tab_x, tab_y = tabs[page]
    click(tab_x, tab_y, f"stash page {page}")
    time.sleep(STEP_DELAY)
    click(button_x, button_y, "Stash All")
    time.sleep(STEP_DELAY)
