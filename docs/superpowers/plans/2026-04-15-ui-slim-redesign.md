# UI 减负重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 13 个编辑模式合并为 7 个，每页高级选项折叠，加防误触保护。

**Architecture:** 创建 4 个合并页面（QTabWidget 包裹原有 page），修改 ToolPanel 模式列表和信号转发，在 canvas 加防误触确认。原有 page 文件不修改，只在外层包裹。

**Tech Stack:** Python 3.10, PyQt5 (QTabWidget, QGroupBox 折叠)

---

### Task 1: 创建可折叠分组组件

**Files:**
- Create: `ui/collapsible.py`

- [ ] **Step 1: 创建 CollapsibleSection widget**

```python
# ui/collapsible.py
"""可折叠分组 — 点击标题展开/收起内容。"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSizePolicy
from PyQt5.QtCore import Qt
from ui.styles import _ACCENT, _INPUT_BG, _BORDER, _DIM


class CollapsibleSection(QWidget):
    """可折叠区域：标题按钮 + 内容容器。"""

    def __init__(self, title: str, parent=None, collapsed: bool = True):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._toggle = QPushButton(f"▸ {title}")
        self._toggle.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {_ACCENT};
                font-size: 11px;
                font-weight: bold;
                text-align: left;
                padding: 6px 8px;
            }}
            QPushButton:hover {{
                color: #7c7cff;
            }}
        """)
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.clicked.connect(self._on_toggle)
        lay.addWidget(self._toggle)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(8, 4, 8, 8)
        self._content_layout.setSpacing(6)
        lay.addWidget(self._content)

        self._title = title
        self._collapsed = not collapsed  # _on_toggle will flip it
        self._on_toggle()

    def layout_content(self) -> QVBoxLayout:
        """返回内容区域的 layout，外部往里加控件。"""
        return self._content_layout

    def _on_toggle(self) -> None:
        self._collapsed = not self._collapsed
        self._content.setVisible(not self._collapsed)
        arrow = "▸" if self._collapsed else "▾"
        self._toggle.setText(f"{arrow} {self._title}")
```

- [ ] **Step 2: 验证导入**

Run: `cd hoi4_map_maker && python -c "from ui.collapsible import CollapsibleSection; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add ui/collapsible.py
git commit -m "feat: 可折叠分组组件 CollapsibleSection"
```

---

### Task 2: 创建合并页面 — 地形（高度+地形）

**Files:**
- Create: `features/map/terrain_combined/page.py`
- Create: `features/map/terrain_combined/__init__.py`

- [ ] **Step 1: 创建合并页面**

```python
# features/map/terrain_combined/__init__.py
"""地形合并模式（高度+地形）。"""
```

```python
# features/map/terrain_combined/page.py
"""地形合并页面 — QTabWidget 包裹 HeightPage + TerrainPage。"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from PyQt5.QtCore import pyqtSignal
from ui.i18n import tr


class TerrainCombinedPage(QWidget):
    """地形合并页：标签页切换高度和地形。"""

    # 转发所有子页面信号（height + terrain）
    # Height signals
    height_value_changed = pyqtSignal(int)
    auto_height_requested = pyqtSignal()
    smooth_height_requested = pyqtSignal()
    ridge_mode_toggled = pyqtSignal(bool)
    ridge_peak_changed = pyqtSignal(int)
    ridge_falloff_changed = pyqtSignal(int)
    # Terrain signals
    terrain_index_changed = pyqtSignal(int)
    terrain_brush_mode_changed = pyqtSignal(bool)
    terrain_brush_size_changed = pyqtSignal(int)
    terrain_soft_edge_changed = pyqtSignal(bool)
    auto_terrain_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        from features.map.height.page import HeightPage
        from features.map.terrain.page import TerrainPage

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab { padding: 6px 16px; font-size: 12px; }
            QTabBar::tab:selected { color: white; border-bottom: 2px solid #6c6cf0; }
            QTabBar::tab:!selected { color: #8888a8; }
        """)

        self._height_page = HeightPage()
        self._terrain_page = TerrainPage()
        self._tabs.addTab(self._height_page, tr("tab_height"))
        self._tabs.addTab(self._terrain_page, tr("tab_terrain"))
        lay.addWidget(self._tabs)

        # 转发 height 信号
        self._height_page.height_value_changed.connect(self.height_value_changed)
        self._height_page.auto_height_requested.connect(self.auto_height_requested)
        self._height_page.smooth_height_requested.connect(self.smooth_height_requested)
        self._height_page.ridge_mode_toggled.connect(self.ridge_mode_toggled)
        self._height_page.ridge_peak_changed.connect(self.ridge_peak_changed)
        self._height_page.ridge_falloff_changed.connect(self.ridge_falloff_changed)
        # 转发 terrain 信号
        self._terrain_page.terrain_index_changed.connect(self.terrain_index_changed)
        self._terrain_page.terrain_brush_mode_changed.connect(self.terrain_brush_mode_changed)
        self._terrain_page.terrain_brush_size_changed.connect(self.terrain_brush_size_changed)
        self._terrain_page.terrain_soft_edge_changed.connect(self.terrain_soft_edge_changed)
        self._terrain_page.auto_terrain_requested.connect(self.auto_terrain_requested)
```

