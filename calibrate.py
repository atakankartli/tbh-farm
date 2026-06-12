"""Live mouse coords — use this on monitor 3 to verify before recording."""

from __future__ import annotations

import time

import config
from coords import capture_coords, format_live, using_absolute
from windows import find_game_window


def main() -> None:
  if using_absolute():
    print("Mode: ABSOLUTE screen coords (USE_ABSOLUTE_COORDS = True)")
    print("Negative X is normal when a monitor sits LEFT of your main display.")
    print("Example (-700, 1200) is valid — press SPACE in record_combo to save as-is.\n")
  else:
    print("Mode: RELATIVE to game window")
    print("If you see negative coords, set USE_ABSOLUTE_COORDS = True in config.py\n")
    game = find_game_window(activate=False)
    print(f"Game: {game.title!r} client@({game.left}, {game.top}) {game.width}x{game.height}\n")

  print("Ctrl+C to stop.\n")

  try:
    while True:
      store_x, store_y, screen_x, screen_y = capture_coords()
      rect = None if using_absolute() else find_game_window(activate=False).refresh()
      print(format_live(store_x, store_y, screen_x, screen_y, rect), end="\r")
      time.sleep(0.1)
  except KeyboardInterrupt:
    print("\nDone.")


if __name__ == "__main__":
  main()
