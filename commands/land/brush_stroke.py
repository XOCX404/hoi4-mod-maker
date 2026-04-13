"""
BrushStrokeCommand — 画笔一次 stroke 的快照式撤销。

包装 UndoManager 的 zlib 压缩快照为 Command 接口，
让画笔操作也能通过 CommandHistory 统一管理。
"""
from __future__ import annotations

import zlib
import numpy as np

from commands.base import Command


class BrushStrokeCommand(Command):
    """画笔一次 stroke 的可撤销命令。

    存储操作前后的数组快照（zlib 压缩），
    只存有变化的图层。
    """

    label = "画笔绘制"

    def __init__(
        self,
        description: str,
        before_snapshots: dict[str, tuple[bytes, tuple]],
        after_snapshots: dict[str, tuple[bytes, tuple]],
    ) -> None:
        """
        参数:
            description: 操作描述
            before_snapshots: 操作前快照 {name: (compressed_data, (shape, dtype))}
            after_snapshots: 操作后快照 {name: (compressed_data, (shape, dtype))}
        """
        self.label = description
        self._before = before_snapshots
        self._after = after_snapshots
        # 目标数组引用（execute 时设置）
        self._target_arrays: dict[str, np.ndarray] = {}

    def set_target_arrays(self, arrays: dict[str, np.ndarray]) -> None:
        """设置撤销/重做时要操作的目标数组引用。"""
        self._target_arrays = arrays

    def execute(self) -> None:
        """恢复到操作后的状态（用于 redo）。"""
        for name, (compressed, (shape, dtype)) in self._after.items():
            if name in self._target_arrays:
                data = zlib.decompress(compressed)
                restored = np.frombuffer(data, dtype=dtype).reshape(shape)
                self._target_arrays[name][:] = restored

    def undo(self) -> None:
        """恢复到操作前的状态。"""
        for name, (compressed, (shape, dtype)) in self._before.items():
            if name in self._target_arrays:
                data = zlib.decompress(compressed)
                restored = np.frombuffer(data, dtype=dtype).reshape(shape)
                self._target_arrays[name][:] = restored

    @staticmethod
    def snapshot_arrays(arrays: dict[str, np.ndarray]) -> dict[str, tuple[bytes, tuple]]:
        """对数组进行 zlib 压缩快照。"""
        result = {}
        for name, arr in arrays.items():
            compressed = zlib.compress(arr.tobytes(), level=1)
            result[name] = (compressed, (arr.shape, arr.dtype))
        return result

    @staticmethod
    def has_changes(
        before: dict[str, tuple[bytes, tuple]],
        after_arrays: dict[str, np.ndarray],
    ) -> bool:
        """检查操作前后是否有实际变化。"""
        for name, (compressed, (shape, dtype)) in before.items():
            if name in after_arrays:
                old_data = zlib.decompress(compressed)
                old_arr = np.frombuffer(old_data, dtype=dtype).reshape(shape)
                if not np.array_equal(old_arr, after_arrays[name]):
                    return True
        return False