- [ ] **Step 2: 验证导入**

Run: `cd hoi4_map_maker && python -c "from PyQt5.QtWidgets import QApplication; app=QApplication([]); from features.map.terrain_combined.page import TerrainCombinedPage; p=TerrainCombinedPage(); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add features/map/terrain_combined/
git commit -m "feat: 地形合并页(高度+地形标签页)"
```

---

### Task 3: 创建合并页面 — 国家与区域（州+国家+大洲）

**Files:**
- Create: `features/map/region_combined/page.py`
- Create: `features/map/region_combined/__init__.py`

- [ ] **Step 1: 创建合并页面**

```python
# features/map/region_combined/__init__.py
"""国家与区域合并模式（州+国家+大洲）。"""
```

```python
# features/map/region_combined/page.py
"""国家与区域合并页面 — QTabWidget 包裹 StatePage + CountryPage + ContinentPage。"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from PyQt5.QtCore import pyqtSignal
from ui.i18n import tr


class RegionCombinedPage(QWidget):
    """国家与区域合并页：标签页切换州/国家/大洲。"""

    # State signals
    auto_states_requested = pyqtSignal(int)
    state_selected = pyqtSignal(int)
    state_property_changed = pyqtSignal(int, str, object)
    state_detail_requested = pyqtSignal(int)
    batch_create_state_toggled = pyqtSignal(bool)
    batch_create_state_confirmed = pyqtSignal()
    # Country signals
    create_country_requested = pyqtSignal()
    quick_create_country_requested = pyqtSignal(str, str, str)
    country_selected = pyqtSignal(str)
    country_property_changed = pyqtSignal(str, str, object)
    country_color_change_requested = pyqtSignal(str)
    # Continent signals
    continent_pick_toggled = pyqtSignal(bool)
    continent_add_requested = pyqtSignal(str)
    continent_rename_requested = pyqtSignal(int, str)
    continent_remove_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        from features.map.state.page import StatePage
        from features.map.country.page import CountryPage
        from features.map.continent.page import ContinentPage

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab { padding: 6px 12px; font-size: 12px; }
            QTabBar::tab:selected { color: white; border-bottom: 2px solid #6c6cf0; }
            QTabBar::tab:!selected { color: #8888a8; }
        """)

        self._state_page = StatePage()
        self._country_page = CountryPage()
        self._continent_page = ContinentPage()
        self._tabs.addTab(self._state_page, tr("tab_state"))
        self._tabs.addTab(self._country_page, tr("tab_country"))
        self._tabs.addTab(self._continent_page, tr("tab_continent"))
        lay.addWidget(self._tabs)

        # 转发 state 信号
        self._state_page.auto_states_requested.connect(self.auto_states_requested)
        self._state_page.state_selected.connect(self.state_selected)
        self._state_page.state_property_changed.connect(self.state_property_changed)
        self._state_page.state_detail_requested.connect(self.state_detail_requested)
        self._state_page.batch_create_state_toggled.connect(self.batch_create_state_toggled)
        self._state_page.batch_create_state_confirmed.connect(self.batch_create_state_confirmed)
        # 转发 country 信号
        self._country_page.create_country_requested.connect(self.create_country_requested)
        self._country_page.quick_create_country_requested.connect(self.quick_create_country_requested)
        self._country_page.country_selected.connect(self.country_selected)
        self._country_page.country_property_changed.connect(self.country_property_changed)
        self._country_page.country_color_change_requested.connect(self.country_color_change_requested)
        # 转发 continent 信号
        self._continent_page.continent_pick_toggled.connect(self.continent_pick_toggled)
        self._continent_page.continent_add_requested.connect(self.continent_add_requested)
        self._continent_page.continent_rename_requested.connect(self.continent_rename_requested)
        self._continent_page.continent_remove_requested.connect(self.continent_remove_requested)
```

