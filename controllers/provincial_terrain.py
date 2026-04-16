"""ProvincialTerrainController — 只改 province 的 gameplay terrain（不动视觉/高度）。

复用 PaintTerrainCommand（已支持只传 provincial_terrain_changes）。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from controllers.base import BaseController
from commands.map.paint_terrain import PaintTerrainCommand

if TYPE_CHECKING:
    from model.project import Project
    from commands.history import CommandHistory


class ProvincialTerrainController(BaseController):
    """点 province → 改它的 provincial_terrain dict（不动 terrain.bmp / height_map）。

    默认是查看模式：点 province 只显示信息（走 app_controller 的省份查询）。
    开启分配模式后：点 province 改地形。
    """

    def __init__(self, project: "Project", command_history: "CommandHistory") -> None:
        super().__init__(project, command_history)
        self.current_type: str = "plains"
        self.assign_mode: bool = False  # 默认查看模式

    def activate(self) -> None:
        self._emit_status("属性地形：查看模式（勾选「分配模式」才能改）")

    def deactivate(self) -> None:
        pass

    def set_type(self, type_name: str) -> None:
        self.current_type = type_name
        if self.assign_mode:
            self._emit_status(f"已选 {type_name}，点击省份生效")
        else:
            self._emit_status(f"已选 {type_name}（请勾选「分配模式」才能改）")

    def set_assign_mode(self, enabled: bool) -> None:
        self.assign_mode = enabled
        if enabled:
            self._emit_status(f"✏️ 分配模式开启：点击省份将其改为 {self.current_type}")
        else:
            self._emit_status("👁 查看模式：点 province 只看信息")

    def on_province_clicked(self, pid: int) -> None:
        if pid <= 0:
            return
        # 查看模式：不改数据，让 app_controller 的省份信息显示处理即可
        if not self.assign_mode:
            return

        map_data = self.project.map_data
        province_map = map_data.province_map
        tile_map = map_data.tile_map

        # 海洋/湖泊省份不能改
        from data.constants import TILE_SEA, TILE_LAKE
        ys, xs = np.where(province_map == pid)
        if len(ys) == 0:
            return
        tile_val = int(tile_map[ys[0], xs[0]])
        if tile_val in (TILE_SEA, TILE_LAKE):
            self._emit_status(f"省份 {pid} 是海洋/湖泊，不能改地形")
            return

        # 复用 PaintTerrainCommand，只传 provincial_terrain_changes
        cmd = PaintTerrainCommand(
            map_data,
            terrain_changes={},
            height_changes=None,
            provincial_terrain_changes={pid: self.current_type},
        )
        self.history.execute(cmd)
        self.project.mark_dirty()
        self._emit_render(full=True)
        self._emit_status(f"省份 {pid} 属性地形 → {self.current_type}")
