# 架构重构设计文档

**日期**: 2026-04-12
**方案**: B — 基于现有 Project + EventBus + 新建 ApplicationController

## 项目目标

这是一个面向 HOI4 MOD 社区发布的地图制作工具。用户的核心诉求：
1. **稳定** — 发布给社区用，不能各种崩溃卡顿
2. **架构清晰** — 每个功能放好位置，改某个功能只动对应文件
3. **调用关系明确** — 功能之间有联动，但调用链要清楚，不要乱串导致 bug

重构不是为了"好看"，是因为**当前的混乱直接导致不断出 bug**。

## 问题背景

v0.20 重构后架构仍有严重耦合问题：
1. main_window 是 God Object（1758 行跨 3 文件），包含大量业务逻辑
2. Feature pages 通过 307 处 `panel._xxx` 私有访问假解耦
3. Canvas widget 既是 View 又是 Model（数据全挂上面）
4. 省份重新生成后，下游数据（State/Country/大陆/战略区域）不会自动清除
5. 两套撤销系统共存（UndoManager + CommandHistory），split_selected() 两套都不用

## 设计目标

- main_window < 400 行，只做 UI 组装和信号路由
- Feature pages 不访问任何 `panel._xxx` 私有属性
- 数据级联失效自动化（省份变 → State 清 → Country 清）
- 统一用 CommandHistory 做撤销

## 架构总览

```
用户事件
  ↓
MainWindow (薄壳: 菜单 + 信号路由)
  ↓
ApplicationController (调度: 模式切换 / 省份信息 / 颜色刷新 / 撤销)
  ↓
Feature Controllers (state / land / province / ...)
  ↓ (通过 Command)
CommandHistory → Project.map_data / Project.*_mgr
  ↓ (通过 EventBus)
级联失效链: province_regen → state_clear → country_clear → UI 刷新
  ↓
Canvas (只读数据 + 渲染) + ToolPanel (纯容器 + 页面切换)
```

---

## 阶段 1: 修 bug + 抽 ApplicationController

### 1.1 修 bug

**split_selected() 撤销 bug**
- 文件: `controllers/province.py` 第 72-103 行
- 问题: 直接改 province_map 数组，没创建 Command
- 修复: 创建 `commands/province/split.py` → `SplitProvinceCommand`

**省份重新生成后列表不刷新**
- 文件: `views/main_window_actions.py` 第 110-113 行
- 问题: `_on_generate_done()` 只更新了 province_map，没刷新 State/Country 列表
- 修复: 阶段 2 的级联事件会自动处理

### 1.2 新建 ApplicationController

**新文件**: `controllers/app_controller.py` (~400 行)

从 main_window.py 搬出的逻辑：

| 方法 | 原位置 | 功能 |
|------|--------|------|
| `calculate_province_info(pid)` | main_window.py:517-585 | 省份信息计算+缓存 |
| `refresh_state_colors()` | main_window.py:713-718 | 构建 state 颜色图 |
| `refresh_country_colors()` | main_window.py:731-737 | 构建 country 颜色图 |
| `refresh_vp_data()` | main_window.py:720-726 | 收集 VP 数据 |
| `refresh_state_list()` | main_window.py:709-711 | 刷新 state 列表 |
| `refresh_country_list()` | main_window.py:728-729 | 刷新 country 列表 |
| `on_mode_changed(mode)` | main_window.py:481-498 | 模式切换副作用 |
| `on_stroke_started/ended()` | main_window.py:623-676 | 撤销管理 |

**MainWindow 保留**:
- `_init_ui()` — 菜单栏、工具栏、布局
- `_connect_signals()` — 信号 → AppController 路由
- `_show_welcome()` / `_show_editor()` — 页面切换
- 快捷键注册

**关键接口**:
```python
class ApplicationController:
    def __init__(self, project, canvas, tool_panel, command_history, event_bus):
        ...
    
    def on_mode_changed(self, mode: str) -> None: ...
    def on_province_clicked(self, pid: int) -> None: ...
    def undo(self) -> None: ...
    def redo(self) -> None: ...
```

