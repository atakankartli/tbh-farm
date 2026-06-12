"""Detect that a farmed run cleared — from the save file, not tbh-meter.

A blue chest only drops when a full run completes (boss kill), and we navigate
to a stage only when our timer says it's READY, so the FIRST clear after we
arrive drops the chest. Gold accrues all run long, so we can't use a gold
threshold to spot the boss kill; instead we wait the stage's measured clear
time (×margin), which guarantees a run finished, and use the save's rising
gold-earned counter only as a "still farming, not stuck" sanity check.
"""

from __future__ import annotations

import time

import config
import savefile
from tracker import ReadyStage


def clear_time(target: ReadyStage) -> float:
  key = f"{target.act}-{target.stage}:{target.difficulty.upper()}"
  table = getattr(config, "CLEAR_TIME_SEC", {})
  return table.get(key, getattr(config, "CLEAR_TIME_DEFAULT", 300))


def wait_for_clear(target: ReadyStage, timeout: float | None = None) -> bool:
  """Block until a full run has completed on `target` (so the boss was killed
  and the chest dropped), or timeout. Returns True on a confirmed clear.

  Gate: ELAPSED >= clear_time * margin guarantees a run finished; gold-rise is
  a sanity check that the game is actually farming (not paused/stuck)."""
  timeout = timeout if timeout is not None else getattr(config, "RUN_TIMEOUT_SEC", 900)
  poll = getattr(config, "SAVE_POLL_SEC", 15)
  margin = getattr(config, "CLEAR_TIME_MARGIN", 1.3)
  need_sec = clear_time(target) * margin
  gold_floor = getattr(config, "GOLD_SANITY_FLOOR", 3000)

  try:
    base_gold = savefile.load().gold_earned
  except Exception as exc:
    print(f"  runwatch: can't read save ({exc}); timed wait {int(need_sec)}s")
    time.sleep(min(timeout, getattr(config, "FALLBACK_CLEAR_SEC", 300)))
    return True

  start = time.time()
  print(f"  Waiting for {target.act}-{target.stage} full clear "
        f"(~{int(need_sec)}s; up to {int(timeout / 60)} min)...")

  while time.time() - start < timeout:
    time.sleep(poll)
    elapsed = time.time() - start
    try:
      gained = savefile.load().gold_earned - base_gold
    except Exception:
      continue
    if elapsed >= need_sec and gained >= gold_floor:
      print(f"  Clear confirmed: {int(elapsed)}s elapsed, +{gained:,} gold")
      return True
    if elapsed >= need_sec and gained < gold_floor:
      # time's up but no gold — game paused/stuck; keep waiting until timeout
      print(f"  ...{int(elapsed)}s elapsed but only +{gained:,} gold; still waiting")

  print(f"  runwatch: no clear confirmed within {int(timeout / 60)} min")
  return False
