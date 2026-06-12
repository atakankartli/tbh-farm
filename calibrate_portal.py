"""
Calibrate shared portal clicks in config.py.

Each dungeon route = 4 clicks:
  1. open difficulty dropdown
  2. pick difficulty (Hell / Nightmare / Normal)
  3. act tab (1 click — hover to calibrate)
  4. dungeon node (record_combo.py)

Usage:
  python calibrate_portal.py difficulty
  python calibrate_portal.py act
"""

from __future__ import annotations

import argparse
from pathlib import Path

import keyboard

import config
from coords import capture_coords, using_absolute
from hotkeys import HotkeySession
from windows import find_game_window

CONFIG_PATH = Path(__file__).with_name("config.py")


def _portal_block(dropdown: tuple[int, int], difficulty_options: dict, act_tabs: dict) -> str:
  delay = config.PORTAL_UI.get("step_delay", 0.25)
  open_delay = config.PORTAL_UI.get("dropdown_open_delay", 0.4)
  return (
    'PORTAL_UI = {\n'
    f'    "difficulty_dropdown": {dropdown},\n'
    '    "difficulty_options": {\n'
    f'        "HELL": {difficulty_options["HELL"]},\n'
    f'        "NIGHTMARE": {difficulty_options["NIGHTMARE"]},\n'
    f'        "NORMAL": {difficulty_options["NORMAL"]},\n'
    '    },\n'
    '    "act_tabs": {\n'
    f'        1: {act_tabs[1]},\n'
    f'        2: {act_tabs[2]},\n'
    f'        3: {act_tabs[3]},\n'
    '    },\n'
    f'    "step_delay": {delay},\n'
    f'    "dropdown_open_delay": {open_delay},\n'
    '}'
  )


def _update_config(replacement: str) -> None:
  text = CONFIG_PATH.read_text(encoding="utf-8")
  marker = "PORTAL_UI = {"
  start = text.index(marker)
  depth = 0
  end = start
  for i, ch in enumerate(text[start:], start):
    if ch == "{":
      depth += 1
    elif ch == "}":
      depth -= 1
      if depth == 0:
        end = i + 1
        break
  else:
    raise RuntimeError("Could not find end of PORTAL_UI block in config.py")
  CONFIG_PATH.write_text(text[:start] + replacement + text[end:], encoding="utf-8")


def _capture_point(session: HotkeySession, points: list[tuple[int, int]], label: str) -> None:
  store_x, store_y, _, _ = capture_coords()
  if not using_absolute():
    rect = find_game_window(activate=False).refresh()
    if not rect.contains_relative(store_x, store_y):
      print(f"\n  REJECTED {label}: ({store_x}, {store_y}) outside game")
      return
  points.append((store_x, store_y))
  print(f"  saved {label}: ({store_x}, {store_y})")


def calibrate_difficulty() -> None:
  points: list[tuple[int, int]] = []
  steps = [
    ("1/4 — difficulty dropdown BUTTON (closed)", "Just hover the dropdown button. Do not open it."),
    ("2/4 — Hell option", "OPEN dropdown first, hover Hell, press SPACE. Do NOT click Hell."),
    ("3/4 — Nightmare option", "OPEN dropdown again, hover Nightmare, press SPACE. Do NOT click."),
    ("4/4 — Normal option", "OPEN dropdown again, hover Normal, press SPACE. Do NOT click."),
  ]

  print("Calibrating difficulty (dropdown closes when you pick an option).\n")
  print("For steps 2-4: open dropdown, HOVER the option, press SPACE to save coords only.\n")

  session = HotkeySession()
  step = {"i": 0}

  def show_prompt() -> None:
    title, hint = steps[step["i"]]
    print(f"\n>>> {title}")
    print(f"    {hint}")

  show_prompt()

  def capture() -> None:
    if step["i"] >= len(steps):
      return
    before = len(points)
    _capture_point(session, points, steps[step["i"]][0])
    if len(points) <= before:
      return
    step["i"] += 1
    if len(points) == 4:
      ui = config.PORTAL_UI
      _update_config(
        _portal_block(
          points[0],
          {"HELL": points[1], "NIGHTMARE": points[2], "NORMAL": points[3]},
          ui["act_tabs"],
        )
      )
      print("\nSaved difficulty dropdown + options to config.py")
      session.stop()
      return
    show_prompt()

  keyboard.add_hotkey("space", capture, suppress=True)
  keyboard.add_hotkey("q", session.stop, suppress=True)
  session.run()
  print("Done.")


def calibrate_acts() -> None:
  points: list[tuple[int, int]] = []
  steps = [
    ("1/3 — Act 1 tab", "Hover Act 1 tab, press SPACE. Do NOT click."),
    ("2/3 — Act 2 tab", "Hover Act 2 tab, press SPACE. Do NOT click."),
    ("3/3 — Act 3 tab", "Hover Act 3 tab, press SPACE. Do NOT click."),
  ]

  print("Calibrating act tabs (1 click per route — no dropdown).\n")
  print("Hover each tab and press SPACE to save coords only.\n")

  session = HotkeySession()
  step = {"i": 0}

  def show_prompt() -> None:
    title, hint = steps[step["i"]]
    print(f"\n>>> {title}")
    print(f"    {hint}")

  show_prompt()

  def capture() -> None:
    if step["i"] >= len(steps):
      return
    before = len(points)
    _capture_point(session, points, steps[step["i"]][0])
    if len(points) <= before:
      return
    step["i"] += 1
    if len(points) == 3:
      ui = config.PORTAL_UI
      dropdown = ui.get("difficulty_dropdown", (0, 0))
      _update_config(
        _portal_block(
          tuple(dropdown),
          ui["difficulty_options"],
          {1: points[0], 2: points[1], 3: points[2]},
        )
      )
      print("\nSaved act tab clicks to config.py")
      session.stop()
      return
    show_prompt()

  keyboard.add_hotkey("space", capture, suppress=True)
  keyboard.add_hotkey("q", session.stop, suppress=True)
  session.run()
  print("Done.")


def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument("target", choices=["difficulty", "act"])
  args = parser.parse_args()

  print("Route: open difficulty -> pick difficulty -> act -> dungeon (4 clicks)\n")
  if using_absolute():
    print("Absolute coords — negative X is OK on left-side monitors.\n")

  print("Open PORTAL in game.\n")
  try:
    if args.target == "difficulty":
      calibrate_difficulty()
    else:
      calibrate_acts()
  except KeyboardInterrupt:
    keyboard.unhook_all()
    print("\nCancelled.")


if __name__ == "__main__":
  main()
