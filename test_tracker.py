"""
Test reading the tracker window (OCR).

Usage:
  python test_tracker.py          # one-shot read
  python test_tracker.py --watch  # poll every 5s
  python test_tracker.py --save   # save tracker screenshot
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2

import config
from dungeons import load_routes, stage_key
from tracker import capture_tracker, debug_tracker


def main() -> None:
  parser = argparse.ArgumentParser(description="Test tracker OCR")
  parser.add_argument("--watch", action="store_true", help="Keep polling")
  parser.add_argument("--save", action="store_true", help="Save tracker screenshot")
  args = parser.parse_args()

  routes = load_routes()
  print(f"Known routes: {', '.join(sorted(routes))}")
  print(f"Priority: highest Lv first (PRIORITIZE_BY_LEVEL={config.PRIORITIZE_BY_LEVEL})\n")

  def run_once() -> None:
    try:
      lines, ready, rect = debug_tracker()
      print(f"Tracker: {rect.title!r}  at ({rect.left}, {rect.top})  {rect.width}x{rect.height}")

      if args.save:
        frame = capture_tracker(rect)
        out = Path(__file__).with_name("tracker_debug.png")
        cv2.imwrite(str(out), frame)
        print(f"Saved screenshot: {out}")

      print("\nOCR lines:")
      for line in lines:
        print(f"  | {line}")

      print("\nREADY stages (sorted by priority):")
      if not ready:
        print("  (none)")
      for i, stage in enumerate(ready, start=1):
        key = stage_key(stage)
        has_route = key in routes
        tag = "OK" if has_route else "NO ROUTE"
        pick = " <- will go here" if i == 1 and has_route else ""
        lv = f"Lv {stage.level}" if stage.level else "Lv ?"
        print(f"  {i}. {key}  {lv}  [{tag}]{pick}")

    except Exception as exc:
      print(f"Error: {exc}")

  if args.watch:
    print(f"Watching every {config.POLL_INTERVAL}s... Ctrl+C to stop\n")
    try:
      while True:
        print("---")
        run_once()
        print()
        time.sleep(config.POLL_INTERVAL)
    except KeyboardInterrupt:
      print("Stopped.")
  else:
    run_once()


if __name__ == "__main__":
  main()
