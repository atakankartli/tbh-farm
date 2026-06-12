"""Detect that a farmed run cleared — from the save file, not tbh-meter.

A blue chest only drops when a full run completes (boss kill), and we navigate
to a stage only when our timer says it's READY, so the FIRST clear after we
arrive drops the chest.

Two confirmation paths:
- run counter: the save's lifetime completed-runs aggregate (Type 15, verified
  against tbh-copilot's totalClears) increments. An increment whose save-flush
  window started after our navigation is definitely OUR clear — and dates the
  run, so we auto-renew the stage's learned clear time on every completion.
- timed gate (fallback): ELAPSED >= clear_time * margin guarantees a run
  finished; the rising gold-earned counter is a "still farming" sanity check.
  Used when the counter is absent or the gate fires before a save flush lands.

Learned clear times live in macro_clear_times.json and take precedence over
config.CLEAR_TIME_SEC, so stages added at runtime get measured automatically
and existing ones track the party getting stronger.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import config
import savefile
from tracker import ReadyStage

LEARNED_CLEAR_PATH = Path(__file__).with_name("macro_clear_times.json")


def _load_learned() -> dict[str, int]:
  try:
    with open(LEARNED_CLEAR_PATH, encoding="utf-8") as fh:
      return {k: int(v) for k, v in json.load(fh).items()}
  except (OSError, ValueError):
    return {}


def _record_clear_time(key: str, est_sec: float) -> None:
  """Fold a fresh per-run measurement into the learned table (EMA, so one
  outlier run can't swing the wait gate much). Stored values are clamped to
  [30, 600]s — beyond that the timed gate would exceed RUN_TIMEOUT anyway,
  and huge estimates are measurement artifacts (e.g. the PC slept mid-wait)."""
  data = _load_learned()
  old = data.get(key)
  new = max(30, min(600, int(round(est_sec if old is None else 0.7 * old + 0.3 * est_sec))))
  data[key] = new
  tmp = LEARNED_CLEAR_PATH.with_suffix(".json.tmp")
  tmp.write_text(json.dumps(data), encoding="utf-8")
  os.replace(tmp, LEARNED_CLEAR_PATH)
  was = f"was {old}s" if old else "first measurement"
  print(f"  Learned clear time {key}: {new}s ({was}; this run ~{int(est_sec)}s)")


def _key(target: ReadyStage) -> str:
  return f"{target.act}-{target.stage}:{target.difficulty.upper()}"


def clear_time(target: ReadyStage) -> float:
  """Learned (auto-renewed) time wins; config table seeds; default last."""
  key = _key(target)
  learned = _load_learned().get(key)
  if learned:
    return learned
  table = getattr(config, "CLEAR_TIME_SEC", {})
  return table.get(key, getattr(config, "CLEAR_TIME_DEFAULT", 300))


def wait_for_clear(target: ReadyStage, timeout: float | None = None, *,
                   learn: bool = True, watcher=None) -> str | None:
  """Block until the game LOGS a blue-chest drop for this stage's level.

  Cleared runs are NOT a result — the game chains runs on the stage, so when
  a run finishes without the drop (our timer was ahead of the in-game chest
  cooldown) we just keep waiting: a later chained run produces the real drop.
  Returns:
    "dropped" — drop line seen in Player.log (authoritative)
    "cleared" — only in legacy mode (watcher=None): a run completed
    None      — timeout

  learn=False skips clear-time learning — used when we joined a run already in
  progress (no navigation), where the measured time would be a partial run."""
  timeout = timeout if timeout is not None else getattr(config, "RUN_TIMEOUT_SEC", 900)
  poll = getattr(config, "SAVE_POLL_SEC", 15)
  log_poll = getattr(config, "LOG_POLL_SEC", 1.0)  # drop check is a cheap file stat
  margin = getattr(config, "CLEAR_TIME_MARGIN", 1.3)
  need_sec = clear_time(target) * margin
  gold_floor = getattr(config, "GOLD_SANITY_FLOOR", 3000)
  key = _key(target)

  def drop_seen() -> bool:
    if watcher is None:
      return False
    for level in watcher.new_blue_drops():
      if not target.level or level == target.level:
        return True
      print(f"  Ignoring blue drop of level {level} (target is Lv{target.level})")
    return False

  try:
    base = savefile.load()
  except Exception as exc:
    print(f"  runwatch: can't read save ({exc}); waiting on the drop log only")
    if watcher is None:
      time.sleep(min(timeout, getattr(config, "FALLBACK_CLEAR_SEC", 300)))
      return "cleared"
    start = time.time()
    while time.time() - start < timeout:
      time.sleep(getattr(config, "LOG_POLL_SEC", 1.0))
      if drop_seen():
        return "dropped"
    return None

  base_gold = base.gold_earned
  prev_clears, prev_saved = base.total_clears, base.saved_at
  counter_ok = prev_clears > 0
  clears_seen = 0

  start = time.time()
  print(f"  Waiting for {target.act}-{target.stage} blue drop "
        f"(clear ~{int(need_sec)}s; up to {int(timeout / 60)} min)...")

  next_save_check = start + poll
  while time.time() - start < timeout:
    time.sleep(log_poll if watcher is not None else poll)
    elapsed = time.time() - start

    # The game logs the drop the moment it happens — no save-flush lag, and
    # checked every second so we move on to the next stage right away.
    if drop_seen():
      # elapsed is a clean single-run measurement only if no earlier chained
      # run finished first
      if learn and clears_seen == 0 and 0 < elapsed <= timeout:
        _record_clear_time(key, elapsed)
      print(f"  Blue drop LOGGED by the game after {int(elapsed)}s")
      return "dropped"

    # The save read (decrypt + parse) is heavier — keep it on the slow poll.
    if watcher is not None and time.time() < next_save_check:
      continue
    next_save_check = time.time() + poll

    try:
      s = savefile.load()
    except Exception:
      continue
    gained = s.gold_earned - base_gold

    if counter_ok and s.saved_at > prev_saved:
      runs = s.total_clears - prev_clears
      if runs > 0 and prev_saved >= start:
        # The whole flush window is after navigation, so the clear is ours.
        est = (prev_saved + s.saved_at) / 2 - start
        # est > timeout means the measurement is bogus (PC slept mid-wait)
        if learn and clears_seen == 0 and runs == 1 and 0 < est <= timeout:
          _record_clear_time(key, est)
        clears_seen += runs
        if watcher is None:
          print(f"  Clear confirmed by run counter: +{runs} run(s), {int(elapsed)}s elapsed")
          return "cleared"
        print(f"  {clears_seen} run(s) cleared, no blue drop yet — the game chains "
              f"runs here, waiting for the drop...")
      # Re-baseline on every flush (pre-navigation windows are ambiguous).
      prev_clears, prev_saved = s.total_clears, s.saved_at

    if watcher is None and elapsed >= need_sec and gained >= gold_floor:
      print(f"  Clear confirmed: {int(elapsed)}s elapsed, +{gained:,} gold")
      return "cleared"
    if elapsed >= need_sec and not clears_seen and gained < gold_floor:
      # time's up but no gold — game paused/stuck; keep waiting until timeout
      print(f"  ...{int(elapsed)}s elapsed but only +{gained:,} gold; still waiting")

  what = "blue drop" if watcher is not None else "clear"
  print(f"  runwatch: no {what} within {int(timeout / 60)} min")
  return None
