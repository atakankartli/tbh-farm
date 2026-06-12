"""
Record click 4 (dungeon node) for one or all routes.

Each dungeon: set difficulty + act in game so the stage is visible,
hover the node, press SPACE (do not click).

Usage:
  python calibrate_dungeons.py              # record all default dungeons
  python calibrate_dungeons.py 2 5 HELL     # record one
  python calibrate_dungeons.py --list         # show routes + coords
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

DUNGEONS_PATH = Path(__file__).with_name("dungeons.json")

# Dungeons from your tracker — edit this list as needed
DEFAULT_DUNGEONS: list[tuple[int, int, str]] = [
  (2, 5, "HELL"),
  (3, 5, "NIGHTMARE"),
  (1, 9, "NIGHTMARE"),
  (3, 8, "NORMAL"),
]


def load_json() -> dict:
  if DUNGEONS_PATH.exists():
    return json.loads(DUNGEONS_PATH.read_text(encoding="utf-8"))
  return {"_comment": "click 4 (dungeon node) per route"}


def save_node(key: str, name: str, node: tuple[int, int]) -> None:
  data = load_json()
  data[key] = {"name": name, "node": [node[0], node[1]]}
  DUNGEONS_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
  print(f"  saved {key} -> ({node[0]}, {node[1]})")


def route_key(act: int, stage: int, difficulty: str) -> str:
  diff = normalize_difficulty(difficulty)
  return f"{act}-{stage}:{diff}"


def route_name(act: int, stage: int, difficulty: str) -> str:
  diff = normalize_difficulty(difficulty)
  return f"Act {act}-{stage} {config.DIFFICULTY_LABELS[diff]}"


def list_routes() -> None:
  data = load_json()
  print("Dungeon nodes (click 4):\n")
  keys = [k for k in data if not k.startswith("_")]
  if not keys:
    print("  (none recorded yet)")
    return
  for key in sorted(keys):
    entry = data[key]
    node = entry.get("node", ["?", "?"])
    print(f"  {key}: {entry.get('name', key)}  node={node}")


def record_one(act: int, stage: int, difficulty: str, *, index: str = "") -> None:
  key = route_key(act, stage, difficulty)
  name = route_name(act, stage, difficulty)
  diff = normalize_difficulty(difficulty)

  prefix = f"{index} " if index else ""
  print(f"\n>>> {prefix}{key} — {name}")
  print(f"    In game: set {config.DIFFICULTY_LABELS[diff]} + Act {act} (portal open).")
  print(f"    Hover stage node [{act}-{stage}], press SPACE. Do NOT click.")
  print("    Q = skip this dungeon | Ctrl+C = quit all\n")

  session = HotkeySession()
  saved = {"done": False}

  def capture() -> None:
    store_x, store_y, screen_x, screen_y = capture_coords()
    save_node(key, name, (store_x, store_y))
    print(f"    screen=({screen_x}, {screen_y})")
    saved["done"] = True
    session.stop()

  def on_tick() -> None:
    store_x, store_y, screen_x, screen_y = capture_coords()
    print(format_live(store_x, store_y, screen_x, screen_y, None), end="\r")

  keyboard.add_hotkey("space", capture, suppress=True)
  keyboard.add_hotkey("q", session.stop, suppress=True)
  session.run(on_tick=on_tick)

  if not saved["done"]:
    print(f"  skipped {key}")


def record_all(dungeons: list[tuple[int, int, str]]) -> None:
  total = len(dungeons)
  print(f"Recording {total} dungeon nodes (click 4 of each route).")
  print("Steps 1-3 (difficulty + act) are already in config.py.\n")
  if using_absolute():
    print("Negative X is OK on left-side monitors.\n")

  for i, (act, stage, diff) in enumerate(dungeons, start=1):
    record_one(act, stage, diff, index=f"{i}/{total}")

  print("\nAll done. Check with: python list_routes.py")


def main() -> None:
  parser = argparse.ArgumentParser(description="Record dungeon node positions")
  parser.add_argument("act", type=int, nargs="?", help="Act number e.g. 2")
  parser.add_argument("stage", type=int, nargs="?", help="Stage number e.g. 5")
  parser.add_argument(
    "difficulty",
    nargs="?",
    choices=["HELL", "NIGHTMARE", "NORMAL", "hell", "nightmare", "normal"],
  )
  parser.add_argument("--list", action="store_true", help="Show saved dungeon nodes")
  args = parser.parse_args()

  if args.list:
    list_routes()
    return

  if args.act is not None and args.stage is not None and args.difficulty is not None:
    try:
      record_one(args.act, args.stage, args.difficulty)
    except KeyboardInterrupt:
      keyboard.unhook_all()
      print("\nCancelled.")
    return

  try:
    record_all(DEFAULT_DUNGEONS)
  except KeyboardInterrupt:
    keyboard.unhook_all()
    print("\nCancelled.")


if __name__ == "__main__":
  main()
