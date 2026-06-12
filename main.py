"""
Blue-chest farm loop — fully self-contained (no tbh-meter dependency):

  - chests.py tracks each stage's 12-min cooldown from OUR OWN drop log
  - navigator.py captures the game window and clicks the route
  - runwatch.py confirms a clear from the encrypted save (gold-earned jump)
  - we stamp the drop ourselves, then stash loot on every page
  - webgui.py serves http://localhost:8765 with timers + farm status

  python test_vision.py    # verify portal detection (no clicks)
  python main.py           # run the farm
  python main.py --warm    # seed cooldowns from tbh-meter history once, then run
"""

from __future__ import annotations

import sys
import time

import chests
import config
import runwatch
from navigator import dismiss_error_dialog, go_to_stage, stash_all
from tracker import ReadyStage
from webgui import set_macro_status, start_in_background

_last_error_check = 0.0


def stage_key(stage: ReadyStage) -> str:
  return f"{stage.act}-{stage.stage}:{stage.difficulty.upper()}"


def maybe_dismiss_error() -> None:
  """Every ERROR_CHECK_SEC, look for the game's error popup and Confirm it."""
  global _last_error_check
  interval = getattr(config, "ERROR_CHECK_SEC", 30)
  if time.time() - _last_error_check < interval:
    return
  _last_error_check = time.time()
  try:
    dismiss_error_dialog()
  except Exception as exc:
    print(f"  Error-dialog check failed: {exc}")


def now_ms() -> int:
  return int(time.time() * 1000)


def main() -> None:
  if "--warm" in sys.argv:
    chests.bootstrap_from_meter()

  start_in_background()
  if getattr(config, "PUBLISH_ENABLED", False):
    import publish
    publish.start_in_background()

  targets = chests.get_targets()
  print(f"Farming {len(targets)} blue-chest stages: " + ", ".join(t.key for t in targets))
  print(f"Self-tracking cooldowns (no tbh-meter). Checking every {config.POLL_INTERVAL}s... (Ctrl+C)")

  while True:
    maybe_dismiss_error()
    ready = chests.get_ready_stages()

    if not ready:
      soonest = min(
        (s for s in chests.get_status() if s["readyAt"]),
        key=lambda s: s["readyAt"],
        default=None,
      )
      detail = f"next: {soonest['key']} in {soonest['secondsLeft']}s" if soonest else ""
      set_macro_status("waiting for cooldowns", detail)
      time.sleep(config.POLL_INTERVAL)
      continue

    target = ready[0]
    handle_key = stage_key(target)

    print(f"READY: {handle_key} (Lv {target.level}) -> navigating...")
    set_macro_status("navigating", "", handle_key)
    try:
      go_to_stage(target)
    except Exception as exc:
      print(f"Navigation failed: {exc}")
      set_macro_status("navigation failed", str(exc), handle_key)
      time.sleep(config.POLL_INTERVAL)
      continue

    # We only navigate to READY stages, so the first clear here drops the chest.
    set_macro_status("running stage", "waiting for clear", handle_key)
    cleared = runwatch.wait_for_clear(target)

    if not cleared:
      print("  No clear confirmed within timeout — leaving cooldown unset, will retry")
      set_macro_status("run timeout", "", handle_key)
      time.sleep(config.POLL_INTERVAL)
      continue

    # Stamp the drop ourselves — this is the authoritative cooldown source.
    chests.record_local_drop(target, now_ms())
    print(f"  Stamped drop for {handle_key}; cooldown {config.CHEST_COOLDOWN_MIN}m starts now")

    set_macro_status("stashing loot", "", handle_key)
    try:
      stash_all()
    except Exception as exc:
      print(f"  Stash failed: {exc}")

    set_macro_status("idle", f"last: {handle_key} cleared")
    time.sleep(config.POLL_INTERVAL)


if __name__ == "__main__":
  main()
