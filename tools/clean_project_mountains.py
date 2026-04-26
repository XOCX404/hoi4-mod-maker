"""
一次性脚本：清理 5.hoi4proj 里的散落小山地，保留大山脊。

算法:
1. 连通分量分析 terrain_map 里所有"山地 type"的像素
2. 标记 blob < BIG_BLOB_THRESHOLD 的像素为"散点" → 降级为丘陵 (palette 17)
3. 散点像素的 height_map 拉低到 145 (丘陵 band)
4. Snow 高度 > 225 的极端峰 → 压到 200
5. 找出所有 provincial_terrain='mountain' 但 >70% 像素在散点里的省份 → 降为 hills
6. 保留所有大山脊的像素和属性

保存到 5.hoi4proj (原文件), 原始备份在 5.hoi4proj.bak。
"""
from __future__ import annotations

import json
import os
import sys
import shutil
from collections import Counter
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

import numpy as np
from scipy.ndimage import label

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.terrain_types import PALETTE_TO_TYPE

PROJECT_PATH = os.path.join(
    os.path.expanduser("~"), "Desktop", "欧若拉", "5.hoi4proj"
)
BIG_BLOB_THRESHOLD = 2000   # 像素数 < 此值的山地块被视为"散点"，降级
SNOW_TOP_CAP = 200          # 雪山最高压到此值 (而不是完全降为山地)
SNOW_HEIGHT_CUTOFF = 225    # 只处理 > 此高度的雪山
HILLS_HEIGHT_TARGET = 145   # 散点山地降级后的目标高度


def main() -> None:
    assert os.path.exists(PROJECT_PATH), f"not found: {PROJECT_PATH}"
    print(f"Opening: {PROJECT_PATH}")

    # 读所有条目
    entries: dict[str, bytes] = {}
    with ZipFile(PROJECT_PATH, "r") as zf:
        for name in zf.namelist():
            entries[name] = zf.read(name)

    tm = np.load(BytesIO(entries["terrain_map.npy"]))
    hm = np.load(BytesIO(entries["height_map.npy"]))
    tile = np.load(BytesIO(entries["tile_map.npy"]))
    pm = np.load(BytesIO(entries["province_map.npy"]))
    pt_raw = entries.get("provincial_terrain.json", b"{}").decode("utf-8")
    pt: dict[str, str] = json.loads(pt_raw)

    orig_tm = tm.copy()
    orig_hm = hm.copy()

    land_mask = tile == 1
    n_land = int(land_mask.sum())

    # —— Step 1: 山地连通分量 ——
    mountain_palettes = [
        idx for idx, typ in PALETTE_TO_TYPE.items() if typ == "mountain"
    ]
    mountain_mask = np.isin(tm, mountain_palettes) & land_mask
    labels, n_blobs = label(mountain_mask, structure=np.ones((3, 3), dtype=bool))
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0  # 背景

    # 散点 blob
    small_labels = np.where((sizes > 0) & (sizes < BIG_BLOB_THRESHOLD))[0]
    big_labels = np.where(sizes >= BIG_BLOB_THRESHOLD)[0]
    scatter_mask = np.isin(labels, small_labels)
    big_blob_mask = np.isin(labels, big_labels)

    print(f"Mountain blobs: {n_blobs} total")
    print(f"  big (>= {BIG_BLOB_THRESHOLD} px):  {len(big_labels):>4d}")
    print(f"  small (scatter):               {len(small_labels):>4d}")
    print(f"  scatter pixels: {int(scatter_mask.sum()):,d} "
          f"({scatter_mask.sum() / mountain_mask.sum() * 100:.1f}% of all mountains)")

    # —— Step 2: 散点像素降级为 hills_blend (17), 高度拉到 145 ——
    tm_new = tm.copy()
    hm_new = hm.copy()
    tm_new[scatter_mask] = 17  # hills_blend
    # 高度: 如果原高度 > 145, 压到 145; 否则保持
    hm_sub = hm_new[scatter_mask]
    hm_new[scatter_mask] = np.minimum(hm_sub, HILLS_HEIGHT_TARGET).astype(np.uint8)

    # —— Step 3: Snow 高度顶端压低 ——
    # 只改 height, 不改 terrain (palette 16 保留, 它在大山脊里)
    snow_top_mask = (tm == 16) & (hm > SNOW_HEIGHT_CUTOFF) & land_mask
    hm_new[snow_top_mask] = SNOW_TOP_CAP
    n_snow_capped = int(snow_top_mask.sum())

    # —— Step 4: 属性层 provincial_terrain 降级 ——
    # 找"mountain 类型但 >70% 像素在散点" 的省份
    pt_new: dict[str, str] = dict(pt)
    mountain_pids = [int(pid) for pid, typ in pt.items() if typ == "mountain"]
    total_px = np.bincount(pm.ravel())
    scatter_px = np.bincount(pm[scatter_mask], minlength=total_px.size)
    big_blob_px = np.bincount(pm[big_blob_mask & mountain_mask],
                              minlength=total_px.size)

    downgraded_pids: list[int] = []
    for pid in mountain_pids:
        if pid <= 0 or pid >= total_px.size:
            continue
        total = total_px[pid]
        if total == 0:
            continue
        in_big = big_blob_px[pid]
        # 规则: 如果该省份在大山脊里的像素 < 30% 省份总面积 → 判为"散点省份" → 降级为 hills
        if in_big < 0.30 * total:
            pt_new[str(pid)] = "hills"
            downgraded_pids.append(pid)

    print(f"\nProvince attribute downgrade:")
    print(f"  mountain provinces before: {len(mountain_pids)}")
    print(f"  downgraded to hills:       {len(downgraded_pids)}")
    print(f"  mountain provinces after:  {len(mountain_pids) - len(downgraded_pids)}")
    print(f"\nSnow peaks capped to {SNOW_TOP_CAP}: {n_snow_capped:,d} pixels")

    # 总统计
    new_mountain_type_pixels = int(np.isin(tm_new,
                                           [idx for idx, t in PALETTE_TO_TYPE.items() if t == "mountain"]).sum())
    print(f"\nMountain-type visual pixels:")
    print(f"  before: {int(mountain_mask.sum()):>10,d} ({mountain_mask.sum() / n_land * 100:.2f}%)")
    print(f"  after:  {new_mountain_type_pixels:>10,d} "
          f"({new_mountain_type_pixels / n_land * 100:.2f}%)")

    # —— Step 5: 写回 zip ——
    entries["terrain_map.npy"] = _np_to_bytes(tm_new)
    entries["height_map.npy"] = _np_to_bytes(hm_new)
    entries["provincial_terrain.json"] = json.dumps(
        pt_new, ensure_ascii=False, indent=2
    ).encode("utf-8")

    tmp_path = PROJECT_PATH + ".tmp"
    with ZipFile(tmp_path, "w", ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    shutil.move(tmp_path, PROJECT_PATH)
    print(f"\nSaved: {PROJECT_PATH}")


def _np_to_bytes(arr: np.ndarray) -> bytes:
    buf = BytesIO()
    np.save(buf, arr)
    return buf.getvalue()


if __name__ == "__main__":
    main()
