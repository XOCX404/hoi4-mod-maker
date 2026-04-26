"""
v3: 按"完整条带"造墙, 再挖一个通道。

A. 哈德良-卡拉利亚 墙: 水平条带 (x=2850-3550, y=870-960), 通道 x=3320-3420
C. 东墙: 垂直条带 (x=4430-4560, y=870-1500), 通道 y=1200-1300
B. 中段: 不动

墙 = 陆地像素抬到 215 (雪山), 通道 = 降到 115 (平原).
边缘羽化 15 px. 保留陆海边界, 不改海.
"""
from __future__ import annotations

import os
import shutil
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

import numpy as np
from scipy.ndimage import distance_transform_edt

HOME = os.path.expanduser("~")
PROJECT_PATH = os.path.join(HOME, "Desktop", "欧若拉", "5.hoi4proj")
BACKUP_PATH = PROJECT_PATH + ".bak"
SEA_LEVEL = 95
WALL_H = 215          # 雪山档
PASS_H = 115          # 平原档
FEATHER = 15

WALLS = [
    # NW 水平条带墙 (between哈德良 and卡拉利亚)
    {
        "name": "NW 哈德良-卡拉利亚 墙",
        "wall_bbox": (2850, 870, 3550, 960),    # x0 y0 x1 y1 — 墙本体
        "pass_bbox": (3320, 870, 3420, 960),    # 通道
        "palette": 16,                           # 雪山
    },
    # E 垂直条带墙 (东边挡兽人)
    {
        "name": "East 兽人墙",
        "wall_bbox": (4430, 870, 4560, 1500),
        "pass_bbox": (4430, 1200, 4560, 1300),
        "palette": 16,
    },
]


def apply_wall(
    tile: np.ndarray,
    terrain: np.ndarray,
    height: np.ndarray,
    wall_bbox: tuple[int, int, int, int],
    pass_bbox: tuple[int, int, int, int],
    palette: int,
) -> tuple[int, int]:
    """填墙 + 挖通道, 只作用在陆地. 返回 (墙px, 通道px)."""
    H, W = tile.shape

    # mask
    def _box_mask(bbox):
        m = np.zeros((H, W), dtype=bool)
        x0, y0, x1, y1 = bbox
        x0 = max(0, x0); y0 = max(0, y0); x1 = min(W, x1); y1 = min(H, y1)
        m[y0:y1, x0:x1] = True
        return m

    wall_mask = _box_mask(wall_bbox)
    pass_mask = _box_mask(pass_bbox)
    land = tile == 1

    # 墙 = wall_bbox − pass_bbox (只动陆地)
    wall_apply = wall_mask & ~pass_mask & land
    pass_apply = pass_mask & land

    n_wall = int(wall_apply.sum())
    n_pass = int(pass_apply.sum())
    if n_wall == 0 and n_pass == 0:
        return 0, 0

    # 1) 墙: 高度抬到 WALL_H, 边缘 FEATHER 像素羽化
    if n_wall > 0:
        dist_in = distance_transform_edt(wall_apply).astype(np.float32)
        w = np.minimum(dist_in / FEATHER, 1.0)
        target = np.full_like(height, WALL_H, dtype=np.float32)
        new_h = height.astype(np.float32) * (1 - w) + target * w
        # 仅在 wall_apply 内应用, 且只能抬高不能降低 (保留比墙更高的原始像素)
        height[wall_apply] = np.maximum(
            height[wall_apply],
            new_h[wall_apply].astype(np.uint8),
        )
        terrain[wall_apply] = palette

    # 2) 通道: 高度降到 PASS_H, 羽化
    if n_pass > 0:
        dist_in = distance_transform_edt(pass_apply).astype(np.float32)
        w = np.minimum(dist_in / FEATHER, 1.0)
        target = np.full_like(height, PASS_H, dtype=np.float32)
        new_h = height.astype(np.float32) * (1 - w) + target * w
        # 通道内, 高的像素降下来, 本来就低的保留
        height[pass_apply] = np.minimum(
            height[pass_apply],
            new_h[pass_apply].astype(np.uint8),
        )
        # 通道地形: 山地变丘陵, 雪山变山地
        terr_in_pass = terrain[pass_apply]
        was_snow = np.isin(terr_in_pass, [16, 19, 31])
        was_mtn = np.isin(terr_in_pass, [6, 10, 11, 18, 20, 27])
        new_terr = terr_in_pass.copy()
        new_terr[was_snow] = 6
        new_terr[was_mtn] = 17
        terrain[pass_apply] = new_terr

    # 守底线
    np.maximum(height, SEA_LEVEL + 1, out=height, where=land)
    return n_wall, n_pass


def main():
    if not os.path.exists(BACKUP_PATH):
        shutil.copy2(PROJECT_PATH, BACKUP_PATH)
        print(f"Backup created: {BACKUP_PATH}")
    else:
        print(f"Backup exists: {BACKUP_PATH}")

    entries = {}
    with ZipFile(PROJECT_PATH, "r") as zf:
        for name in zf.namelist():
            entries[name] = zf.read(name)

    tile = np.load(BytesIO(entries["tile_map.npy"])).copy()
    terrain = np.load(BytesIO(entries["terrain_map.npy"])).copy()
    height = np.load(BytesIO(entries["height_map.npy"])).copy()

    for w in WALLS:
        n_wall, n_pass = apply_wall(
            tile, terrain, height,
            wall_bbox=w["wall_bbox"],
            pass_bbox=w["pass_bbox"],
            palette=w["palette"],
        )
        print(f"  {w['name']}: 墙 {n_wall:,d} px, 通道 {n_pass:,d} px")

    entries["tile_map.npy"] = _to_bytes(tile)
    entries["terrain_map.npy"] = _to_bytes(terrain)
    entries["height_map.npy"] = _to_bytes(height)

    tmp = PROJECT_PATH + ".tmp"
    with ZipFile(tmp, "w", ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    shutil.move(tmp, PROJECT_PATH)
    print(f"\nSaved: {PROJECT_PATH}")


def _to_bytes(arr):
    buf = BytesIO()
    np.save(buf, arr)
    return buf.getvalue()


if __name__ == "__main__":
    main()