- [ ] **Step 2: 验证 + Commit**

Run: `cd hoi4_map_maker && python -c "from PyQt5.QtWidgets import QApplication; app=QApplication([]); from features.map.region_combined.page import RegionCombinedPage; p=RegionCombinedPage(); print('OK')"`

```bash
git add features/map/region_combined/
git commit -m "feat: 国家与区域合并页(州+国家+大洲标签页)"
```

---

### Task 4: 创建合并页面 — 后勤（战略区+后勤系统）

**Files:**
- Create: `features/map/logistics_combined/page.py`
- Create: `features/map/logistics_combined/__init__.py`

- [ ] **Step 1: 创建合并页面**

```python
# features/map/logistics_combined/__init__.py
"""后勤合并模式（战略区+后勤系统）。"""
```

```python
# features/map/logistics_combined/page.py
"""后勤合并页面 — QTabWidget 包裹 StrategicRegionPage + LogisticsPage。"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from PyQt5.QtCore import pyqtSignal
from ui.i18n import tr


class LogisticsCombinedPage(QWidget):
    """后勤合并页：标签页切换战略区域和后勤系统。"""

    # Strategic region signals
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
    # Logistics signals
    open_adjacency_dialog_requested = pyqtSignal()
    open_railway_list_requested = pyqtSignal()
    logistics_railway_level_changed = pyqtSignal(int)
    logistics_railway_draw_toggled = pyqtSignal(bool)
    logistics_supply_pick_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        from features.map.strategic_region.page import StrategicRegionPage
        from features.map.logistics.page import LogisticsPage

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab { padding: 6px 12px; font-size: 12px; }
            QTabBar::tab:selected { color: white; border-bottom: 2px solid #6c6cf0; }
            QTabBar::tab:!selected { color: #8888a8; }
        """)

        self._strategic_region_page = StrategicRegionPage()
        self._logistics_page = LogisticsPage()
        self._tabs.addTab(self._strategic_region_page, tr("tab_strategic_region"))
        self._tabs.addTab(self._logistics_page, tr("tab_logistics"))
        lay.addWidget(self._tabs)

        # 转发 strategic_region 信号
        p = self._strategic_region_page
        p.strategic_region_auto_requested.connect(self.strategic_region_auto_requested)
        p.strategic_region_selected.connect(self.strategic_region_selected)
        p.strategic_region_new_requested.connect(self.strategic_region_new_requested)
        p.strategic_region_delete_requested.connect(self.strategic_region_delete_requested)
        p.strategic_region_name_changed.connect(self.strategic_region_name_changed)
        p.strategic_region_weather_changed.connect(self.strategic_region_weather_changed)
        p.strategic_region_naval_changed.connect(self.strategic_region_naval_changed)
        p.strategic_region_pick_toggled.connect(self.strategic_region_pick_toggled)
        p.create_from_states_toggled.connect(self.create_from_states_toggled)
        p.create_from_states_confirmed.connect(self.create_from_states_confirmed)
        # 转发 logistics 信号
        p2 = self._logistics_page
        p2.open_adjacency_dialog_requested.connect(self.open_adjacency_dialog_requested)
        p2.open_railway_list_requested.connect(self.open_railway_list_requested)
        p2.logistics_railway_level_changed.connect(self.logistics_railway_level_changed)
        p2.logistics_railway_draw_toggled.connect(self.logistics_railway_draw_toggled)
        p2.logistics_supply_pick_toggled.connect(self.logistics_supply_pick_toggled)
```

- [ ] **Step 2: 验证 + Commit**

