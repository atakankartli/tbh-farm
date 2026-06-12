"""Real drop detection from the game's own Unity log — no inference.

When a stage-boss (blue) chest drops, TaskBarHero's Player.log gets a line:

    GetBoxCount Success Count : 1 // ItemKey : 920651

The item key encodes the chest: prefix 920 = blue (stage-boss) chest,
then the two-digit chest level, then a trailing 1 (920651 = level 65,
920151 = level 15). Normal/white chests use the 910 prefix and are ignored.

DropWatcher tails the log from the moment it's created, so a drop is only
credited when the GAME says one happened — never assumed from a cleared run.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

import config

_BLUE_DROP_RE = re.compile(r"GetBoxCount Success Count : \d+ // ItemKey : 920(\d{2})1\b")


def log_path() -> Path:
  """Player.log lives next to the save file; PLAYER_LOG in config overrides."""
  override = getattr(config, "PLAYER_LOG", None)
  if override:
    return Path(os.path.expanduser(override))
  save = getattr(config, "SAVE_FILE",
                 os.path.expanduser(r"~\AppData\LocalLow\TesseractStudio\TaskBarHero\SaveFile_Live.es3"))
  return Path(save).parent / "Player.log"


class DropWatcher:
  """Tail Player.log for blue-chest drop lines appearing after start."""

  def __init__(self) -> None:
    self.path = log_path()
    try:
      self._offset = self.path.stat().st_size
    except OSError:
      self._offset = 0

  def new_blue_drops(self) -> list[int]:
    """Chest LEVELS of blue drops logged since the last call (empty if none).
    Handles the game restarting (log recreated -> smaller file)."""
    try:
      size = self.path.stat().st_size
    except OSError:
      return []
    if size < self._offset:  # log rotated (game restarted)
      self._offset = 0
    if size == self._offset:
      return []
    with open(self.path, encoding="utf-8", errors="replace") as fh:
      fh.seek(self._offset)
      chunk = fh.read()
      self._offset = fh.tell()
    return [int(m.group(1)) for m in _BLUE_DROP_RE.finditer(chunk)]


class DropTracker:
  """Persistent drop ledger for the whole farm session.

  Every blue drop seen in Player.log goes pending (keyed by chest level) until
  a farm cycle consumes it — so drops logged while we were navigating, between
  cycles, or while waiting on a different stage are never lost. Stamping uses
  the time the drop was SEEN, so a late consume still starts the cooldown at
  the right moment."""

  def __init__(self) -> None:
    self._watcher = DropWatcher()
    self.pending: dict[int, int] = {}   # chest level -> dropAt (ms)
    self.last_taken_ms: int | None = None

  def refresh(self) -> None:
    for level in self._watcher.new_blue_drops():
      self.pending[level] = int(time.time() * 1000)
      print(f"  Drop ledger: blue chest Lv{level} logged by the game")

  def take(self, level: int) -> int | None:
    """Consume a pending drop of this chest level (0 = any, newest first).
    Returns its dropAt timestamp in ms, or None."""
    self.refresh()
    key = None
    if level:
      if level in self.pending:
        key = level
    elif self.pending:
      key = max(self.pending, key=self.pending.get)
    if key is None:
      return None
    self.last_taken_ms = self.pending.pop(key)
    return self.last_taken_ms
