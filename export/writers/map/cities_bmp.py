"""
map/cities.bmp 写入器.

HOI4 用 cities.bmp 决定城市 3D 模型分布. 8-bit indexed BMP.
扫描 terrain_map 中 urban terrain (palette index 13, spawn_city=yes),
在对应位置标记城市. 无 terrain_map 时生成全黑 (无城市).

参考: Map modding.txt §Cities
"""

from __future__ import annotations

import os
import struct

import numpy as np

from data.constants import MAP_WIDTH, MAP_HEIGHT


# terrain.bmp 中 spawn_city=yes 的调色板索引
_URBAN_PALETTE_INDEX = 13


def write_cities_bmp(output_dir: str,
                     terrain_map: np.ndarray | None = None) -> None:
    """生成 map/cities.bmp（全尺寸，和 provinces.bmp 一样大）。
    vanilla cities.bmp 就是全尺寸 5632x2048，不是 1/4。"""
    d = os.path.join(output_dir, "map")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "cities.bmp")

    from data.constants import MAP_WIDTH, MAP_HEIGHT
    w, h = MAP_WIDTH, MAP_HEIGHT

    if terrain_map is not None:
        # 直接在全尺寸上标记 urban 像素
        data = np.zeros((h, w), dtype=np.uint8)
        src_h, src_w = terrain_map.shape
        rh, rw = min(h, src_h), min(w, src_w)
        data[:rh, :rw] = (terrain_map[:rh, :rw] == _URBAN_PALETTE_INDEX).astype(np.uint8) * 15
    else:
        data = np.zeros((h, w), dtype=np.uint8)

    _write_8bit_bmp(path, data, w, h)


def _write_8bit_bmp(path: str, data: np.ndarray,
                    w: int, h: int) -> None:
    """写 8-bit indexed BMP 文件 (bottom-up)."""
    row_pad = (4 - w % 4) % 4
    padded_row = w + row_pad

    palette_size = 256 * 4
    pixel_size = padded_row * h
    header_size = 14 + 40 + palette_size
    file_size = header_size + pixel_size

    with open(path, "wb") as f:
        # BMP header
        f.write(b"BM")
        f.write(struct.pack("<I", file_size))
        f.write(struct.pack("<HH", 0, 0))
        f.write(struct.pack("<I", header_size))

        # DIB header
        f.write(struct.pack("<I", 40))
        f.write(struct.pack("<i", w))
        f.write(struct.pack("<i", h))  # positive = bottom-up
        f.write(struct.pack("<HH", 1, 8))
        f.write(struct.pack("<I", 0))
        f.write(struct.pack("<I", pixel_size))
        f.write(struct.pack("<ii", 2835, 2835))
        f.write(struct.pack("<II", 256, 0))

        # Palette — 必须是**真正的**调色板（非 identity grayscale），
        # 否则部分解析器会把 BMP 当作灰度 L 模式读取，8-bit 像素值被当高度差，
        # 调色板索引失效 → HOI4 读到异常城市类型 → EXCEPTION_INT_DIVIDE_BY_ZERO。
        # HOI4 实际只读 index 0 / 1 / 2 / 3 / 15，其余填任意非对角色。
        _CITIES_PALETTE = {
            0: (0, 0, 0),        # 无城市
            1: (150, 150, 150),  # 普通城市
            2: (180, 140, 80),   # 沙漠城市
            3: (120, 90, 50),    # 深色城市
            15: (200, 200, 200), # 沙漠城市 (variant)
        }
        for i in range(256):
            if i in _CITIES_PALETTE:
                r, g, b = _CITIES_PALETTE[i]
            else:
                # 其他索引填一个和 identity grayscale 明显不同的色，防止解析器降级
                r, g, b = (i, (i * 131) & 0xFF, (i * 239) & 0xFF)
            f.write(struct.pack("BBBB", b, g, r, 0))  # BMP palette = BGRA

        # Pixel data (bottom-up)
        pad = b"\x00" * row_pad
        for row_idx in range(h - 1, -1, -1):
            f.write(data[row_idx].tobytes())
            if row_pad:
                f.write(pad)
