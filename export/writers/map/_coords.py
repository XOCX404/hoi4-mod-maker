"""省份坐标计算工具 — buildings.txt 和 positions.txt 共用。"""
import numpy as np


def safe_coord(pid, province_map, pid_count, sum_x, sum_y):
    """返回保证在该省份像素内部（非边缘）的坐标 (cx, cy)。
    先试质心，如果质心飘到隔壁省份就回退到省份的几何中心像素。
    HOI4 对边缘像素的坐标匹配不稳定，必须用内部像素。"""
    cx = sum_x[pid] / pid_count[pid]
    cy = sum_y[pid] / pid_count[pid]
    icy, icx = int(round(cy)), int(round(cx))
    h, w = province_map.shape
    if 0 <= icy < h and 0 <= icx < w and province_map[icy, icx] == pid:
        return cx, cy
    # 质心不在省份内 → 找几何中心（median of y, median of x）
    ys, xs = np.where(province_map == pid)
    if len(ys) == 0:
        return cx, cy
    my = float(np.median(ys))
    mx = float(np.median(xs))
    imy, imx = int(round(my)), int(round(mx))
    if 0 <= imy < h and 0 <= imx < w and province_map[imy, imx] == pid:
        return mx, my
    # 中位数也不行（非凸省份），取最靠近质心的省份内像素
    dist = (ys.astype(float) - cy)**2 + (xs.astype(float) - cx)**2
    best = np.argmin(dist)
    return float(xs[best]), float(ys[best])
