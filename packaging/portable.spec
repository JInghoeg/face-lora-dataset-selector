# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

PROJECT_ROOT = Path(SPECPATH).resolve().parent

def root_path(relative):
    return str(PROJECT_ROOT / relative)

# Bundle only the explicitly tracked runtime models. MI-GAN and Composite Split
# detector caches remain on-demand and must never be swept into Portable builds
# just because a developer has downloaded them locally.
datas = [
    (root_path('models/yunet_2023mar.onnx'), 'models'),
    (root_path('models/ediffiqa_t.onnx'), 'models'),
    (root_path('models/brisque_model_live.yml'), 'models'),
    (root_path('models/brisque_range_live.yml'), 'models'),
    (root_path('models/mb1_120x120.onnx'), 'models'),
    (root_path('models/param_mean_std_62d_120x120.pkl'), 'models'),
    (root_path('models/pose_landmarker_lite.task'), 'models'),
    (root_path('models/ppocrv5_mobile_det/inference.onnx'), 'models/ppocrv5_mobile_det'),
    (root_path('models/ppocrv5_mobile_det/inference.yml'), 'models/ppocrv5_mobile_det'),
    (root_path('translations/app_en_US.qm'), 'translations'),
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
    [root_path('app.py')],
    pathex=[str(PROJECT_ROOT)],
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
