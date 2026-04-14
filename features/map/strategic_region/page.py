"""战略区域 page — 独立 QWidget, 不依赖 ToolPanel.

功能: region 列表 + 自动生成 + 编辑 (名字/weather/naval_terrain) + 拾取省份.
"""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QListWidget, QComboBox, QScrollArea,
)

from domain.managers.strategic_region import PRESET_LABELS

from ui.styles import (
    _DIM_LABEL_STYLE, _PRIMARY_BTN_STYLE,
    _LIST_STYLE, _COMBOBOX_STYLE, _LINEEDIT_STYLE,
)


class StrategicRegionPage(QWidget):
    """战略区域页面."""

    # 输出信号
    strategic_region_auto_requested = pyqtSignal()
    strategic_region_selected = pyqtSignal(int)
    strategic_region_new_requested = pyqtSignal()
    strategic_region_delete_requested = pyqtSignal()
    strategic_region_name_changed = pyqtSignal(str)
    strategic_region_weather_changed = pyqtSignal(str)
    strategic_region_naval_changed = pyqtSignal(str)
    strategic_region_pick_toggled = pyqtSignal(bool)
    create_from_states_toggled = pyqtSignal(bool)
    create_from_states_confirmed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        tip = QLabel("战略区域: 省份分组 + 天气 + 海军地形.\n"
                     "建议先点'自动生成'按 State 创建初始分组，\n"
                     "再手动调整。每个区域可设天气和海军地形类型.\n"
                     "用拾取模式点省份可移入选中的区域.")
        tip.setWordWrap(True)
        tip.setStyleSheet(_DIM_LABEL_STYLE)
        lay.addWidget(tip)

        auto_btn = QPushButton("自动生成 (按 State 分组)")
        auto_btn.setStyleSheet(_PRIMARY_BTN_STYLE)
        auto_btn.clicked.connect(lambda: self.strategic_region_auto_requested.emit())
        lay.addWidget(auto_btn)

        # 从州创建
        self._from_states_btn = QPushButton("选择州 → 创建战略区域")
        self._from_states_btn.setCheckable(True)
        self._from_states_btn.setStyleSheet(_PRIMARY_BTN_STYLE)
        self._from_states_btn.setToolTip("开启后点击地图选择多个州，然后点确认合并为一个战略区域")
        self._from_states_btn.toggled.connect(self.create_from_states_toggled.emit)
        lay.addWidget(self._from_states_btn)

        self._from_states_confirm_btn = QPushButton("确认创建战略区域")
        self._from_states_confirm_btn.setStyleSheet(
            "QPushButton { background: #22c55e; color: white; padding: 6px;"
            " border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background: #2ad66a; }"
        )
        self._from_states_confirm_btn.clicked.connect(self.create_from_states_confirmed.emit)
        lay.addWidget(self._from_states_confirm_btn)

        # Region 列表
        self._sr_list = QListWidget()
        self._sr_list.setStyleSheet(_LIST_STYLE)
        self._sr_list.setMaximumHeight(150)
        self._sr_list.currentRowChanged.connect(
            lambda row: self.strategic_region_selected.emit(row)
        )
        lay.addWidget(self._sr_list)

        btn_row = QHBoxLayout()
        new_btn = QPushButton("新建")
        new_btn.clicked.connect(lambda: self.strategic_region_new_requested.emit())
        del_btn = QPushButton("删除")
        del_btn.clicked.connect(lambda: self.strategic_region_delete_requested.emit())
        btn_row.addWidget(new_btn)
        btn_row.addWidget(del_btn)
        lay.addLayout(btn_row)

        # 编辑字段
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("名字:"))
        self._sr_name_edit = QLineEdit()
        self._sr_name_edit.setStyleSheet(_LINEEDIT_STYLE)
        self._sr_name_edit.editingFinished.connect(
            lambda: self.strategic_region_name_changed.emit(self._sr_name_edit.text())
        )
        name_row.addWidget(self._sr_name_edit)
        lay.addLayout(name_row)

        weather_row = QHBoxLayout()
        weather_row.addWidget(QLabel("天气:"))
        self._sr_weather_combo = QComboBox()
        self._sr_weather_combo.setStyleSheet(_COMBOBOX_STYLE)
        for key, label in PRESET_LABELS.items():
            self._sr_weather_combo.addItem(label, key)
        self._sr_weather_combo.currentIndexChanged.connect(
            lambda idx: self.strategic_region_weather_changed.emit(
                self._sr_weather_combo.currentData() or "temperate"
            )
        )
        weather_row.addWidget(self._sr_weather_combo)
        lay.addLayout(weather_row)

        naval_row = QHBoxLayout()
        naval_row.addWidget(QLabel("Naval:"))
        self._sr_naval_combo = QComboBox()
        self._sr_naval_combo.setStyleSheet(_COMBOBOX_STYLE)
        self._sr_naval_combo.addItem("(无)", "")
        for nt in ("ocean", "deep_ocean", "shallow_sea"):
            self._sr_naval_combo.addItem(nt, nt)
        self._sr_naval_combo.currentIndexChanged.connect(
            lambda idx: self.strategic_region_naval_changed.emit(
                self._sr_naval_combo.currentData() or ""
            )
        )
        naval_row.addWidget(self._sr_naval_combo)
        lay.addLayout(naval_row)

        self._sr_prov_count = QLabel("省份: 0")
        self._sr_prov_count.setStyleSheet(_DIM_LABEL_STYLE)
        lay.addWidget(self._sr_prov_count)

        self._sr_pick_btn = QPushButton("开始拾取省份")
        self._sr_pick_btn.setCheckable(True)
        self._sr_pick_btn.setStyleSheet(_PRIMARY_BTN_STYLE)
        self._sr_pick_btn.toggled.connect(
            lambda on: self.strategic_region_pick_toggled.emit(on)
        )
        lay.addWidget(self._sr_pick_btn)

        lay.addStretch(1)
        scroll.setWidget(page)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)
