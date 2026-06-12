"""Print matched windows — use to set TRACKER_WINDOW_TITLE in config.py."""

import config
from windows import find_tracker_window, list_windows


def main() -> None:
  print(f"TRACKER_WINDOW_TITLE = {config.TRACKER_WINDOW_TITLE!r}")
  print(f"Exclude game panels: {config.TRACKER_EXCLUDE_TITLES}\n")

  all_tbh = list_windows(config.TRACKER_WINDOW_TITLE)
  print(f"All windows matching {config.TRACKER_WINDOW_TITLE!r}:")
  for i, w in enumerate(all_tbh):
    print(f"  [{i}] {w.title!r}  {w.width}x{w.height}  @({w.left}, {w.top})")

  print()
  try:
    picked = find_tracker_window()
    print(f"Auto-picked tracker: {picked.title!r}  {picked.width}x{picked.height}  @({picked.left}, {picked.top})")
  except RuntimeError as exc:
    print(f"Auto-pick failed: {exc}")


if __name__ == "__main__":
  main()
