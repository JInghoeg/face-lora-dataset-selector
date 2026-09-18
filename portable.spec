# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_dynamic_libs

# Bundle only this project's runtime models. MI-GAN remains on-demand.
datas = [('models', 'models')]

# MediaPipe needs native extension modules, but collecting the entire package
# with collect_all() also drags in unrelated features and data. Keep native
# binaries and let PyInstaller's import graph collect Python modules actually
# reached by the application/runtime.
binaries = collect_dynamic_libs('mediapipe')

hiddenimports = [
    'mediapipe.tasks.python.vision.pose_landmarker',
    'mediapipe.tasks.python.vision.core.vision_task_running_mode',
]

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # These GUI stacks are not used by the application.
        'PyQt5',
        'PyQt6',
        'PySide2',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Face LoRA Dataset Selector',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Face-LoRA-Dataset-Selector',
)
