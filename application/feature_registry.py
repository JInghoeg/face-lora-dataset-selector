"""Built-in feature registry.

This is intentionally small: it describes internal product capabilities and their
contributions. It is not a third-party plugin loader.
"""
from __future__ import annotations

from core.contracts import FeatureSpec


class FeatureRegistry:
    def __init__(self, specs=()):
        self._specs = {}
        for spec in specs:
            self.register(spec)

    def register(self, spec: FeatureSpec):
        if spec.feature_id in self._specs:
            raise ValueError(f'duplicate feature id: {spec.feature_id}')
        self._specs[spec.feature_id] = spec

    def contains(self, feature_id: str) -> bool:
        return feature_id in self._specs

    def specs(self):
        return tuple(self._specs.values())

    def excluded_source_dirs(self):
        values = []
        seen = set()
        for spec in self._specs.values():
            for name in spec.excluded_source_dirs:
                folded = name.casefold()
                if folded not in seen:
                    seen.add(folded)
                    values.append(name)
        return tuple(values)


def default_registry():
    return FeatureRegistry(
        (
            FeatureSpec('ranking', '数据集质量排序 / 推荐', optional=False),
            FeatureSpec('duplicates', '近重复筛选'),
            FeatureSpec(
                'composite',
                '组合图检测与切分',
                excluded_source_dirs=('_CompositeSplit_Originals',),
            ),
            FeatureSpec('text_cleanup', '字幕 / 水印检测与修复'),
            FeatureSpec('auto_crop', 'General Auto Crop'),
            FeatureSpec('source_organizer', 'Source Organizer'),
        )
    )