```bash
git add features/map/logistics_combined/
git commit -m "feat: 后勤合并页(战略区+后勤标签页)"
```

---

### Task 5: 创建合并页面 — 设置（总览贴图+地图配置）

**Files:**
- Create: `features/map/settings_combined/page.py`
- Create: `features/map/settings_combined/__init__.py`

- [ ] **Step 1: 创建合并页面**

```python
# features/map/settings_combined/__init__.py
"""设置合并模式（总览贴图+地图配置）。"""
```

```python
# features/map/settings_combined/page.py
"""设置合并页面 — QTabWidget 包裹 ColormapPage + DefaultMapPage。"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from PyQt5.QtCore import pyqtSignal
from ui.i18n import tr


class SettingsCombinedPage(QWidget):
    """设置合并页：标签页切换总览贴图和地图配置。"""

    colormap_color_changed = pyqtSignal(str, int, int, int)
    colormap_reset_requested = pyqtSignal()
    default_map_river_changed = pyqtSignal(int)
    default_map_tree_add_requested = pyqtSignal()
    default_map_tree_del_requested = pyqtSignal()
    default_map_tree_reset_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        from features.map.colormap.page import ColormapPage
        from features.map.default_map.page import DefaultMapPage

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab { padding: 6px 12px; font-size: 12px; }
            QTabBar::tab:selected { color: white; border-bottom: 2px solid #6c6cf0; }
            QTabBar::tab:!selected { color: #8888a8; }
        """)

        self._colormap_page = ColormapPage()
        self._default_map_page = DefaultMapPage()
        self._tabs.addTab(self._colormap_page, tr("tab_colormap"))
        self._tabs.addTab(self._default_map_page, tr("tab_default_map"))
        lay.addWidget(self._tabs)

        self._colormap_page.colormap_color_changed.connect(self.colormap_color_changed)
        self._colormap_page.colormap_reset_requested.connect(self.colormap_reset_requested)
        self._default_map_page.default_map_river_changed.connect(self.default_map_river_changed)
        self._default_map_page.default_map_tree_add_requested.connect(self.default_map_tree_add_requested)
        self._default_map_page.default_map_tree_del_requested.connect(self.default_map_tree_del_requested)
        self._default_map_page.default_map_tree_reset_requested.connect(self.default_map_tree_reset_requested)
```

- [ ] **Step 2: 验证 + Commit**

```bash
git add features/map/settings_combined/
git commit -m "feat: 设置合并页(总览贴图+地图配置标签页)"
```

---

### Task 6: 重构 ToolPanel — 13→7 模式

**Files:**
- Modify: `ui/tool_panel.py`

- [ ] **Step 1: 更新模式列表和页面创建**

修改 `_init_ui` 中的 `_GroupedModeBar` 参数，从 13 个模式改为 7 个：

```python
# 旧的3组13模式 → 新的7模式（不分组，直接列表）
self._mode_tabs = _GroupedModeBar([
    (tr("group_map_drawing"), [
        ("land", tr("mode_land_new")),         # 画地图
        ("province", tr("mode_province")),      # 省份
        ("terrain", tr("mode_terrain_new")),     # 地形
        ("river", tr("mode_river_nav")),         # 河流
    ]),
    (tr("group_region_mgmt"), [
        ("region", tr("mode_region")),           # 国家与区域
        ("logistics", tr("mode_logistics_new")), # 后勤
    ]),
    (tr("group_settings"), [
        ("settings", tr("mode_settings")),       # 设置
    ]),
])
```

修改 `_create_pages`：用合并页面替换原有页面，同时保留对子页面的引用（兼容外部通过 `_land_page` 等属性访问）：

