from __future__ import annotations

import time
from dataclasses import dataclass

import pygetwindow as gw

import config
from win32_coords import activate_hwnd, get_client_rect_screen


@dataclass(frozen=True)
class WindowRect:
  left: int
  top: int
  width: int
  height: int
  title: str = ""
  hwnd: int = 0

  @property
  def right(self) -> int:
    return self.left + self.width

  @property
  def bottom(self) -> int:
    return self.top + self.height

  def contains_relative(self, x: int, y: int) -> bool:
    return 0 <= x <= self.width and 0 <= y <= self.height

  def refresh(self) -> WindowRect:
    if not self.hwnd:
      return self
    left, top, width, height = get_client_rect_screen(self.hwnd)
    return WindowRect(left, top, width, height, self.title, self.hwnd)


def _is_excluded(title: str, exclude: str | None, exclude_all: tuple[str, ...]) -> bool:
  lower = title.lower()
  if exclude and exclude.lower() in lower:
    return True
  return any(token in lower for token in exclude_all)


def _rect_from_window(win) -> WindowRect | None:
  title = (win.title or "").strip()
  hwnd = int(getattr(win, "_hWnd", 0) or 0)
  if hwnd:
    try:
      left, top, width, height = get_client_rect_screen(hwnd)
      if width > 0 and height > 0:
        return WindowRect(left, top, width, height, title, hwnd)
    except OSError:
      pass
  if win.width <= 0 or win.height <= 0:
    return None
  return WindowRect(win.left, win.top, win.width, win.height, title, hwnd)


def list_windows(
  title_substring: str,
  *,
  exclude: str | None = None,
  exclude_titles: tuple[str, ...] = ("cursor", "python", "powershell", "cmd"),
) -> list[WindowRect]:
  needle = title_substring.lower()
  matches: list[WindowRect] = []
  for win in gw.getAllWindows():
    title = (win.title or "").strip()
    if not title:
      continue
    if needle not in title.lower():
      continue
    if _is_excluded(title, exclude, exclude_titles):
      continue
    rect = _rect_from_window(win)
    if rect:
      matches.append(rect)
  matches.sort(key=lambda w: -(w.width * w.height))
  return matches


def find_window(
  title_substring: str,
  *,
  exclude: str | None = None,
  activate: bool = True,
) -> WindowRect:
  matches = list_windows(title_substring, exclude=exclude)
  if not matches:
    raise RuntimeError(
      f"No window found matching '{title_substring}'. "
      "Check GAME_WINDOW_TITLE in config.py."
    )

  if len(matches) > 1 and activate:
    print("Multiple windows matched (using largest):")
    for i, rect in enumerate(matches):
      mark = " <- using" if i == 0 else ""
      print(
        f"  [{i}] {rect.title!r}  {rect.width}x{rect.height}  "
        f"client@({rect.left}, {rect.top}){mark}"
      )

  rect = matches[0].refresh()
  if activate and rect.hwnd:
    if not activate_hwnd(rect.hwnd):
      print(f"  WARNING: could not bring {rect.title!r} to foreground — captures may show overlapping windows")
    time.sleep(0.15)
    rect = rect.refresh()
  return rect


def find_game_window(*, activate: bool = False) -> WindowRect:
  return find_window(config.GAME_WINDOW_TITLE, activate=activate)


def _is_game_panel(title: str) -> bool:
  upper = title.upper()
  return any(token in upper for token in config.TRACKER_EXCLUDE_TITLES)


def find_tracker_window(*, activate: bool = False) -> WindowRect:
  """Find the TBH tracker overlay (narrow sidebar), not game PORTAL/HERO/STASH windows."""
  needle = config.TRACKER_WINDOW_TITLE
  matches = list_windows(needle)
  if not matches:
    raise RuntimeError(
      f"No window matching '{needle}'. "
      "Set TRACKER_WINDOW_TITLE in config.py (try 'TBH')."
    )

  tracker_candidates = [w for w in matches if not _is_game_panel(w.title)]
  if not tracker_candidates:
    tracker_candidates = matches

  # Tracker sidebar is the narrowest matching window
  tracker_candidates.sort(key=lambda w: (w.width, w.height))
  rect = tracker_candidates[0].refresh()

  if activate and rect.hwnd:
    activate_hwnd(rect.hwnd)
    time.sleep(0.1)
    rect = rect.refresh()
  return rect


def mouse_relative_to_window(
  title_substring: str,
  *,
  exclude: str | None = None,
) -> tuple[int, int, WindowRect]:
  import pyautogui

  rect = find_window(title_substring, exclude=exclude, activate=False).refresh()
  x, y = pyautogui.position()
  return x - rect.left, y - rect.top, rect
