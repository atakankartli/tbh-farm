# PyInstaller spec — builds a single onedir bundle with two console exes:
#   TBH-Macro.exe       (main.py — the farm loop + web GUI)
#   TBH-TestVision.exe  (test_vision.py — portal detection check, no clicks)
#
# config.py is EXCLUDED from the bundle; the runtime hook adds the exe's
# folder to sys.path so users edit the config.py shipped next to the exe.
# Writable state (macro_*.json) lands in _internal/ next to the bundled code.
#
# Build:  python -m PyInstaller packaging/tbh_macro.spec --noconfirm

import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

datas = [
    (os.path.join(ROOT, "stage_data.json"), "."),
    (os.path.join(ROOT, "dungeons.json"), "."),
    (os.path.join(ROOT, "sprites"), "sprites"),
]

common = dict(
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    excludes=["config"],
    runtime_hooks=[os.path.join(SPECPATH, "runtime_hook.py")],
    noarchive=False,
)

a_main = Analysis([os.path.join(ROOT, "main.py")], **common)
a_vision = Analysis([os.path.join(ROOT, "test_vision.py")], **common)

pyz_main = PYZ(a_main.pure)
pyz_vision = PYZ(a_vision.pure)

exe_main = EXE(
    pyz_main,
    a_main.scripts,
    [],
    exclude_binaries=True,
    name="TBH-Macro",
    console=True,
    disable_windowed_traceback=False,
)

exe_vision = EXE(
    pyz_vision,
    a_vision.scripts,
    [],
    exclude_binaries=True,
    name="TBH-TestVision",
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe_main,
    exe_vision,
    a_main.binaries,
    a_main.datas,
    a_vision.binaries,
    a_vision.datas,
    strip=False,
    upx=False,
    name="tbh-macro",
)
