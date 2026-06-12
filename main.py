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
import droplog
import runwatch
from navigator import (
  StageLockedError,
  collect_blue_chests,
  dismiss_error_dialog,
  go_to_stage,
  stash_all,
)
from tracker import ReadyStage
from webgui import command_pending, get_settings, pop_command, set_macro_status, start_in_background

_last_error_check = 0.0

# Stages that cleared WITHOUT the game logging a blue drop (our cooldown was
# off) wait this long before another attempt, so we don't burn runs in a loop.
NO_DROP_BACKOFF_SEC = 180
_no_drop_backoff: dict[str, float] = {}

# Where WE last sent the game (auto or manual navigation). The save's
# currentStage lags 1-2 min behind, so this is the fresh source of truth for
# "are we already on this stage" — and the manually chosen stage is farmed
# first when it's ready, instead of being yanked away.
_parked_on: str | None = None


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
  global _parked_on
  if "--warm" in sys.argv:
    chests.bootstrap_from_meter()

  start_in_background()
  if getattr(config, "PUBLISH_ENABLED", False):
    import publish
    publish.start_in_background()

  targets = chests.get_targets()
  print(f"Farming {len(targets)} blue-chest stages: " + ", ".join(t.key for t in targets))

  # Show restored cooldowns so it's clear restarting didn't reset timings
  print("Restored drop timings from disk:")
  for s in chests.get_status():
    when = "READY now" if s["ready"] else f"ready in {s['secondsLeft'] // 60}m{s['secondsLeft'] % 60:02d}s"
    last = "never" if not s["lastDropAt"] else f"{int((time.time() * 1000 - s['lastDropAt']) / 60000)}m ago"
    print(f"  {s['key']:16} last drop {last:>12}  ->  {when}")
  print(f"Self-tracking cooldowns (no tbh-meter). Checking every {config.POLL_INTERVAL}s... (Ctrl+C)")
  if not get_settings().get("macroEnabled", False):
    print("MACRO IS OFF (default) — it won't touch the mouse until you click the "
          "'macro' pill on the dashboard to turn it on.")

  # One ledger for the whole session: drops logged at ANY moment (navigating,
  # between cycles, waiting on another stage) stay pending until consumed.
  watcher = droplog.DropTracker() if droplog.log_path().exists() else None
  if watcher is None:
    print(f"  WARNING: {droplog.log_path()} not found — drops can't be verified, "
          "falling back to clear-based stamping")

  while True:
    # Manual navigation from the GUI — an explicit user action, so it runs
    # even while the macro is paused, and aborts any in-progress wait.
    cmd = pop_command()
    if cmd and cmd.get("goto"):
      spec = cmd["goto"]
      print(f"Manual navigation requested: {spec}")
      set_macro_status("navigating (manual)", "", spec)
      try:
        go_to_stage(chests.validate_stage(spec))
        _parked_on = spec
        set_macro_status("idle", f"manually moved to {spec} — the game farms it now")
        print(f"  Now parked on {spec}")
      except Exception as exc:
        print(f"  Manual navigation failed: {exc}")
        set_macro_status("manual navigation failed", str(exc), spec)
      continue

    if not get_settings().get("macroEnabled", False):
      # Master switch off: no navigation, no error-dialog clicks — the mouse
      # is entirely the user's until they flip it back on in the GUI.
      set_macro_status("paused", "macro switched off in web GUI")
      time.sleep(config.POLL_INTERVAL)
      continue

    maybe_dismiss_error()
    now = time.time()
    ready = [s for s in chests.get_ready_stages()
             if now - _no_drop_backoff.get(stage_key(s), 0) >= NO_DROP_BACKOFF_SEC]

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

    # The stage we (or the user, via Go) parked the game on runs first when
    # ready — don't yank the game away from a deliberate manual choice.
    target = next((s for s in ready if stage_key(s) == _parked_on), ready[0])
    handle_key = stage_key(target)

    # If the game is already parked on this stage, clicking its node would
    # RESTART the run and lose the progress — skip navigation and just wait.
    # Our own navigation memory is fresher than the save (1-2 min flush lag).
    if _parked_on is not None:
      already_on = _parked_on == handle_key
    else:
      already_on = False
      try:
        import savefile
        already_on = savefile.load().current_stage_key == chests.numeric_stage_key(target)
      except Exception:
        pass

    if already_on:
      print(f"READY: {handle_key} (Lv {target.level}) -> already farming it; "
            "skipping navigation so the current run isn't reset")
    else:
      print(f"READY: {handle_key} (Lv {target.level}) -> navigating...")
      set_macro_status("navigating", "", handle_key)
    try:
      if not already_on:
        go_to_stage(target)
        _parked_on = handle_key
    except StageLockedError as exc:
      # Retrying every poll would click forever at a chained map; drop the
      # target and keep farming the rest. Re-add it from the GUI once the
      # act is unlocked in-game.
      chests.remove_target(handle_key)
      print(f"Stage locked: {exc} — removed {handle_key} from targets; "
            f"re-add it from the web GUI after unlocking the act in-game")
      set_macro_status("stage locked", f"{handle_key} removed from targets (act locked in-game)")
      continue
    except Exception as exc:
      print(f"Navigation failed: {exc}")
      set_macro_status("navigation failed", str(exc), handle_key)
      time.sleep(2)  # brief pause so a persistent vision failure can't hot-loop
      continue

    # We only navigate to READY stages, so the first clear here drops the chest.
    set_macro_status("running stage",
                     "already on stage; waiting for clear" if already_on else "waiting for clear",
                     handle_key)
    result = runwatch.wait_for_clear(target, learn=not already_on, watcher=watcher,
                                     abort=command_pending)

    if result == "aborted":
      continue  # loop top executes the pending manual command

    if result is None:
      if watcher is not None:
        # Runs kept chaining but the game never logged the drop — our timer
        # is way off for this stage. Back off so other stages get farmed.
        _no_drop_backoff[handle_key] = time.time()
        print(f"  No blue drop within the timeout — not stamping; "
              f"retrying {handle_key} in {NO_DROP_BACKOFF_SEC // 60}m")
        set_macro_status("no drop (timeout)", f"{handle_key} retry in {NO_DROP_BACKOFF_SEC // 60}m")
      else:
        print("  No clear confirmed within timeout — leaving cooldown unset, will retry")
        set_macro_status("run timeout", "", handle_key)
      continue  # backoff guards the failed stage; pick the next one now

    # "dropped" (game-verified), or "cleared" in legacy no-log mode. Stamp
    # with the moment the drop was actually seen, not the consume time.
    _no_drop_backoff.pop(handle_key, None)
    drop_at = (watcher.last_taken_ms if watcher and result == "dropped" else None) or now_ms()
    chests.record_local_drop(target, drop_at)
    verified = "VERIFIED " if result == "dropped" else ""
    print(f"  Stamped {verified}drop for {handle_key}; cooldown {config.CHEST_COOLDOWN_MIN}m starts now")

    # Open the blue chest if its bubble is on screen (white ones auto-open).
    try:
      if collect_blue_chests():
        set_macro_status("collecting blue chest", "", handle_key)
    except Exception as exc:
      print(f"  Blue-chest check failed: {exc}")

    if get_settings().get("stashEnabled", False):
      set_macro_status("stashing loot", "", handle_key)
      try:
        stash_all()
      except Exception as exc:
        print(f"  Stash failed: {exc}")
    else:
      print("  Stash skipped (turned off in web GUI)")

    set_macro_status("idle", f"last: {handle_key} cleared")
    # no sleep: the loop top re-checks cooldowns immediately and only waits
    # (POLL_INTERVAL) when nothing is ready


if __name__ == "__main__":
  main()