```python
def _create_pages(self) -> None:
    from features.map.land.page import LandPage
    from features.map.province.page import ProvincePage
    from features.map.terrain_combined.page import TerrainCombinedPage
    from features.map.river.page import RiverPage
    from features.map.region_combined.page import RegionCombinedPage
    from features.map.logistics_combined.page import LogisticsCombinedPage
    from features.map.settings_combined.page import SettingsCombinedPage

    self._land_page = LandPage()
    self._province_page = ProvincePage()
    self._terrain_combined = TerrainCombinedPage()
    self._river_page = RiverPage()
    self._region_combined = RegionCombinedPage()
    self._logistics_combined = LogisticsCombinedPage()
    self._settings_combined = SettingsCombinedPage()

    # 兼容属性：外部代码通过 _height_page, _terrain_page 等访问
    self._height_page = self._terrain_combined._height_page
    self._terrain_page = self._terrain_combined._terrain_page
    self._state_page = self._region_combined._state_page
    self._country_page = self._region_combined._country_page
    self._continent_page = self._region_combined._continent_page
    self._strategic_region_page = self._logistics_combined._strategic_region_page
    self._logistics_page = self._logistics_combined._logistics_page
    self._colormap_page = self._settings_combined._colormap_page
    self._default_map_page = self._settings_combined._default_map_page

    page_list = [
        ("land", self._land_page),
        ("province", self._province_page),
        ("terrain", self._terrain_combined),
        ("river", self._river_page),
        ("region", self._region_combined),
        ("logistics", self._logistics_combined),
        ("settings", self._settings_combined),
    ]
    # ... rest same as before
```

修改信号连接：合并页面的信号直接连接到 ToolPanel（替换原来分开的 `_connect_height_signals` + `_connect_terrain_signals` 等）：

```python
self._connect_land_signals()
self._connect_province_signals()
self._connect_terrain_combined_signals()  # 替换 height + terrain
self._connect_river_signals()
self._connect_region_combined_signals()   # 替换 state + country + continent
self._connect_logistics_combined_signals() # 替换 strategic_region + logistics
self._connect_settings_combined_signals()  # 替换 colormap + default_map
```

每个新方法直接连合并页面的信号（合并页面已经做了子页面→自身的转发）。

- [ ] **Step 2: 更新 _on_mode_changed 的 display_mode 映射**

合并模式的 display_mode 需要映射到 canvas 能识别的模式名。canvas 的 `_full_render` 有 renderers 字典，需要加 "region"/"settings" 的映射：

```python
def _on_mode_changed(self, mode: str) -> None:
    idx = self._mode_index.get(mode, 0)
    self._stack.setCurrentIndex(idx)
    # 合并模式映射到 canvas display_mode
    canvas_mode = {
        "region": "state",      # 默认显示 state 渲染
        "settings": "colormap", # 默认显示 colormap 渲染
    }.get(mode, mode)
    if mode not in ("province", "region"):
        self.tool_changed.emit("brush")
    self._hint_bar.on_mode_changed(mode)
    self.mode_changed.emit(canvas_mode)
```

- [ ] **Step 3: 验证 ToolPanel 启动**

Run: `cd hoi4_map_maker && python -c "from PyQt5.QtWidgets import QApplication; app=QApplication([]); from ui.tool_panel import ToolPanel; tp=ToolPanel(); print('modes:', len(tp._pages)); print('OK')"`
Expected: `modes: 7` + `OK`

- [ ] **Step 4: Commit**

```bash
git add ui/tool_panel.py
git commit -m "refactor: ToolPanel模式13→7(合并页面+信号转发)"
```

---

### Task 7: 更新 main_window.py 信号连接

**Files:**
- Modify: `views/main_window.py`

- [ ] **Step 1: 更新 _connect_signals**

canvas display_mode 的 renderers 字典需要增加合并模式的映射。在 `views/canvas/widget.py` 的 `_full_render` 和 `_partial_render` 中加：

```python
"region": self._render_state_mode,
"settings": self._render_land_mode,
```

同时检查 `views/main_window.py` 的 `_connect_signals` 中所有 `tp.xxx.connect()` 是否仍然有效（ToolPanel 的信号名不变，只是内部转发路径变了）。

- [ ] **Step 2: 验证完整启动**

Run: `cd hoi4_map_maker && python -c "from PyQt5.QtWidgets import QApplication; app=QApplication([]); from views.main_window import MainWindow; w=MainWindow(); print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add views/main_window.py views/canvas/widget.py
git commit -m "fix: 更新canvas渲染器+信号连接适配合并模式"
```

---

### Task 8: 防误触保护

**Files:**
- Modify: `views/canvas/widget.py`

- [ ] **Step 1: 修改 _stamp_brush 的陆地模式**

在 `_stamp_brush` 的 `mode == "land"` 分支中，替换静默清除逻辑：

