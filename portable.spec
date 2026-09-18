# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_dynamic_libs

# Bundle only this project's runtime models. MI-GAN remains on-demand.
datas = [('models', 'models')]

# MediaPipe uses native extension modules. Keep its native binaries, but do
# not collect the whole Python package: the application only uses PoseLandmarker.
binaries = collect_dynamic_libs('mediapipe')

# The imports below are deliberately narrow. In particular, do not use
# collect_all('mediapipe') or collect_all('rapidocr_onnxruntime'): those pull
# unrelated vision/audio/OCR features and bundled OCR weights into Portable.
hiddenimports = [
    'mediapipe.tasks.python.vision.pose_landmarker',
    'mediapipe.tasks.python.vision.core.vision_task_running_mode',
    'rapidocr_onnxruntime.ch_ppocr_det.text_detect',
    'rapidocr_onnxruntime.ch_ppocr_det.utils',
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
        # Optional MediaPipe ecosystems not used by this application.
        'jax',
        'jaxlib',
        'matplotlib',
        'sounddevice',
        'mediapipe.tasks.python.audio',
        'mediapipe.tasks.python.text',
        # Avoid accidental inclusion of unrelated GUI stacks.
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
