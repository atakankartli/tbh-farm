"""Shared hotkey loop — never call sys.exit() inside keyboard callbacks."""

from __future__ import annotations

import time

import keyboard


class HotkeySession:
  def __init__(self) -> None:
    self.done = False

  def stop(self) -> None:
    self.done = True
    keyboard.unhook_all()

  def run(self, *, tick: float = 0.05, on_tick=None) -> None:
    while not self.done:
      if on_tick:
        on_tick()
      time.sleep(tick)
