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
