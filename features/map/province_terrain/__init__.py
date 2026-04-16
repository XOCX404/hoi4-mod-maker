"""省份属性地形 feature — 显示每个 province 的 gameplay 地形（用颜色块）。

和 terrain feature 区分：
- terrain feature：显示+编辑 terrain.bmp 像素（视觉）
- province_terrain feature：显示+编辑每个 province 的 gameplay terrain 类型（属性）

两个模式完全独立：在 province_terrain 模式下点 province 只改属性，不动视觉。
"""

from features.base import BaseFeature


class ProvincialTerrainFeature(BaseFeature):
    id = "map.province_terrain"
    display_name = "地形（属性）"
    category = "map"
