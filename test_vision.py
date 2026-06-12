"""
Dry-run the portal vision (no clicks): show detected difficulty, act tabs,
and dungeon nodes, and save an annotated _vision_debug.png to verify.

  python test_vision.py                              # capture live PORTAL window
  python test_vision.py --image reference.image.png  # offline, full screenshot
  python test_vision.py --act 2                      # expected act for node labels
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

import vision
from windows import find_game_window

DEBUG_PATH = Path(__file__).with_name("_vision_debug.png")


def _imread(path: str) -> np.ndarray | None:
  """cv2.imread fails on non-ASCII paths (e.g. Masaüstü) — decode from bytes."""
  try:
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
  except OSError:
    return None


def _imwrite(path: Path, image: np.ndarray) -> None:
  ok, buf = cv2.imencode(".png", image)
  if not ok:
    raise RuntimeError("PNG encode failed")
  path.write_bytes(buf.tobytes())


def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument("--image", help="run on a saved screenshot instead of the live window")
  parser.add_argument("--act", type=int, default=0, help="act shown on the map (default: selected tab)")
  args = parser.parse_args()

  if args.image:
    full = _imread(args.image)
    if full is None:
      raise SystemExit(f"Could not read {args.image}")
    print(f"Loaded {args.image} ({full.shape[1]}x{full.shape[0]})")
  else:
    rect = find_game_window(activate=False)
    full = vision.capture_window(rect)
    print(f"Captured game window {rect.width}x{rect.height} @ ({rect.left}, {rect.top})")

  orb = vision.find_portal_orb(full)
  print(f"Portal button (blue sphere): {'at (%d,%d)' % orb if orb else 'not found'}")

  try:
    region = vision.find_portal_panel(full)
    print(f"PORTAL panel at ({region.x0},{region.y0})-({region.x1},{region.y1})")
    image = region.crop(full)
  except RuntimeError as exc:
    print(f"PORTAL panel: FAILED — {exc} (running detection on the full capture)")
    image = full

  annotated = image.copy()
  words = vision.ocr_words_multi(image)

  try:
    difficulty, word = vision.read_current_difficulty(words)
    print(f"Difficulty: {difficulty} (dropdown text at {word.cx},{word.cy})")
    cv2.rectangle(annotated, (word.x, word.y), (word.x + word.w, word.y + word.h), (0, 0, 255), 2)
  except RuntimeError as exc:
    print(f"Difficulty: FAILED — {exc}")

  act_for_nodes = args.act
  map_top = 0
  try:
    tabs = vision.find_act_tabs(words, panel_width=image.shape[1])
    map_top = max(t.y + t.h for t in tabs.values()) + 5
    for act, tab in sorted(tabs.items()):
      print(f"Act {act} tab at ({tab.cx},{tab.cy})")
      cv2.rectangle(annotated, (tab.x, tab.y), (tab.x + tab.w, tab.y + tab.h), (255, 0, 0), 2)
    if not act_for_nodes:
      act_for_nodes = max(tabs)  # without --act, assume the highest act is selected
  except RuntimeError as exc:
    print(f"Act tabs: FAILED — {exc}")

  if act_for_nodes:
    try:
      nodes = vision.find_dungeon_nodes(image, act_for_nodes, map_top=map_top)
      for node in nodes:
        print(f"Stage {act_for_nodes}-{node.stage} circle at ({node.cx},{node.cy})  ocr={node.label_text!r}")
        cv2.circle(annotated, (node.cx, node.cy), 12, (0, 255, 0), 2)
        cv2.putText(
          annotated, f"{act_for_nodes}-{node.stage}", (node.cx - 10, node.cy - 14),
          cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1,
        )
    except RuntimeError as exc:
      print(f"Dungeon nodes: FAILED — {exc}")

  _imwrite(DEBUG_PATH, annotated)
  print(f"\nAnnotated capture saved to {DEBUG_PATH.name}")


if __name__ == "__main__":
  main()
