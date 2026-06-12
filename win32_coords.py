"""Windows DPI + multi-monitor helpers (Win32 client-area coords)."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32


class RECT(ctypes.Structure):
  _fields_ = [
    ("left", ctypes.c_long),
    ("top", ctypes.c_long),
    ("right", ctypes.c_long),
    ("bottom", ctypes.c_long),
  ]


class POINT(ctypes.Structure):
  _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def enable_dpi_awareness() -> None:
  """Match mouse coords to GetWindowRect on multi-monitor + scaled displays."""
  try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
    return
  except Exception:
    pass
  try:
    user32.SetProcessDPIAware()
  except Exception:
    pass


enable_dpi_awareness()


def get_client_rect_screen(hwnd: int) -> tuple[int, int, int, int]:
  """Client area origin + size in virtual screen coordinates."""
  client = RECT()
  if not user32.GetClientRect(hwnd, ctypes.byref(client)):
    raise OSError(f"GetClientRect failed for hwnd {hwnd}")

  origin = POINT(0, 0)
  if not user32.ClientToScreen(hwnd, ctypes.byref(origin)):
    raise OSError(f"ClientToScreen failed for hwnd {hwnd}")

  width = client.right - client.left
  height = client.bottom - client.top
  return origin.x, origin.y, width, height


def get_cursor_pos() -> tuple[int, int]:
  pt = POINT()
  user32.GetCursorPos(ctypes.byref(pt))
  return pt.x, pt.y


def move_cursor(x: int, y: int) -> None:
  user32.SetCursorPos(int(x), int(y))


def click_screen(x: int, y: int) -> None:
  user32.SetCursorPos(int(x), int(y))
  # MOUSEEVENTF_LEFTDOWN=0x0002, MOUSEEVENTF_LEFTUP=0x0004
  user32.mouse_event(0x0002, 0, 0, 0, 0)
  user32.mouse_event(0x0004, 0, 0, 0, 0)


def drag_screen(x1: int, y1: int, x2: int, y2: int, *, steps: int = 15, duration: float = 0.3) -> None:
  """Press, move in small steps so the game registers a drag, release."""
  import time

  user32.SetCursorPos(int(x1), int(y1))
  user32.mouse_event(0x0002, 0, 0, 0, 0)
  time.sleep(0.08)
  for i in range(1, steps + 1):
    t = i / steps
    user32.SetCursorPos(int(x1 + (x2 - x1) * t), int(y1 + (y2 - y1) * t))
    time.sleep(duration / steps)
  time.sleep(0.05)
  user32.mouse_event(0x0004, 0, 0, 0, 0)


def activate_hwnd(hwnd: int) -> bool:
  """Bring the window to the foreground so screen captures show it unoccluded.

  Plain SetForegroundWindow is silently rejected when the caller is not the
  foreground process (typical when running from a terminal); pressing Alt
  around the call is the documented workaround for the foreground lock."""
  try:
    if user32.GetForegroundWindow() == hwnd:
      return True
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE in case it is minimized
    user32.keybd_event(0x12, 0, 0, 0)        # Alt down
    user32.SetForegroundWindow(hwnd)
    user32.keybd_event(0x12, 0, 0x0002, 0)   # Alt up
    return user32.GetForegroundWindow() == hwnd
  except Exception:
    return False