### 涉及文件
- 新建: `controllers/app_controller.py`
- 新建: `commands/province/split.py`
- 修改: `views/main_window.py` (删除搬走的方法)
- 修改: `controllers/province.py` (split_selected 用 Command)

---

## 阶段 2: 级联失效机制

### 2.1 事件定义

在 EventBus 上新增事件（不需要新文件，沿用现有 event_bus）：

| 事件名 | 触发时机 | 携带数据 |
|--------|----------|----------|
| `province_map_regenerated` | 全量重新生成省份后 | `{incremental: bool}` |
| `province_map_incremental` | 增量生成省份后 | `{new_ids: list[int]}` |

### 2.2 级联订阅链

```
province_map_regenerated
  → StateController.on_province_regen()     # clear all states
  → CountryController.on_province_regen()   # clear all countries  
  → ContinentController.on_province_regen() # clear continent assignments
  → StrategicRegionController.on_province_regen() # clear regions
  → AppController.on_province_regen()       # 刷新 UI 列表 + 颜色图
```

### 2.3 订阅时机

关键改变：级联订阅在 **Controller 构造时** 注册，不是 activate() 时。
因为省份重新生成可能发生在任何模式下，不只是 State 模式。

```python
class StateController(BaseController):
    def __init__(self, project, command_history):
        super().__init__(project, command_history)
        # 始终监听，不管当前是什么模式
        self.event_bus.subscribe("province_map_regenerated", self._on_province_regen)
    
    def _on_province_regen(self, event):
        if not event.data.get("incremental"):
            self.project.state_mgr.clear()
            self.event_bus.emit("state_changed", state_id=0, action="refresh")
```

### 2.4 触发点

修改 `views/main_window_actions.py` 的 `_on_generate_done()`：
```python
def _on_generate_done(self, province_map, count):
    was_incremental = self._gen_thread._incremental
    self._canvas.province_map = province_map
    self._update_province_count()
    # 发事件，让级联自动处理
    self.event_bus.emit("province_map_regenerated", incremental=was_incremental)
    self._status_info.setText(f"省份生成完成: {count} 个")
```

### 涉及文件
- 修改: `controllers/state.py` (加 _on_province_regen)
- 修改: `controllers/country.py` (加 _on_province_regen)
- 修改: `controllers/continent.py` (加 _on_province_regen)
- 修改: `controllers/strategic_region.py` (加 _on_province_regen)
- 修改: `controllers/app_controller.py` (加 UI 刷新响应)
- 修改: `views/main_window_actions.py` (改 _on_generate_done)

---

## 阶段 3: Feature page 真正解耦

### 3.1 目标

每个 page.py 变成独立 QWidget 子类：
- 自己持有控件（`self._brush_slider` 而非 `panel._brush_slider`）
- 暴露公开信号和方法
- 不需要知道 ToolPanel 的存在

### 3.2 模式：以 LandPage 为例

**之前** (`features/map/land/page.py`):
```python
def build_page(panel) -> QWidget:
    page = QWidget()
    panel._tool_group = QButtonGroup()
    panel._brush_slider = QSlider(...)
    panel._brush_slider.valueChanged.connect(panel._on_brush_size)
    ...
    return page
```

**之后** (`features/map/land/page.py`):
```python
class LandPage(QWidget):
    # 公开信号
    tool_changed = pyqtSignal(str)
    brush_size_changed = pyqtSignal(int)
    tile_type_changed = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tool_group = QButtonGroup()
        self._brush_slider = QSlider(...)
        self._brush_slider.valueChanged.connect(self.brush_size_changed)
        self._build_ui()
    
    def _build_ui(self):
        # 所有 UI 构建在这里
        ...
```

### 3.3 ToolPanel 变化

**之前** (568 行，持有所有页面的控件):
```python
class ToolPanel(QWidget):
    def __init__(self):
        self._brush_slider = ...  # 被 land/page.py 注入
        self._state_list = ...    # 被 state/page.py 注入
        ...
```

**之后** (~200 行，纯容器):
```python
class ToolPanel(QWidget):
    mode_changed = pyqtSignal(str)
    
    def __init__(self):
        self._stack = QStackedWidget()
        self._pages: dict[str, QWidget] = {}
    
    def add_page(self, mode_id: str, page: QWidget) -> None:
        self._pages[mode_id] = page
        self._stack.addWidget(page)
    
    def get_page(self, mode_id: str) -> QWidget:
        return self._pages[mode_id]
```

