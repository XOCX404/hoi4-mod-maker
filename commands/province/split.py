"""
SplitProvinceCommand — 拆分省份。

将指定像素从原省份分配给新省份 ID。
"""

from __future__ import annotations

import numpy as np

from commands.base import Command
from domain.map_data import MapData


class SplitProvinceCommand(Command):
    """拆分省份：将 split_pixels 从 pid 分配给 new_pid，并修复连通性。"""

    label = "拆分省份"

    def __init__(
        self,
        map_data: MapData,
        pid: int,
        new_pid: int,
        split_pixels: np.ndarray,
    ) -> None:
        self._map_data = map_data
        self._pid = pid
        self._new_pid = new_pid
        self._split_pixels = split_pixels.copy()
        # undo 用：记录所有被改动的像素的原始值
        self._snapshot: np.ndarray | None = None

    def execute(self) -> None:
        """分割 + 修复连通性。"""
        pm = self._map_data.province_map
        # 快照原始状态（只记录会被修改的区域）
        affected = self._split_pixels | (pm == self._pid) | (pm == self._new_pid)
        self._snapshot = pm.copy()

        # 分割
        pm[self._split_pixels] = self._new_pid

        # 修复连通性：如果切出多个碎块，小块归另一方
        self._fix_connectivity(pm, self._pid, self._new_pid)
        self._fix_connectivity(pm, self._new_pid, self._pid)

    def undo(self) -> None:
        """恢复到分割前的完整快照。"""
        if self._snapshot is not None:
            # 只恢复两个省份涉及的像素
            mask = (self._snapshot == self._pid) | (self._snapshot == self._new_pid) | \
                   (self._map_data.province_map == self._pid) | (self._map_data.province_map == self._new_pid)
            self._map_data.province_map[mask] = self._snapshot[mask]

    @staticmethod
    def _fix_connectivity(pm: np.ndarray, pid: int, other_pid: int) -> None:
        """如果 pid 有多个连通分量，保留最大的，小的归 other_pid。"""
        from scipy.ndimage import label as _label
        mask = pm == pid
        labeled, n_comp = _label(mask)
        if n_comp <= 1:
            return
        sizes = [(int(np.sum(labeled == c)), c) for c in range(1, n_comp + 1)]
        sizes.sort(reverse=True)
        for _, c in sizes[1:]:
            pm[labeled == c] = other_pid
