# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).resolve().parent


def root_path(relative):
    return str(PROJECT_ROOT / relative)


datas = [
    (root_path('resources/models/yunet_2023mar.onnx'), 'models'),
    (root_path('resources/models/ediffiqa_t.onnx'), 'models'),
    (root_path('resources/models/mb1_120x120.onnx'), 'models'),
    (root_path('resources/models/ppocrv5_mobile_det/inference.onnx'), 'models/ppocrv5_mobile_det'),
    (root_path('resources/models/composite_split_cache/person_detect_v1.3_s/model.onnx'), 'models/composite_split_cache/person_detect_v1.3_s'),
    (root_path('resources/models/composite_split_cache/head_detect_v2.0_s/model.onnx'), 'models/composite_split_cache/head_detect_v2.0_s'),
    (root_path('resources/models/auto_crop/skytnt_anime_seg_isnetis/isnetis.onnx'), 'models/auto_crop/skytnt_anime_seg_isnetis'),
    (root_path('resources/models/text_cleanup/migan/migan_pipeline_v2.onnx'), 'models/text_cleanup/migan'),
]

a = Analysis(
    [root_path('tools/benchmarks/directml_root_cause_probe.py')],
    pathex=[
        root_path('src'),
        root_path('tools/benchmarks'),
        str(PROJECT_ROOT),
    ],
    binaries=[],
    datas=datas,
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
    name='Face LoRA DirectML Root Cause',
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
    name='FaceLoRA-DirectML-Root-Cause',
)
