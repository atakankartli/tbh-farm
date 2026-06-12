"""Print all configured dungeon click combos."""

import config
from dungeons import load_routes


def main() -> None:
  mode = "absolute screen" if config.USE_ABSOLUTE_COORDS else "window-relative"
  print(f"Coord mode: {mode}\n")

  print("Portal clicks — steps 1-3 from config.py:")
  ui = config.PORTAL_UI
  print(f"  1. open difficulty: {ui.get('difficulty_dropdown')}")
  for diff, point in ui["difficulty_options"].items():
    print(f"  2. {diff}: {point} ({config.DIFFICULTY_LABELS[diff]})")
  print(f"  3. act tabs: {ui['act_tabs']}")
  print("  4. dungeon node: per entry in dungeons.json\n")

  routes = load_routes()
  if not routes:
    print("\nNo routes in dungeons.json")
    return

  print(f"\n{len(routes)} dungeon routes:")
  for key, route in sorted(routes.items()):
    print(f"\n{key} — {route.name} [{route.difficulty}]")
    for i, step in enumerate(route.clicks, start=1):
      label = f" ({step.label})" if step.label else ""
      print(f"  {i}. ({step.x}, {step.y}) delay={step.delay}s{label}")


if __name__ == "__main__":
  main()
