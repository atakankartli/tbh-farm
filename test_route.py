"""Run one dungeon click combo without waiting for the tracker (for testing)."""

from __future__ import annotations

import argparse

from dungeons import load_routes
from navigator import go_to_stage
from tracker import ReadyStage


def main() -> None:
  parser = argparse.ArgumentParser(description="Test a dungeon route by key")
  parser.add_argument("key", help='Route key e.g. "2-5:HELL"')
  args = parser.parse_args()

  routes = load_routes()
  key = args.key.upper()
  if key not in routes:
    raise SystemExit(f"Unknown route '{key}'. Known: {', '.join(sorted(routes))}")

  act_s, diff = key.split(":", 1)
  act_s, stage_s = act_s.split("-", 1)
  target = ReadyStage(
    label=f"{act_s}-{stage_s}",
    act=int(act_s),
    stage=int(stage_s),
    difficulty=diff,
  )

  print(f"Testing {key} in 3 seconds — focus game window...")
  import time

  time.sleep(3)
  go_to_stage(target)
  print("Done.")


if __name__ == "__main__":
  main()
