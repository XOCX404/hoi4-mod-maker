"""ApplicationController — 应用级调度器。

从 MainWindow 抽出的业务逻辑：
- 模式切换副作用
- 省份信息计算
- State/Country 颜色图刷新
- VP 数据收集
- 列表刷新
- 撤销/重做管理

MainWindow 只做 UI 构建和信号路由，所有逻辑委托到这里。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from model.project import Project
    from model.events import EventBus
    from commands.history import CommandHistory
    from views.canvas.widget import MapCanvas
    from ui.tool_panel import ToolPanel

from data.constants import TILE_LAND, TILE_SEA, TILE_LAKE
from commands.land.brush_stroke import BrushStrokeCommand


class ApplicationController:
    """应用级调度器 — 协调 controllers、canvas、tool_panel。"""

    def __init__(
        self,
        project: "Project",
        canvas: "MapCanvas",
        tool_panel: "ToolPanel",
        cmd_history: "CommandHistory",
        controllers: dict[str, Any],
        undo_mgr: Any,
    ) -> None:
        self._project = project
        self._canvas = canvas
        self._panel = tool_panel
        self._cmd_history = cmd_history
        self._controllers = controllers
        self._undo_mgr = undo_mgr
        self._event_bus: "EventBus" = project.event_bus
        self._current_controller = None
        self._province_info_cache: dict[int, dict] = {}

        # 画笔 stroke 状态（用于 BrushStrokeCommand）
        self._stroke_before: dict | None = None

        # 订阅 EventBus 事件
        self._subscribe_events()

    # ═══════════════════════ EventBus 订阅 ═══════════════════

    def _subscribe_events(self) -> None:
        bus = self._event_bus
        bus.subscribe("request_render", self._on_render)
        bus.subscribe("province_count_changed", self._on_province_count)
        bus.subscribe("state_changed", self._on_state_changed)
        bus.subscribe("country_changed", self._on_country_changed)
        bus.subscribe("vp_changed", self._on_vp_changed)
        bus.subscribe("province_map_regenerated", self._on_province_regen)

    # ═══════════════════════ 模式切换 ═══════════════════════

    # 模式名称映射
    _MODE_NAMES = {
        "land": "大陆", "province": "省份", "terrain": "地形",
        "height": "高度", "state": "State", "country": "国家",
        "river": "河流", "continent": "大洲", "logistics": "后勤",
        "strategic_region": "战略区", "colormap": "总览贴图",
        "default_map": "地图配置",
    }

    def on_mode_changed(self, mode: str) -> str:
        """模式切换：停用旧 controller、激活新 controller、刷新相关数据。
        返回模式中文名。"""
        if self._current_controller is not None:
            self._current_controller.deactivate()

        self._canvas.cleanup_mode_state()
        self._canvas.display_mode = mode

        self._current_controller = self._controllers.get(mode)
        if self._current_controller is not None:
            self._current_controller.activate()

        # 按模式刷新颜色图
        if mode == "state":
            self._refresh_state_colors()
        elif mode == "country":
            self._refresh_country_colors()

        return self._MODE_NAMES.get(mode, mode)

    @property
    def current_controller(self):
        return self._current_controller

    # ═══════════════════════ 省份信息 ═══════════════════════

    def invalidate_province_cache(self) -> None:
        """清除省份信息缓存。"""
        self._province_info_cache.clear()

    def calculate_province_info(self, pid: int) -> dict | None:
        """计算省份信息（类型/地形/像素数/沿海），带缓存。
        返回 dict 或 None。"""
        if pid in self._province_info_cache:
            return self._province_info_cache[pid]

        pm = self._canvas.province_map
        tm = self._canvas.tile_map
        mask = pm == pid
        pixels = int(np.sum(mask))

        ys, xs = np.where(mask)
        if len(ys) == 0:
            return None

        tiles = tm[mask]
        land_n = int(np.sum(tiles == TILE_LAND))
        sea_n = int(np.sum(tiles == TILE_SEA))
        lake_n = int(np.sum(tiles == TILE_LAKE))
        if sea_n >= land_n and sea_n >= lake_n:
            ptype = "海洋"
        elif lake_n >= land_n:
            ptype = "湖泊"
        else:
            ptype = "陆地"

        # 沿海检查
        _adj = False
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            ny = np.clip(ys + dy, 0, tm.shape[0] - 1)
            nx = np.clip(xs + dx, 0, tm.shape[1] - 1)
            if np.any(tm[ny, nx] == TILE_SEA):
                _adj = True
                break
        coastal = _adj and ptype == "陆地"

        from data.terrain_types import GRAPHICAL_TERRAIN_BY_INDEX
        terrain_data = self._canvas.terrain_map[mask]
        if len(terrain_data) > 0:
            terrain_idx = int(np.bincount(terrain_data).argmax())
            gt = GRAPHICAL_TERRAIN_BY_INDEX.get(terrain_idx)
            terrain_name = gt.name_cn if gt else "未知"
        else:
            terrain_name = "未知"

        info = {
            "ptype": ptype, "terrain": terrain_name,
            "pixels": pixels, "coastal": coastal,
        }
        self._province_info_cache[pid] = info
        return info

    # ═══════════════════════ State/Country 刷新 ═══════════════

    def _refresh_state_list(self) -> None:
        items = [(sid, s.name) for sid, s in self._project.state_mgr.states.items()]
        self._panel.update_state_list(items)

    def _refresh_state_colors(self) -> None:
        if int(self._canvas.province_map.max()) == 0:
            return
        rgb = self._project.state_mgr.build_state_color_map(self._canvas.province_map)
        self._canvas.set_state_colors(rgb)
        self._refresh_vp_data()

    def _refresh_vp_data(self) -> None:
        vp_dict: dict[int, int] = {}
        for state in self._project.state_mgr.states.values():
            for pid, vp_val in state.victory_points.items():
                if vp_val > 0:
                    vp_dict[pid] = vp_val
        self._canvas.set_vp_data(vp_dict)

    def _refresh_country_list(self) -> None:
        self._panel.update_country_list(self._project.country_mgr.get_country_list())

    def _refresh_country_colors(self) -> None:
        if int(self._canvas.province_map.max()) == 0:
            return
        rgb = self._project.country_mgr.build_country_color_map(
            self._canvas.province_map, self._project.state_mgr
        )
        self._canvas.set_country_colors(rgb)

    def update_province_count(self) -> int:
        """返回当前省份数量。"""
        return int(self._canvas.province_map.max())

    # ═══════════════════════ EventBus 处理器 ═══════════════════

    def _on_render(self, event) -> None:
        full = event.data.get("full", False)
        bbox = event.data.get("bbox")
        self._canvas._rebind_aliases()
        if full or bbox is None:
            self._canvas._full_render()
        else:
            x0, y0, x1, y1 = bbox
            self._canvas._partial_render(x0, y0, x1, y1)

    def _on_province_count(self, event) -> None:
        # 由 MainWindow 处理状态栏更新
        pass

    def _on_state_changed(self, event) -> None:
        """State 数据变化 → 刷新 UI。"""
        action = event.data.get("action", "")
        if action == "refresh":
            self.invalidate_province_cache()
            self._refresh_state_list()
            self._refresh_state_colors()
        elif action == "modified":
            sid = event.data.get("state_id", 0)
            state = self._project.state_mgr.get_state(sid)
            if state:
                self._panel.update_state_info(
                    state.name, state.manpower, state.category
                )
            prop = event.data.get("property", "")
            if prop in ("", "provinces", "assign"):
                self._refresh_state_colors()
        elif action == "selected":
            sid = event.data.get("state_id", 0)
            state = self._project.state_mgr.get_state(sid)
            if state:
                self._panel.update_state_info(
                    state.name, state.manpower, state.category
                )

    def _on_country_changed(self, event) -> None:
        """Country 数据变化 → 刷新 UI。"""
        action = event.data.get("action", "")
        tag = event.data.get("tag", "")
        if action in ("refresh", "created", "modified"):
            self._refresh_country_list()
            self._refresh_country_colors()
            if tag:
                self._update_country_info_panel(tag)
        elif action == "selected" and tag:
            self._update_country_info_panel(tag)

    def _update_country_info_panel(self, tag: str) -> None:
        country = self._project.country_mgr.get_country(tag)
        if country:
            capital_name = f"省份 {country.capital}" if country.capital > 0 else ""
            self._panel.update_country_info(
                country.tag, country.name, country.ruling_party,
                country.color, capital_name,
            )

    def _on_vp_changed(self, event) -> None:
        self._refresh_vp_data()

    def _on_province_regen(self, event) -> None:
        """省份重新生成 → 清除画布颜色缓存、刷新省份缓存。"""
        self.invalidate_province_cache()
        self._canvas._state_color_rgb = None
        self._canvas._country_color_rgb = None

    # ═══════════════════════ 撤销/重做 ═══════════════════════

    def _get_stroke_arrays(self) -> dict[str, np.ndarray]:
        """获取当前模式对应的数组，用于画笔快照。"""
        mode = self._canvas.display_mode
        if mode == "land":
            return {"tile_map": self._canvas.tile_map}
        elif mode == "terrain":
            return {"terrain_map": self._canvas.terrain_map}
        elif mode == "height":
            return {"height_map": self._canvas.height_map}
        elif mode == "province":
            return {"province_map": self._canvas.province_map}
        elif mode == "river":
            return {"river_map": self._canvas.river_map}
        return {}

    def _get_all_arrays(self) -> dict[str, np.ndarray]:
        """获取所有数组引用（撤销/重做时需要）。"""
        return {
            "tile_map": self._canvas.tile_map,
            "province_map": self._canvas.province_map,
            "terrain_map": self._canvas.terrain_map,
            "height_map": self._canvas.height_map,
            "river_map": self._canvas.river_map,
        }

    def on_stroke_started(self) -> None:
        """画笔开始 — 记录操作前快照。"""
        arrays = self._get_stroke_arrays()
        self._stroke_before = BrushStrokeCommand.snapshot_arrays(arrays)

    def on_stroke_ended(self) -> None:
        """画笔结束 — 比较变化，创建 Command 并推入 CommandHistory。"""
        if self._stroke_before is None:
            return
        arrays = self._get_stroke_arrays()
        if BrushStrokeCommand.has_changes(self._stroke_before, arrays):
            after = BrushStrokeCommand.snapshot_arrays(arrays)
            mode = self._canvas.display_mode
            cmd = BrushStrokeCommand(f"{mode} 绘制", self._stroke_before, after)
            cmd.set_target_arrays(self._get_all_arrays())
            # 直接推入栈，不调 execute（因为画笔已经绘制完了）
            self._cmd_history._undo_stack.append(cmd)
            self._cmd_history._redo_stack.clear()
            if len(self._cmd_history._undo_stack) > self._cmd_history._max_size:
                self._cmd_history._undo_stack.pop(0)
            self._cmd_history._notify()
        self._stroke_before = None

    def undo(self) -> str:
        """执行撤销。返回状态消息。"""
        # 如果有未完成的 stroke，先提交
        if self._stroke_before is not None:
            self.on_stroke_ended()

        if not self._cmd_history.can_undo:
            return "没有可撤销的操作"

        # 确保 BrushStrokeCommand 有最新的数组引用
        cmd = self._cmd_history._undo_stack[-1]
        if isinstance(cmd, BrushStrokeCommand):
            cmd.set_target_arrays(self._get_all_arrays())

        self._cmd_history.undo()
        self._canvas.refresh_display()
        return "已撤销"

    def redo(self) -> str:
        """执行重做。返回状态消息。"""
        if self._stroke_before is not None:
            self.on_stroke_ended()

        if not self._cmd_history.can_redo:
            return "没有可重做的操作"

        cmd = self._cmd_history._redo_stack[-1]
        if isinstance(cmd, BrushStrokeCommand):
            cmd.set_target_arrays(self._get_all_arrays())

        self._cmd_history.redo()
        self._canvas.refresh_display()
        return "已重做"

    # ═══════════════════════ 省份点击路由 ═══════════════════

    def on_province_clicked(self, pid: int) -> dict | None:
        """省份被点击：计算信息 + 转发给当前 controller。返回省份信息 dict。"""
        if pid <= 0:
            return None
        info = self.calculate_province_info(pid)
        if self._current_controller is not None:
            self._current_controller.on_province_clicked(pid)
        return info

    def on_province_double_clicked(self, pid: int) -> None:
        if pid <= 0:
            return
        if self._current_controller is not None:
            self._current_controller.on_province_double_clicked(pid)
