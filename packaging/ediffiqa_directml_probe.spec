# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).resolve().parent


def root_path(relative):
    return str(PROJECT_ROOT / relative)


a = Analysis(
    [root_path('tools/benchmarks/ediffiqa_directml_probe.py')],
    pathex=[
        root_path('src'),
        root_path('tools/benchmarks'),
        str(PROJECT_ROOT),
    ],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PIL.AvifImagePlugin',
        'qfluentwidgets',
        'mediapipe',
        'cv2',
        'pyqtgraph',
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
    name='Face LoRA eDifFIQA DirectML Probe',
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
    name='FaceLoRA-eDifFIQA-DirectML-Probe',
)
