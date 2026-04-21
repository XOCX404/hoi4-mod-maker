"""
DowngradeMountainCommand — 一键把"太多山"降级。

做三件事:
1. 视觉层 (terrain.bmp): 雪山→山地, 山地→丘陵, 丘陵→平原
   + 连通分量清理<50px 的小丘陵斑块→平原
2. 高度图 (height_map): 同步降一级 (雪-45, 山-35, 丘-30)
   这保证游戏内 3D 效果和贴图一致, 不会出现"平原贴图但还是高山"的割裂
3. 属性层 (provincial_terrain dict): 同步降级 per-province 类型

支持 undo (保存旧 terrain_map + 旧 height_map + 旧 provincial_terrain dict)。
"""
from __future__ import annotations

import numpy as np

from commands.base import Command
from data.constants import SEA_LEVEL
from data.terrain_types import PALETTE_TO_TYPE, TERRAIN_PALETTE_INDEX
from domain.map_data import MapData


# 视觉层(terrain.bmp) 的 palette 降级映射
# 保持大生态（沙漠山地→沙漠丘陵），其他山地→通用丘陵
_PALETTE_DOWNGRADE: dict[int, int] = {
    # 雪山 → 山地
    16: 6,       # snow_16 → terrain_6 (mountain)
    31: 6,       # desert_mountain_tops → mountain
    19: 0,       # plains_snow → plains
    # 山地 → 丘陵 (保留沙漠生态)
    6: 17,       # terrain_6 (mountain) → hills_blend
    10: 17,      # terrain_10 → hills_blend
    11: 8,       # desert_mountain_11 → desert_hills (沙漠丘陵)
    18: 17,      # sand mountain variation → hills_blend
    20: 17,      # grass mountain variation → hills_blend
    27: 1,       # jungle_mountain → forest(丛林里降级成森林/丘陵争议,用森林)
    # 丘陵 → 平原 (保留沙漠)
    17: 0,       # hills_blend → terrain_0 (plains)
    2: 3,        # desert_mountain(hills type) → desert
    8: 3,        # desert_hills → desert
}


# 属性层(provincial_terrain dict) 的类型名降级
_TYPE_DOWNGRADE: dict[str, str] = {
    "mountain": "hills",
    "hills": "plains",
}


# 降级后，小于此像素数的孤立"丘陵"斑块（原本是散落的山地碎点）
# 被清理成平原。直接修复"平原区域散落橙色碎点"的问题。
_MIN_PATCH_PIXELS = 50

# 丘陵类的 palette 索引（降级后要清理的）
_HILLS_PALETTES = (17, 2, 8)

# 高度图降级量（按原像素所在的 palette 类别）
# HOI4 高度 band 中心间隔约 40，降一个 band ≈ 减 30-45
_SNOW_PALETTES = (16, 19, 31)
_MOUNTAIN_PALETTES = (6, 10, 11, 18, 20, 27)
_HEIGHT_DROP_SNOW = 45      # 雪山 -45 → 山地高度
_HEIGHT_DROP_MOUNTAIN = 35  # 山地 -35 → 丘陵高度
_HEIGHT_DROP_HILLS = 30     # 丘陵 -30 → 平原高度


