"""province feature 页面 — 独立 QWidget, 不依赖 ToolPanel.

默认点击 = 查看省份数据
合并/扩张 需要手动开启，操作完自动关闭回到查看模式。
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel,
)

from ui.styles import (
    make_section as _make_section,
    _DIM, _ACCENT, _SECTION_STYLE, _LABEL_STYLE, _DIM_LABEL_STYLE,
    _PRIMARY_BTN_STYLE, _SECONDARY_BTN_STYLE,
)
from ui.i18n import tr

# 模式激活时的按钮样式（醒目橙色）
_ACTIVE_MODE_BTN_STYLE = """
    QPushButton {
        background: #e67e22;
        border: 2px solid #f39c12;
        color: white;
        padding: 7px 12px;
        font-size: 13px;
        font-weight: bold;
        border-radius: 5px;
    }
    QPushButton:hover {
        background: #f39c12;
    }
"""

# 模式激活时的提示样式（橙色背景）
_ACTIVE_HINT_STYLE = """
    color: white;
    font-size: 13px;
    font-weight: bold;
    padding: 10px;
    background: rgba(230, 126, 34, 0.25);
    border: 1px solid rgba(230, 126, 34, 0.5);
    border-radius: 4px;
"""

_NORMAL_HINT_STYLE = f"color: {_DIM}; font-size: 12px; padding: 8px;"




class ProvincePage(QWidget):
    """省份编辑页面."""

    # 输出信号
    split_mode_toggled = pyqtSignal(bool)
    lasso_province_toggled = pyqtSignal(bool)
    merge_mode_toggled = pyqtSignal(bool)
    regen_mode_toggled = pyqtSignal(bool)
    regen_execute_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)

        # 提示 (动态更新)
        self._province_hint = QLabel(tr("province_hint_default"))
        self._province_hint.setStyleSheet(f"color: {_DIM}; font-size: 12px; padding: 8px;")
        self._province_hint.setWordWrap(True)
        lay.addWidget(self._province_hint)

        # ── 省份信息 ──
        info_box = _make_section(tr("province_section_info"))
        il = info_box.layout()

        self._prov_labels: dict[str, QLabel] = {}
        for key, display in [
            ("id", tr("province_info_id")),
            ("type", tr("province_info_type")),
            ("terrain", tr("province_info_terrain")),
            ("pixels", tr("province_info_pixels")),
            ("coastal", tr("province_info_coastal")),
        ]:
            row = QHBoxLayout()
            name_lbl = QLabel(f"{display}:")
            name_lbl.setStyleSheet(_LABEL_STYLE)
            val_lbl = QLabel("—")
            val_lbl.setStyleSheet(_DIM_LABEL_STYLE)
            val_lbl.setAlignment(Qt.AlignRight)
            row.addWidget(name_lbl)
            row.addStretch()
            row.addWidget(val_lbl)
            il.addLayout(row)
            self._prov_labels[key] = val_lbl

        lay.addWidget(info_box)

        # ── 省份统计 ──
        self._stats_label = QLabel()
        self._stats_label.setWordWrap(True)
        self._stats_label.setStyleSheet(f"color: {_DIM}; font-size: 12px; padding: 4px 8px;")
        lay.addWidget(self._stats_label)

        # ── 工具按钮 ──
        tools_box = _make_section(tr("province_section_tools"))

        # 合并按钮 (toggle)
        self._merge_btn = QPushButton(tr("province_btn_merge"))
        self._merge_btn.setCheckable(True)
        self._merge_btn.setStyleSheet(_SECONDARY_BTN_STYLE)
        self._merge_btn.setToolTip(tr("province_btn_merge_tip"))
        tools_box.layout().addWidget(self._merge_btn)

        # 扩张按钮 (toggle)
        self._expand_btn = QPushButton(tr("province_btn_expand"))
        self._expand_btn.setCheckable(True)
        self._expand_btn.setStyleSheet(_SECONDARY_BTN_STYLE)
        self._expand_btn.setToolTip(tr("province_btn_expand_tip"))
        tools_box.layout().addWidget(self._expand_btn)

        # 切割按钮 (toggle)
        self._split_btn = QPushButton(tr("province_btn_split"))
        self._split_btn.setCheckable(True)
        self._split_btn.setStyleSheet(_SECONDARY_BTN_STYLE)
        self._split_btn.setToolTip(tr("province_btn_split_tip"))
        tools_box.layout().addWidget(self._split_btn)

        lay.addWidget(tools_box)

        # ── 增量生成 ──
        regen_box = _make_section(tr("province_section_regen"))

        self._regen_btn = QPushButton(tr("province_btn_select_area"))
        self._regen_btn.setCheckable(True)
        self._regen_btn.setStyleSheet(_SECONDARY_BTN_STYLE)
        self._regen_btn.setToolTip(tr("province_btn_select_area_tip"))
        regen_box.layout().addWidget(self._regen_btn)

        self._regen_exec_btn = QPushButton(tr("province_btn_regen_exec"))
        self._regen_exec_btn.setStyleSheet(_PRIMARY_BTN_STYLE)
        self._regen_exec_btn.setToolTip(tr("province_btn_regen_exec_tip"))
        regen_box.layout().addWidget(self._regen_exec_btn)

        lay.addWidget(regen_box)

        # ── 信号连接 ──
        self._merge_btn.toggled.connect(self._on_merge_toggled)
        self._expand_btn.toggled.connect(self._on_expand_toggled)
        self._split_btn.toggled.connect(self._on_split_toggled)
        self._regen_btn.toggled.connect(self._on_regen_toggled)
        self._regen_exec_btn.clicked.connect(self.regen_execute_requested.emit)

        lay.addStretch()

    # ── 槽函数 ──
    def _clear_other_modes(self, *keep: QPushButton) -> None:
        """关闭除 keep 之外的所有模式按钮。"""
        for btn in (self._merge_btn, self._expand_btn, self._split_btn, self._regen_btn):
            if btn not in keep and btn.isChecked():
                btn.setChecked(False)

    def _on_merge_toggled(self, on: bool) -> None:
        if on:
            self._clear_other_modes(self._merge_btn)
        self.merge_mode_toggled.emit(on)
        self._update_mode_visuals()

    def _on_expand_toggled(self, on: bool) -> None:
        if on:
            self._clear_other_modes(self._expand_btn)
        self.lasso_province_toggled.emit(on)
        self._update_mode_visuals()

    def _on_split_toggled(self, on: bool) -> None:
        if on:
            self._clear_other_modes(self._split_btn)
        self.split_mode_toggled.emit(on)
        self._update_mode_visuals()

    def _on_regen_toggled(self, on: bool) -> None:
        if on:
            self._clear_other_modes(self._regen_btn)
        self.regen_mode_toggled.emit(on)
        self._update_mode_visuals()

    def _update_mode_visuals(self) -> None:
        """根据当前激活模式更新按钮样式和提示条。"""
        merging = self._merge_btn.isChecked()
        expanding = self._expand_btn.isChecked()
        splitting = self._split_btn.isChecked()
        regening = self._regen_btn.isChecked()

        # 按钮样式：激活时变橙色
        for btn, active in [
            (self._merge_btn, merging),
            (self._expand_btn, expanding),
            (self._split_btn, splitting),
            (self._regen_btn, regening),
        ]:
            btn.setStyleSheet(_ACTIVE_MODE_BTN_STYLE if active else _SECONDARY_BTN_STYLE)

        # 提示条
        if merging:
            self._province_hint.setText(tr("province_hint_merge"))
            self._province_hint.setStyleSheet(_ACTIVE_HINT_STYLE)
        elif expanding:
            self._province_hint.setText(tr("province_hint_expand"))
            self._province_hint.setStyleSheet(_ACTIVE_HINT_STYLE)
        elif splitting:
            self._province_hint.setText(tr("province_hint_split"))
            self._province_hint.setStyleSheet(_ACTIVE_HINT_STYLE)
        elif regening:
            self._province_hint.setText(tr("province_hint_regen"))
            self._province_hint.setStyleSheet(_ACTIVE_HINT_STYLE)
        else:
            self._province_hint.setText(tr("province_hint_default"))
            self._province_hint.setStyleSheet(_NORMAL_HINT_STYLE)

    # ── 公共更新方法 ──
    def update_province_info(
        self, pid: int, ptype: str, terrain: str, pixels: int, coastal: bool
    ) -> None:
        """更新省份信息面板"""
        self._prov_labels["id"].setText(str(pid))
        self._prov_labels["type"].setText(ptype)
        self._prov_labels["terrain"].setText(terrain)
        self._prov_labels["pixels"].setText(str(pixels))
        self._prov_labels["coastal"].setText(tr("province_coastal_yes") if coastal else tr("province_coastal_no"))

    def update_province_gaps(self, gap_ids: list[int]) -> None:
        """更新省份 ID 空洞提示。"""
        if not gap_ids:
            self._stats_label.setText("")
            self._stats_label.setStyleSheet(f"color: {_DIM}; font-size: 12px; padding: 4px 8px;")
            return

        if len(gap_ids) <= 10:
            ids_str = ", ".join(str(i) for i in gap_ids)
        else:
            ids_str = ", ".join(str(i) for i in gap_ids[:10]) + f" ... 共 {len(gap_ids)} 个"

        self._stats_label.setText(
            f"缺失省份 ID: {ids_str}\n需要用切割或增量生成补回"
        )
        self._stats_label.setStyleSheet(
            "color: #f59e0b; font-size: 12px; font-weight: bold; padding: 8px;"
            " background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.3);"
            " border-radius: 4px;"
        )