```python
if mode in ("land", "density"):
    if self._display_mode == "density":
        # ... 密度画笔逻辑不变 ...
        return

    # 防误触：画陆地时如果已有省份，需确认
    if self._has_provinces and not getattr(self, '_province_clear_confirmed', False):
        # 设置标志，让 canvas 发信号给 MainWindow 弹确认框
        self._pending_land_paint = True
        self.land_paint_blocked.emit()  # 新信号
        return

    # 原有逻辑...
```

新增信号 `land_paint_blocked = pyqtSignal()` 在 MapCanvas 上。

MainWindow 连接这个信号，弹确认框：
```python
self._canvas.land_paint_blocked.connect(self._on_land_paint_blocked)

def _on_land_paint_blocked(self):
    reply = QMessageBox.warning(
        self, tr("dlg_land_clear_title"),
        tr("dlg_land_clear_body"),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    if reply == QMessageBox.StandardButton.Yes:
        self._canvas._province_clear_confirmed = True
        # 重新触发渲染
    else:
        self._canvas._pending_land_paint = False
```

- [ ] **Step 2: 添加翻译**

```python
"dlg_land_clear_title": {"zh": "修改陆地", "en": "Modify Land"},
"dlg_land_clear_body": {"zh": "修改陆地将清除现有省份数据，是否继续？", "en": "Modifying land will clear existing province data. Continue?"},
```

- [ ] **Step 3: Commit**

```bash
git add views/canvas/widget.py views/main_window.py ui/i18n.py
git commit -m "feat: 防误触保护(修改陆地前确认清除省份)"
```

---

### Task 9: 添加 i18n 翻译

**Files:**
- Modify: `ui/i18n.py`

- [ ] **Step 1: 添加所有新翻译键**

```python
# 合并模式名
"mode_land_new": {"zh": "画地图", "en": "Draw Map"},
"mode_terrain_new": {"zh": "地形", "en": "Terrain"},
"mode_region": {"zh": "国家与区域", "en": "Countries & Regions"},
"mode_logistics_new": {"zh": "后勤", "en": "Logistics"},
"mode_settings": {"zh": "设置", "en": "Settings"},
"group_settings": {"zh": "配置", "en": "Config"},

# 标签页名
"tab_height": {"zh": "高度", "en": "Height"},
"tab_terrain": {"zh": "地形", "en": "Terrain"},
"tab_state": {"zh": "州", "en": "States"},
"tab_country": {"zh": "国家", "en": "Countries"},
"tab_continent": {"zh": "大洲", "en": "Continents"},
"tab_strategic_region": {"zh": "战略区域", "en": "Strategic Regions"},
"tab_logistics": {"zh": "后勤系统", "en": "Logistics"},
"tab_colormap": {"zh": "总览贴图", "en": "Colormap"},
"tab_default_map": {"zh": "地图配置", "en": "Map Config"},
```

- [ ] **Step 2: Commit**

```bash
git add ui/i18n.py
git commit -m "feat: UI减负翻译(合并模式名+标签页名)"
```

---

### Task 10: 删除独立 density 模式（已合并到画地图）

**Files:**
- Delete: `features/map/density/page.py`
- Delete: `features/map/density/__init__.py`
- Modify: `ui/tool_panel.py` — 确保 density 不再作为独立模式注册

- [ ] **Step 1: 清理 density 目录**

```bash
rm -rf features/map/density/
```

确认 ToolPanel 中 density 相关信号已通过 land_page 转发（密度作为画地图的工具选项）。

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "refactor: 删除独立density模式(已合并到画地图工具)"
```

---

### Task 11: 全量测试 + 最终提交

- [ ] **Step 1: 验证完整启动和模式切换**

```bash
cd hoi4_map_maker
python -c "
from PyQt5.QtWidgets import QApplication
app = QApplication([])
from views.main_window import MainWindow
w = MainWindow()
print('MainWindow OK')
# 验证模式数量
tp = w._tool_panel
print(f'Modes: {len(tp._pages)}')  # 应该是 7
# 验证子页面引用
assert tp._height_page is not None
assert tp._terrain_page is not None
assert tp._state_page is not None
assert tp._country_page is not None
print('All page references OK')
"
```

- [ ] **Step 2: Push**

```bash
git push
```