class DowngradeMountainCommand(Command):
    """一键降级山脉。"""

    label = "一键降级山脉"

    def __init__(
        self,
        map_data: MapData,
        mask: np.ndarray | None = None,
        strength: float = 0.5,
    ) -> None:
        """
        mask: None = 对整张地图降级
              (H,W) bool 数组 = 仅对 mask==True 的像素降级
        strength: 0..1, 降级力度
            1.0 = 整个 band 都降级 (-45/-35/-30 高度)
            0.5 = 只降 band 上半段 (-22/-17/-15 高度, 更温和)
            0.0 = 啥都不降 (no-op)
        """
        self._map_data = map_data
        self._mask = mask.copy() if mask is not None else None
        self._strength = float(max(0.0, min(1.0, strength)))
        self._old_terrain: np.ndarray | None = None
        self._old_height: np.ndarray | None = None
        self._old_prov_terrain: dict | None = None

    def execute(self) -> None:
        if self._strength <= 0:
            # no-op, 仍然 snapshot 方便统一 undo
            self._old_terrain = self._map_data.terrain_map.copy()
            self._old_height = self._map_data.height_map.copy()
            self._old_prov_terrain = dict(self._map_data.provincial_terrain)
            return

        # 注意: terrain_map 是 ref, 改回去会污染. 必须先 copy 原始值
        tm_orig = self._map_data.terrain_map.copy()  # 原始 palette 给高度降级用
        hm = self._map_data.height_map
        self._old_terrain = tm_orig
        self._old_height = hm.copy()
        self._old_prov_terrain = dict(self._map_data.provincial_terrain)

        # —— Step 1: 按强度计算每个 band 的"降级阈值"
        # 强度 1.0: 整个 band 都降级 (threshold = band_low)
        # 强度 0.5: 只降 band 上半段 (threshold = 中点)
        # 强度 0.2: 只降 band 最顶端 20%
        # 对陆地像素逐个判断"当前高度 > 阈值"才降级
        # Band 区间 (对应 TerrainGenConfig 默认值):
        #   Hills: 130-165, Mountain: 165-210, Snow: 210+
        #   Plains: <130 (不降级)
        s = self._strength
        hills_thr = 130 + (1 - s) * 35   # 130..165
        mountain_thr = 165 + (1 - s) * 45  # 165..210
        snow_thr = 210 + (1 - s) * 30    # 210..240 (snow 上限算 240)

        # 找出每种 band 里"够高被降级"的像素
        was_snow = np.isin(tm_orig, _SNOW_PALETTES) & (hm >= snow_thr)
        was_mountain = np.isin(tm_orig, _MOUNTAIN_PALETTES) & (hm >= mountain_thr)
        was_hills = np.isin(tm_orig, _HILLS_PALETTES) & (hm >= hills_thr)
        downgrade_mask = was_snow | was_mountain | was_hills

        # —— Step 2: 只对 downgrade_mask 内的像素应用 palette LUT ——
        lut = np.arange(256, dtype=np.uint8)
        for old_idx, new_idx in _PALETTE_DOWNGRADE.items():
            lut[old_idx] = new_idx
        new_tm = tm_orig.copy()
        new_tm[downgrade_mask] = lut[tm_orig[downgrade_mask]]

        # —— Step 3: 清理小丘陵斑块 (只处理刚降下来的 hills) ——
        hills_after = np.isin(new_tm, _HILLS_PALETTES) & downgrade_mask
        small_patch_mask = np.zeros_like(hills_after)
        if np.any(hills_after):
            from scipy.ndimage import label as _label
            labels, n = _label(hills_after, structure=np.ones((3, 3), dtype=bool))
            if n > 0:
                sizes = np.bincount(labels.ravel())
                small_labels = np.where(sizes < _MIN_PATCH_PIXELS)[0]
                small_labels = small_labels[small_labels > 0]
                if len(small_labels) > 0:
                    small_patch_mask = np.isin(labels, small_labels)
                    new_tm[small_patch_mask] = 0

        # —— 如果指定了选区 mask, 把 mask 外的 terrain 恢复为原值 ——
        if self._mask is not None:
            new_tm[~self._mask] = tm_orig[~self._mask]

        self._map_data.terrain_map[:] = new_tm

        # —— Step 4: 高度图降级 (只降 Step 1 标记为被降级的像素, 量按 strength 缩放) ——
        new_hm = hm.astype(np.int16)  # 用 int16 避免下溢
        # 如果有 mask, 高度降级也限制在选区内
        if self._mask is not None:
            was_snow = was_snow & self._mask
            was_mountain = was_mountain & self._mask
            was_hills = was_hills & self._mask
            small_patch_mask_in = small_patch_mask & self._mask
        else:
            small_patch_mask_in = small_patch_mask
        # 按 strength 缩放下降量(1.0=-45/-35/-30, 0.5=-22/-17/-15)
        new_hm[was_snow] -= int(_HEIGHT_DROP_SNOW * s)
        new_hm[was_mountain] -= int(_HEIGHT_DROP_MOUNTAIN * s)
        new_hm[was_hills] -= int(_HEIGHT_DROP_HILLS * s)
        # 小斑点额外降
        extra_drop = small_patch_mask_in & (~was_snow)
        new_hm[extra_drop] -= int(15 * s)
        # 守底线: 陆地不能低于 SEA_LEVEL+1
        land_mask = self._map_data.tile_map == 1  # TILE_LAND
        np.clip(new_hm, 0, 255, out=new_hm)
        new_hm_u8 = new_hm.astype(np.uint8)
        # 陆地像素至少 SEA_LEVEL+1
        np.maximum(
            new_hm_u8, SEA_LEVEL + 1, out=new_hm_u8, where=land_mask
        )
        self._map_data.height_map[:] = new_hm_u8

        # —— Step 5: 降级 provincial_terrain dict (属性层) ——
        # 只降级"过半像素实际被改"的省份, 避免零星像素变化就改整省属性
        changed_mask = downgrade_mask.copy()
        if self._mask is not None:
            changed_mask &= self._mask
        downgrade_pids = self._pids_majority_in_mask(changed_mask)

        new_prov: dict = {}
        for pid, typ in self._old_prov_terrain.items():
            if pid in downgrade_pids:
                new_prov[pid] = _TYPE_DOWNGRADE.get(typ, typ)
            else:
                new_prov[pid] = typ
        self._map_data.provincial_terrain.clear()
        self._map_data.provincial_terrain.update(new_prov)

    def _pids_majority_in_mask(self, mask: np.ndarray) -> set[int]:
        """返回 province_map 里 >50% 像素落在 mask 内的 province id 集合。"""
        if not np.any(mask):
            return set()
        pm = self._map_data.province_map
        all_pids = pm.ravel()
        max_pid = int(all_pids.max())
        total = np.bincount(all_pids, minlength=max_pid + 1)
        in_cnt = np.bincount(pm[mask], minlength=max_pid + 1)
        ratio = np.zeros_like(total, dtype=np.float32)
        nonzero = total > 0
        ratio[nonzero] = in_cnt[nonzero] / total[nonzero]
        pids = np.where(ratio > 0.5)[0]
        return set(int(p) for p in pids if p > 0)

    def undo(self) -> None:
        if self._old_terrain is not None:
            self._map_data.terrain_map[:] = self._old_terrain
        if self._old_height is not None:
            self._map_data.height_map[:] = self._old_height
        if self._old_prov_terrain is not None:
            self._map_data.provincial_terrain.clear()
            self._map_data.provincial_terrain.update(self._old_prov_terrain)
