"""Read TaskBarHero's encrypted save directly — no OCR, no tbh-meter.

Decryption approach forked from shigake/tbh-copilot (MIT), which extracted the
Easy Save 3 password from the IL2CPP game binary. ES3 scheme:
  key = PBKDF2-HMAC-SHA1(password, salt=IV, iterations=100, dkLen=16)
  plaintext = AES-128-CBC-decrypt(ciphertext, key, IV); PKCS7; optional gzip
The first 16 bytes of the file are the IV.

What the save DOES contain: party, hero levels, gold, stage progress,
inventory + stash occupancy, runes, gear. What it does NOT contain: blue-chest
cooldown timers (those live in game memory only — see chests.py).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass

from Crypto.Cipher import AES

import config

# ES3 password baked into the game binary (extracted by tbh-copilot).
ES3_PASSWORD = getattr(config, "ES3_PASSWORD", "emuMqG3bLYJ938ZDCfieWJ").encode()

SAVE_PATH = getattr(
  config, "SAVE_FILE",
  os.path.expanduser(r"~\AppData\LocalLow\TesseractStudio\TaskBarHero\SaveFile_Live.es3"),
)

# .NET DateTime ticks (100ns since 0001-01-01) -> Unix seconds
_TICKS_EPOCH_OFFSET = 62135596800
STASH_PER_PAGE = 49  # 343 slots = 7 pages of 49

HERO_CLASS = {101: "Knight", 201: "Ranger", 301: "Sorcerer",
              401: "Priest", 501: "Hunter", 601: "Slayer"}


def _es3_decrypt(blob: bytes) -> bytes:
  iv = blob[:16]
  key = hashlib.pbkdf2_hmac("sha1", ES3_PASSWORD, iv, 100, dklen=16)
  plain = AES.new(key, AES.MODE_CBC, iv).decrypt(blob[16:])
  plain = plain[: -plain[-1]]  # strip PKCS7 padding
  if plain[:2] == b"\x1f\x8b":
    plain = gzip.decompress(plain)
  return plain


def _parse_inner(raw: str) -> dict:
  """PlayerSaveData.value is JSON-in-a-string; 16+ digit ints overflow JS so
  the game stores them unquoted but oversized — quote them before parsing
  (mirrors tbh-copilot's parseSave)."""
  fixed = re.sub(
    r"([:\[,])(\s*)(\d{16,})(?=\s*[,\]}])",
    lambda m: m.group(1) + m.group(2) + '"' + m.group(3) + '"',
    raw,
  )
  return json.loads(fixed)


@dataclass
class Save:
  player: dict
  account: dict
  system: dict

  # ---- timestamps ----
  @property
  def saved_at(self) -> float:
    ticks = int(self.player["commonSaveData"]["lastSavedTime"])
    return ticks / 1e7 - _TICKS_EPOCH_OFFSET

  @property
  def play_time_sec(self) -> float:
    return self.player["commonSaveData"].get("playTime", 0)

  # ---- progress ----
  @property
  def current_stage_key(self) -> int:
    return self.player["commonSaveData"].get("currentStageKey", 0)

  @property
  def max_completed_stage(self) -> int:
    return self.player["commonSaveData"].get("maxCompletedStage", 0)

  @property
  def party(self) -> list[int]:
    return [k for k in self.player["commonSaveData"].get("arrangedHeroKey", []) if k]

  @property
  def gold(self) -> int:
    for c in self.player.get("currenySaveDatas", []):
      if c.get("Quantity") is not None:
        return c["Quantity"]
    return 0

  def max_party_level(self) -> int:
    levels = {h["heroKey"]: h.get("HeroLevel", 1) for h in self.player.get("heroSaveDatas", [])}
    return max((levels.get(k, 1) for k in self.party), default=1)

  def party_heroes(self) -> list[dict]:
    """The arranged party in slot order, with class, level, XP and gear count."""
    saves = {h.get("heroKey"): h for h in self.player.get("heroSaveDatas", [])}
    out = []
    for key in self.party:
      hs = saves.get(key, {})
      out.append({
        "key": key,
        "cls": HERO_CLASS.get(key, f"Hero {key}"),
        "level": hs.get("HeroLevel", 1),
        "exp": hs.get("HeroExp", 0),
        "gear": sum(1 for i in hs.get("equippedItemIds", []) if i),
        "sprite": f"Hero_{key}.png",
      })
    return out

  # ---- lifetime aggregates (monotonic counters; used to detect run progress) ----
  def aggregate(self, type_: int, subkey: int) -> int:
    for row in self.player.get("aggregateSaveDatas", []):
      if row.get("Type") == type_ and row.get("SubKey") == subkey:
        return row.get("Value", 0)
    return 0

  @property
  def gold_earned(self) -> int:
    """Lifetime gold earned (only ever increases) — a clean 'a run paid out'
    signal, unlike the spendable gold balance."""
    return self.aggregate(2, 1)

  # ---- stash / inventory occupancy (for the stash-all sweep) ----
  def _occupancy(self, slots: list[dict]) -> tuple[int, int, int]:
    unlocked = [s for s in slots if s.get("IsUnLock")]
    filled = [s for s in unlocked if s.get("ItemUniqueId")]
    return len(filled), len(unlocked), len(unlocked) - len(filled)

  def stash_occupancy(self) -> tuple[int, int, int]:
    """(filled, unlocked, free) across all stash pages."""
    return self._occupancy(self.player.get("stashSaveDatas", []))

  def stash_page_fill(self) -> dict[int, tuple[int, int]]:
    """page (1-based) -> (filled, unlocked) — lets the macro skip empty pages."""
    pages: dict[int, list[dict]] = {}
    for slot in self.player.get("stashSaveDatas", []):
      page = slot.get("Index", 0) // STASH_PER_PAGE + 1
      pages.setdefault(page, []).append(slot)
    return {
      page: (len([s for s in slots if s.get("IsUnLock") and s.get("ItemUniqueId")]),
             len([s for s in slots if s.get("IsUnLock")]))
      for page, slots in sorted(pages.items())
    }

  def inventory_occupancy(self) -> tuple[int, int, int]:
    return self._occupancy(self.player.get("inventorySaveDatas", []))

  @property
  def unopened_boxes(self) -> int:
    qty = self.player.get("BoxData", {}).get("BoxQuantity", [])
    return sum(qty) if qty else 0


def load(path: str | None = None) -> Save:
  with open(path or SAVE_PATH, "rb") as fh:
    blob = fh.read()
  outer = json.loads(_es3_decrypt(blob).decode("utf-8"))
  return Save(
    player=_parse_inner(outer["PlayerSaveData"]["value"]),
    account=outer.get("AccountSaveData", {}),
    system=outer.get("SystemInfo", {}),
  )


def summary(path: str | None = None) -> dict:
  s = load(path)
  filled, unlocked, free = s.stash_occupancy()
  inv_f, inv_u, inv_free = s.inventory_occupancy()
  return {
    "savedAt": int(s.saved_at * 1000),
    "savedAtStr": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(s.saved_at)),
    "party": s.party,
    "partyHeroes": s.party_heroes(),
    "maxPartyLevel": s.max_party_level(),
    "gold": s.gold,
    "currentStage": s.current_stage_key,
    "maxCompletedStage": s.max_completed_stage,
    "stash": {"filled": filled, "unlocked": unlocked, "free": free,
              "pages": s.stash_page_fill()},
    "inventory": {"filled": inv_f, "unlocked": inv_u, "free": inv_free},
    "unopenedBoxes": s.unopened_boxes,
  }


if __name__ == "__main__":
  print(json.dumps(summary(), indent=2))
