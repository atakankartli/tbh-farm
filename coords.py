"""Convert between stored coords and screen clicks."""

from __future__ import annotations

import config
from win32_coords import click_screen, get_cursor_pos
from windows import WindowRect, find_game_window


def using_absolute() -> bool:
  return bool(getattr(config, "USE_ABSOLUTE_COORDS", False))


def capture_coords() -> tuple[int, int, int, int]:
  """
  Returns (store_x, store_y, screen_x, screen_y).
  Absolute mode: raw virtual-screen coords (can be negative if monitor is left of primary).
  Relative mode: offset from game client area top-left.
  """
  screen_x, screen_y = get_cursor_pos()
  if using_absolute():
    return screen_x, screen_y, screen_x, screen_y

  rect = find_game_window(activate=False).refresh()
  rel_x = screen_x - rect.left
  rel_y = screen_y - rect.top
  return rel_x, rel_y, screen_x, screen_y


def to_screen(x: int, y: int, game: WindowRect | None = None) -> tuple[int, int]:
  if using_absolute():
    return x, y
  if game is None:
    game = find_game_window(activate=False)
  game = game.refresh()
  return game.left + x, game.top + y


def click_at(x: int, y: int, game: WindowRect | None = None) -> None:
  screen_x, screen_y = to_screen(x, y, game)
  click_screen(screen_x, screen_y)


def format_live(store_x: int, store_y: int, screen_x: int, screen_y: int, rect: WindowRect | None) -> str:
  if using_absolute():
    return f"  ABS screen=({screen_x}, {screen_y})  <- save these   "
  inside = rect.contains_relative(store_x, store_y) if rect else False
  tag = "OK" if inside else "OUT (set USE_ABSOLUTE_COORDS=True?)"
  return f"  REL store=({store_x:5d}, {store_y:5d})  screen=({screen_x}, {screen_y}) [{tag}]   "