### 3.4 转换顺序（从简到难）

1. land/page.py (71 `panel._` 访问，最简单的画笔UI)
2. height/page.py
3. terrain/page.py
4. province/page.py
5. state/page.py (有列表交互，稍复杂)
6. country/page.py
7. river/page.py
8. continent/page.py
9. logistics/page.py
10. strategic_region/page.py
11. colormap/page.py, default_map/page.py

### 涉及文件
- 修改: 所有 `features/map/*/page.py` (11 个文件)
- 修改: `ui/tool_panel.py` (从 568 行降到 ~200 行)
- 修改: `views/main_window.py` (连接方式变化)
- 修改: `controllers/app_controller.py` (连接 page 信号)

---

## 阶段 4: 统一撤销系统

### 4.1 现状

- **UndoManager** (`domain/undo_manager.py`): 快照式，zlib 压缩整个数组，main_window 在画笔 stroke 前后调用
- **CommandHistory** (`commands/history.py`): Command 模式，每个操作是可逆 Command，controllers 使用
- **split_selected()**: 两个都不用，直接改数组

### 4.2 统一方案

新建 `commands/land/brush_stroke.py`:
```python
class BrushStrokeCommand(Command):
    """画笔一次 stroke 的所有像素变化。"""
    def __init__(self, map_data, layer: str, changes: dict[tuple, tuple]):
        # changes: {(y,x): (old_val, new_val)}
        ...
    def execute(self): ...
    def undo(self): ...
```

- AppController 在 stroke_started 时开始收集变化
- stroke_ended 时创建 BrushStrokeCommand 并 push 到 CommandHistory
- 删除 UndoManager

### 4.3 风险

画笔 stroke 可能涉及数万像素，全部存 dict 内存开销大。
**缓解**: 只存变化区域的 bbox 快照（numpy 切片 copy），而非逐像素 dict。

### 涉及文件
- 新建: `commands/land/brush_stroke.py`
- 删除: `domain/undo_manager.py`
- 修改: `controllers/app_controller.py` (stroke 管理)
- 修改: `controllers/land.py` (stroke 收集)

---

## 验证方案

每个阶段完成后：

1. **运行程序**: `python main.py`，加载存档 `2.hoi4proj`
2. **基本功能测试**:
   - Land 模式：画笔/橡皮/填充/撤销
   - Province 模式：生成省份（全量+增量），合并/切割
   - State 模式：自动分组，选择 State，设置 VP
   - Country 模式：创建国家，分配领土
   - 导出测试
3. **级联测试**（阶段 2 后）:
   - 加载旧存档 → 重新生成省份 → 确认 State/Country 列表已清空
   - 切换到 State 模式 → 不卡顿
4. **撤销测试**（阶段 4 后）:
   - 画笔画几笔 → Ctrl+Z 撤销 → 确认恢复
   - 切割省份 → Ctrl+Z → 确认恢复
5. **跑 pytest**: `pytest tests/`

## 文件清单

### 新建文件
| 文件 | 用途 | 预计行数 |
|------|------|----------|
| `controllers/app_controller.py` | 应用调度器 | ~400 |
| `commands/province/split.py` | 切割省份 Command | ~60 |
| `commands/land/brush_stroke.py` | 画笔 Command | ~80 |

### 主要修改文件
| 文件 | 变化 |
|------|------|
| `views/main_window.py` | 836 → ~400 行，删除业务逻辑 |
| `ui/tool_panel.py` | 568 → ~200 行，变纯容器 |
| `features/map/*/page.py` × 11 | `build_page(panel)` → 独立 QWidget 类 |
| `controllers/state.py` | 加级联订阅 |
| `controllers/country.py` | 加级联订阅 |
| `controllers/province.py` | split 改用 Command |
| `views/main_window_actions.py` | 发 province_regen 事件 |

### 删除文件
| 文件 | 原因 |
|------|------|
| `domain/undo_manager.py` | 被 CommandHistory 统一取代 |
