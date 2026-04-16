"""
海岸线平滑 — 在 tile_map 上平滑陆海边界

算法参考 Azgaar Fantasy Map Generator 的海岸线处理:
1. 提取陆海边界像素
2. 对 tile_map 做高斯模糊
3. 用阈值重新二值化（陆/海）
4. 保持湖泊不变

效果：锯齿状海岸线变成自然弧线。
应在生成省份之前使用，这样省份边界自然跟随平滑后的海岸线。
"""
import numpy as np
from scipy.ndimage import gaussian_filter

from data.constants import TILE_LAND, TILE_SEA, TILE_LAKE


def smooth_coastline(
    tile_map: np.ndarray,
    strength: float = 2.0,
    region: tuple[int, int, int, int] | None = None,
) -> np.ndarray:
    """平滑 tile_map 的陆海边界。

    参数:
        tile_map: (H, W) uint8, TILE_LAND/SEA/LAKE
        strength: 平滑强度（高斯 sigma），越大越平滑
        region: 可选 (y0, x0, y1, x1) 局部区域，None=全图

    返回:
        新的 tile_map（不修改原数组）
    """
    result = tile_map.copy()

    if region is not None:
        y0, x0, y1, x1 = region
        # 留 margin 给高斯模糊避免边缘伪影
        margin = int(strength * 4)
        H, W = tile_map.shape
        ey0 = max(0, y0 - margin)
        ex0 = max(0, x0 - margin)
        ey1 = min(H, y1 + margin)
        ex1 = min(W, x1 + margin)
        sub = tile_map[ey0:ey1, ex0:ex1]
    else:
        sub = tile_map
        y0, x0 = 0, 0
        ey0, ex0 = 0, 0

    # 保存湖泊位置（不参与平滑）
    lake_mask = sub == TILE_LAKE

    # 陆地二值图：陆地=1，其余=0
    land_float = (sub == TILE_LAND).astype(np.float32)

    # 高斯模糊
    blurred = gaussian_filter(land_float, sigma=strength)

    # 阈值化：> 0.5 → 陆地，否则海洋
    new_land = blurred > 0.5

    # 构建平滑后的子图
    smoothed = np.where(new_land, TILE_LAND, TILE_SEA).astype(sub.dtype)
    smoothed[lake_mask] = TILE_LAKE

    if region is not None:
        # 只把用户指定的区域写回（margin 部分不写）
        ry0 = y0 - ey0
        rx0 = x0 - ex0
        ry1 = ry0 + (y1 - y0)
        rx1 = rx0 + (x1 - x0)
        result[y0:y1, x0:x1] = smoothed[ry0:ry1, rx0:rx1]
    else:
        result[:] = smoothed

    return result
