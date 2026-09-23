# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# Bundle only the explicitly tracked runtime models. MI-GAN and Composite Split
# detector caches remain on-demand and must never be swept into Portable builds
# just because a developer has downloaded them locally.
datas = [
    ('models/yunet_2023mar.onnx', 'models'),
    ('models/ediffiqa_t.onnx', 'models'),
    ('models/brisque_model_live.yml', 'models'),
    ('models/brisque_range_live.yml', 'models'),
    ('models/mb1_120x120.onnx', 'models'),
    ('models/param_mean_std_62d_120x120.pkl', 'models'),
    ('models/pose_landmarker_lite.task', 'models'),
    ('models/ppocrv5_mobile_det/inference.onnx', 'models/ppocrv5_mobile_det'),
    ('models/ppocrv5_mobile_det/inference.yml', 'models/ppocrv5_mobile_det'),
]

# QFluentWidgets loads packaged QSS/resources at runtime.  The selected Auto
# Crop production UI uses these assets while still keeping PySide6-Essentials.
datas += collect_data_files('qfluentwidgets')

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
        # AVIF is not an accepted input format in this application; the Pillow
        # AVIF extension alone adds several MB to the Portable folder.
        'PIL.AvifImagePlugin',
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
