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
  """Block until the run on `target` finishes. Returns:
    "dropped" — the game LOGGED a blue-chest drop for this stage's level
                (droplog.DropWatcher; real-time, authoritative)
    "cleared" — a run completed (save run-counter / timed gate) but no drop
                line was seen; the caller decides whether to trust it
    None      — nothing confirmed within the timeout

  learn=False skips clear-time learning — used when we joined a run already in
  progress (no navigation), where the measured time would be a partial run."""
  timeout = timeout if timeout is not None else getattr(config, "RUN_TIMEOUT_SEC", 900)
  poll = getattr(config, "SAVE_POLL_SEC", 15)
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
    print(f"  runwatch: can't read save ({exc}); timed wait {int(need_sec)}s")
    time.sleep(min(timeout, getattr(config, "FALLBACK_CLEAR_SEC", 300)))
    return "dropped" if drop_seen() else "cleared"

  base_gold = base.gold_earned
  prev_clears, prev_saved = base.total_clears, base.saved_at
  counter_ok = prev_clears > 0

  start = time.time()
  print(f"  Waiting for {target.act}-{target.stage} full clear "
        f"(~{int(need_sec)}s; up to {int(timeout / 60)} min)...")

  while time.time() - start < timeout:
    time.sleep(poll)
    elapsed = time.time() - start

    # The game logs the drop the moment it happens — no save-flush lag.
    if drop_seen():
      if learn and 0 < elapsed <= timeout:
        _record_clear_time(key, elapsed)
      print(f"  Blue drop LOGGED by the game after {int(elapsed)}s — clear + drop confirmed")
      return "dropped"

    try:
      s = savefile.load()
    except Exception:
      continue
    gained = s.gold_earned - base_gold

    if counter_ok and s.saved_at > prev_saved:
      runs = s.total_clears - prev_clears
      if runs > 0 and prev_saved >= start:
        # The whole flush window is after navigation, so the clear is ours.
        # Best estimate of the kill moment: middle of the window.
        est = (prev_saved + s.saved_at) / 2 - start
        # est > timeout means the measurement is bogus (PC slept mid-wait)
        if learn and runs == 1 and 0 < est <= timeout:
          _record_clear_time(key, est)
        print(f"  Clear confirmed by run counter: +{runs} run(s), {int(elapsed)}s elapsed")
        return "dropped" if drop_seen() else "cleared"
      # Window overlaps pre-navigation time (could contain the previous
      # stage's clear) or no new runs yet — re-baseline on this flush.
      prev_clears, prev_saved = s.total_clears, s.saved_at

    if elapsed >= need_sec and gained >= gold_floor:
      print(f"  Clear confirmed: {int(elapsed)}s elapsed, +{gained:,} gold")
      return "dropped" if drop_seen() else "cleared"
    if elapsed >= need_sec and gained < gold_floor:
      # time's up but no gold — game paused/stuck; keep waiting until timeout
      print(f"  ...{int(elapsed)}s elapsed but only +{gained:,} gold; still waiting")

  print(f"  runwatch: no clear confirmed within {int(timeout / 60)} min")
  return None
