"""
Record click 4 (dungeon node). Prefer: python calibrate_dungeons.py

Full route = 4 clicks: open difficulty -> pick difficulty -> act -> dungeon
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import keyboard

import config
from coords import capture_coords, format_live, using_absolute
from dungeons import normalize_difficulty
from hotkeys import HotkeySession
from windows import find_game_window

DUNGEONS_PATH = Path(__file__).with_name("dungeons.json")


def load_json() -> dict:
  if DUNGEONS_PATH.exists():
    return json.loads(DUNGEONS_PATH.read_text(encoding="utf-8"))
  return {"_comment": "act-stage:DIFFICULTY. node = stage click coords"}


def save_route(key: str, entry: dict) -> None:
  data = load_json()
  data[key] = entry
  DUNGEONS_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
  print(f"\nSaved to {DUNGEONS_PATH.name} -> {key}")


def _validate(store_x: int, store_y: int, rect) -> bool:
  if using_absolute():
    # Negative X/Y is valid on multi-monitor setups (monitor left/above primary).
    return True
  if rect and rect.contains_relative(store_x, store_y):
    return True
  print(f"\n  REJECTED ({store_x}, {store_y}) — outside game client area.")
  if rect:
    print(f"  Window: {rect.title!r} client@({rect.left}, {rect.top}) size {rect.width}x{rect.height}")
  print("  Fix: keep USE_ABSOLUTE_COORDS = True in config.py for 3rd monitor.\n")
  return False


def record_node(key: str, display_name: str) -> None:
  print(f"Recording click 4 (dungeon node) for {key}")
  print("Route: 1 open difficulty -> 2 pick difficulty -> 3 act -> 4 dungeon")
  print("In game: set the right difficulty + act so this stage is visible.")
  print("Hover the stage node, press SPACE. Do NOT click.")

  session = HotkeySession()

  def capture_node() -> None:
    store_x, store_y, screen_x, screen_y = capture_coords()
    rect = None if using_absolute() else find_game_window(activate=False).refresh()
    if not _validate(store_x, store_y, rect):
      return
    save_route(key, {"name": display_name, "node": [store_x, store_y]})
    print(f"  saved ({store_x}, {store_y})  screen=({screen_x}, {screen_y})")
    session.stop()

  def on_tick() -> None:
    store_x, store_y, screen_x, screen_y = capture_coords()
    rect = None if using_absolute() else find_game_window(activate=False).refresh()
    print(format_live(store_x, store_y, screen_x, screen_y, rect), end="\r")

  keyboard.add_hotkey("space", capture_node, suppress=True)
  keyboard.add_hotkey("q", session.stop, suppress=True)
  session.run(on_tick=on_tick)
  print("\nDone.")


def record_full(key: str, display_name: str) -> None:
  clicks: list[dict] = []
  print(f"Recording all 4 clicks for {key}")
  print("Order: open difficulty -> pick difficulty -> act -> dungeon")
  print("SPACE=add | U=undo | S=save | Q=quit\n")

  session = HotkeySession()

  def add_click() -> None:
    store_x, store_y, _, _ = capture_coords()
    rect = None if using_absolute() else find_game_window(activate=False).refresh()
    if not _validate(store_x, store_y, rect):
      return
    clicks.append({"x": store_x, "y": store_y, "delay": 0.25, "label": f"step {len(clicks) + 1}"})
    print(f"  + ({store_x}, {store_y})")

  def undo() -> None:
    if clicks:
      removed = clicks.pop()
      print(f"  - removed ({removed['x']}, {removed['y']})")

  def save() -> None:
    if not clicks:
      print("Nothing to save.")
      return
    if len(clicks) != 4:
      print(f"Need exactly 4 clicks (got {len(clicks)}).")
      print("Order: open difficulty, pick difficulty, act, dungeon.")
      return
    labels = [
      "1 open difficulty",
      "2 pick difficulty",
      "3 act",
      "4 dungeon",
    ]
    for i, step in enumerate(clicks):
      step["label"] = labels[i]
    save_route(key, {"name": display_name, "clicks": clicks})
    print(f"  {len(clicks)} clicks")
    session.stop()

  keyboard.add_hotkey("space", add_click, suppress=True)
  keyboard.add_hotkey("u", undo, suppress=True)
  keyboard.add_hotkey("s", save, suppress=True)
  keyboard.add_hotkey("q", session.stop, suppress=True)
  session.run()
  print("Done.")


def main() -> None:
  parser = argparse.ArgumentParser(description="Record dungeon route")
  parser.add_argument("act", type=int)
  parser.add_argument("stage", type=int)
  parser.add_argument("difficulty", choices=["HELL", "NIGHTMARE", "NORMAL", "hell", "nightmare", "normal"])
  parser.add_argument("--name", default="")
  parser.add_argument("--full", action="store_true")
  args = parser.parse_args()

  diff = normalize_difficulty(args.difficulty)
  key = f"{args.act}-{args.stage}:{diff}"
  display_name = args.name or f"Act {args.act}-{args.stage} {config.DIFFICULTY_LABELS[diff]}"

  try:
    if args.full:
      record_full(key, display_name)
    else:
      record_node(key, display_name)
  except KeyboardInterrupt:
    keyboard.unhook_all()
    print("\nCancelled.")


if __name__ == "__main__":
  main()
