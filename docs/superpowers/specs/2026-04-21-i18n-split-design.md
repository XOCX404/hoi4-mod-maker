# i18n 拆分设计（按语言分文件夹）

**日期**：2026-04-21
**范围**：只改 `ui/i18n.py`（1508 行）→ `ui/i18n/` 文件夹
**目标**：让翻译好维护、加新语言零成本、不动任何功能代码

---

## 1. 问题

`ui/i18n.py` 现状：
- 单文件 **1508 行** / **1124 条翻译条目** / **~65 个 section 注释块**
- 所有 key 的 zh+en 挤在一个 `_translations` 大字典里
- 加新功能 = 在 1500 行里 Ctrl+F 定位、插入、保持分节注释
- 以后加第 3、第 4 种语言 = 要给 1124 条每一条加新 key，改动面极大

**功能代码本身是干净的**：
- features/views 里没有硬编码中英文原文
- 所有 UI 字串都走 `tr("key")`
- 所以这次拆分**只动翻译仓库本身，功能代码零改动**

---

## 2. 目标架构

**重要**：现在的 `ui/i18n.py`（单文件）必须**删除**，替换为 `ui/i18n/` 目录（即 Python 包）。两者不能共存，否则 Python 会优先选包而忽略文件（但留着文件会让代码库混淆）。

**语言代码约定**：使用 ISO 639-1 小写两字母码（`zh` / `en` / `ja` / `ru` / `ko` / `de` / `fr` 等）。未来若需要区分方言（如 `zh_CN` vs `zh_TW`），也走文件夹名的方式，加载器天然支持。

```
ui/i18n/
├── __init__.py          # 加载器 + tr() + set_language() + get_language()
│
├── zh/                  # 中文
│   ├── __init__.py      # （空，只做包标记）
│   ├── menu.py          # STRINGS = {"action_new": "新建项目", ...}
│   ├── toolbar.py
│   ├── status.py
│   ├── navigation.py
│   ├── welcome.py
│   ├── common.py
│   ├── dialogs.py
│   ├── context_menu.py
│   ├── tips.py
│   ├── validate.py
│   ├── export.py
│   ├── import_.py
│   ├── crash.py
│   ├── land.py
│   ├── province.py
│   ├── state.py
│   ├── country.py
│   ├── continent.py
│   ├── strategic_region.py
│   ├── logistics.py
│   ├── colormap.py
│   ├── default_map.py
│   ├── height.py
│   ├── river.py
│   ├── terrain.py
│   ├── density.py
│   └── new_land.py
│
└── en/                  # 英文（和 zh/ 同样的文件名 + 同样的 key）
    ├── __init__.py
    ├── menu.py          # STRINGS = {"action_new": "New Project", ...}
    ├── ...
    └── new_land.py
```

**每个翻译文件的格式（统一、极简）**：
```python
# ui/i18n/zh/menu.py
STRINGS = {
    "action_new":  "新建项目",
    "action_open": "打开项目",
    "action_save": "保存项目",
}
```

```python
# ui/i18n/en/menu.py
STRINGS = {
    "action_new":  "New Project",
    "action_open": "Open Project",
    "action_save": "Save Project",
}
```

---

## 3. 加载器（`ui/i18n/__init__.py`）

**行为**：
1. 启动时扫描 `ui/i18n/*/` 下所有语言文件夹
2. 每个语言文件夹下的所有 `*.py`（除 `__init__.py`）都导入，合并其中的 `STRINGS` dict
3. 如果不同文件里 key 重复，**抛 ImportError**（防止维护时无意重复定义）
4. 对外暴露：`tr(key, *args)` / `set_language(lang)` / `get_language()` / `available_languages()`
5. `tr()` 查不到当前语言的 key 时，**fallback 到 en → zh → key 本身**，不崩

**核心代码骨架**：
```python
# ui/i18n/__init__.py
import importlib, pkgutil
from pathlib import Path
from PyQt5.QtCore import QSettings

_languages: dict[str, dict[str, str]] = {}   # lang_code -> {key: text}
_current_lang: str = "zh"
_fallback_chain = ("en", "zh")


def _load_all_languages() -> None:
    """扫描 ui/i18n/<lang>/ 下所有 .py，合并 STRINGS 字典"""
    pkg_root = Path(__file__).parent
    for lang_dir in pkg_root.iterdir():
        if not lang_dir.is_dir() or lang_dir.name.startswith("_"):
            continue
        lang = lang_dir.name
        merged: dict[str, str] = {}
        for py_file in lang_dir.glob("*.py"):
            if py_file.stem == "__init__":
                continue
            mod = importlib.import_module(f"ui.i18n.{lang}.{py_file.stem}")
            strings = getattr(mod, "STRINGS", {})
            overlap = merged.keys() & strings.keys()
            if overlap:
                raise ImportError(
                    f"重复的翻译 key {overlap} 在 {lang}/{py_file.name}"
                )
            merged.update(strings)
        _languages[lang] = merged


def _load_saved_language() -> str:
    try:
        s = QSettings("HOI4MapMaker", "Settings")
        return s.value("language", "zh")
    except Exception:
        return "zh"


_load_all_languages()
_current_lang = _load_saved_language()


def available_languages() -> list[str]:
    """列出所有已加载的语言 code (eg. ['zh', 'en', 'ja'])"""
    return sorted(_languages.keys())


def set_language(lang: str) -> None:
    global _current_lang
    if lang in _languages:
        _current_lang = lang
        try:
            s = QSettings("HOI4MapMaker", "Settings")
            s.setValue("language", lang)
        except Exception:
            pass


def get_language() -> str:
    return _current_lang


def tr(key: str, *args) -> str:
    for lang in (_current_lang, *_fallback_chain):
        text = _languages.get(lang, {}).get(key)
        if text is not None:
            return text.format(*args) if args else text
    return key  # 最终 fallback：显示 key 本身便于定位漏翻
```

---

## 4. Key → 文件 映射表

基于现有 1508 行里的 section 注释，映射到 27 个目标文件。**每个文件预期 30-80 行**。

| 目标文件 | 原文件的 section（按源行号） | 估计条目数 |
|---|---|---|
| `menu.py` | 主窗口(菜单部分, L18-56)、菜单补充(L525)、帮助菜单(L735) | ~40 |
| `toolbar.py` | 工具面板(L58-75) | ~15 |
| `status.py` | 状态栏(L98)、状态栏补充(L532)、状态栏信息(L1341)、状态消息(L878) | ~30 |
| `navigation.py` | 导航栏 7 模式(L624)、导航组 tooltip(L866) | ~25 |
| `welcome.py` | 欢迎页(L488, L875) | ~20 |
| `common.py` | 通用(L207, L1461)、单位词(L621) | ~30 |
| `dialogs.py` | 对话框(L556)、新手引导(L648)、快捷键(L1352)、关于(L618)、VP(L1379) | ~100 |
| `context_menu.py` | 右键菜单(L1465) | ~10 |
| `tips.py` | 模式操作提示条(L740) | ~30 |
| `validate.py` | 验证(L84)、验证结果补充(L608) | ~20 |
| `export.py` | 导出(L93)、导出验证(L946)、导出对话框(L958) | ~100 |
| `import_.py` | 导入(L599) | ~10 |
| `crash.py` | 崩溃处理(L953) | ~5 |
| `land.py` | 主窗口里的 tile_land/sea/lake(L70-73) | ~8 |
| `province.py` | 省份生成(L77)、属性地形 page(L827)、省份建筑对话框(L1331) | ~60 |
| `state.py` | State 页面(L110)、州页面补充(L1070)、State 详情对话框(L1276) | ~90 |
| `country.py` | 国家页面(L125) | ~20 |
| `continent.py` | 大陆页面(L145)、大陆对话框(L1173)、剩余硬编码(L1406) | ~40 |
| `strategic_region.py` | 战略区域页面(L157)、战略区域对话框(L1127)、战略区域页面补充(L1059)、剩余硬编码(L1383) | ~80 |
| `logistics.py` | 后勤页面(L176)、后勤页面补充(L1049)、邻接对话框(L1149)、邻接规则对话框(L1193)、铁路对话框(L1268)、剩余硬编码(L1393, L1418, L1458) | ~150 |
| `colormap.py` | 总览贴图(L191)、颜色贴图对话框(L1248)、剩余硬编码(L1451) | ~15 |
| `default_map.py` | 地图配置(L199)、地图配置对话框(L1232)、剩余硬编码(L1441) | ~20 |
| `height.py` | 高度 tab 顶部大按钮(L854)、页面 UI 里高度相关 key | ~25 |
| `river.py` | 河流(L107)、河流 page 新版(L790)、河流类型按钮(L895) | ~25 |
| `terrain.py` | 地形视觉(L842)、地形类型(L907)、Graphical terrain 变体(L919) | ~90 |
| `density.py` | 密度模式(L317) | ~60 |
| `new_land.py` | 新大陆画笔(L1259, L1345) | ~20 |

**未分类兜底**：拆完后跑脚本核对——若源 `_translations` 里有 key 没归入上表任何一个文件，报错并由人工判定归属。**绝对不允许遗漏**（否则运行时会出现 key-only 未翻译字串）。

---

## 5. 调用点兼容性

**所有 `tr()` 的调用点**（features/views/ui 里，粗略估计上千处）**一个字不改**：
- `tr("new_land_generate")` 还是有效
- `tr("status_pos", x, y)` 格式化参数还是有效
- `set_language("en")` / `get_language()` API 不变

**唯一新增的公共 API**：
- `available_languages() -> list[str]` — 供设置对话框动态填充"语言"下拉

**设置对话框需要小改一处**（不算功能代码改动，属 i18n 配套）：把硬编码的 `["zh", "en"]` 改成 `available_languages()`。

---

## 6. 加新语言的流程（验收要求）

**示例：加日语 `ja`**

1. 复制 `ui/i18n/en/` 整个文件夹 → `ui/i18n/ja/`
2. 挨个文件打开 `ja/*.py`，把 `STRINGS` 里的英文 value 翻译成日文
3. 软件重启
4. **预期结果**：
   - "设置 → 语言"下拉自动多出 "ja" 选项
   - 选 ja 后所有已翻译文案变日文
   - 未翻译的 key 自动 fallback 到英文，**软件不崩**

**零代码改动**。纯加文件。

---

## 7. 打包（PyInstaller）

`hoi4_map_maker.spec` 需要把 `ui/i18n/*/*.py` **确保打进 exe**。

由于 `__init__.py` 里用 `importlib.import_module` 动态加载，PyInstaller 默认可能不会把那些模块识别为依赖。需要在 spec 的 `hiddenimports` 或 `datas` 里显式加入：

```python
# hoi4_map_maker.spec 里
hiddenimports = [
    ...,
    'ui.i18n.zh.menu', 'ui.i18n.zh.toolbar', ..., 'ui.i18n.zh.new_land',
    'ui.i18n.en.menu', 'ui.i18n.en.toolbar', ..., 'ui.i18n.en.new_land',
]
```

**自动化**：在 spec 开头写一段扫描 `ui/i18n/*/*.py` 的代码自动生成 `hiddenimports`，避免手动列表维护。这样社区用户加了 `ja/` 文件夹，重新 PyInstaller 打包也会自动把 `ui.i18n.ja.*` 算进去：

```python
# hoi4_map_maker.spec 顶部
from pathlib import Path
I18N_DIR = Path("ui/i18n")
_i18n_modules = [
    f"ui.i18n.{p.parent.name}.{p.stem}"
    for p in I18N_DIR.glob("*/*.py")
    if p.stem != "__init__"
]
# 然后把 _i18n_modules 加进 Analysis(... hiddenimports=_i18n_modules + [...])
```

---

## 8. 回滚方案

若拆分后出现问题：
- 保留 `ui/i18n.py.bak` 作为原始备份（拆分脚本第一步就做）
- 恢复：`git revert` 或 `cp ui/i18n.py.bak ui/i18n.py && rm -rf ui/i18n/`
- 由于功能代码零改动，回滚无副作用

---

## 9. 验收标准

拆分完成后必须全部通过：
- [ ] 启动软件，默认中文界面正常（对比拆分前截图无差异）
- [ ] 设置 → 语言切到 English，重启后界面变英文（对比拆分前）
- [ ] 1124 条翻译条目 100% 迁移完毕（脚本对比 key 集合）
- [ ] 每个 feature 页面抽查 3 个按钮/提示，中英切换正确
- [ ] 跑 `pytest`，不应因为 i18n 路径变化导致测试失败
- [ ] 手动打包 `pyinstaller hoi4_map_maker.spec`，exe 运行语言切换正常
- [ ] 额外：造一个 `ui/i18n/test_lang/` 伪语言目录（只翻译 menu.py），验证 fallback 生效、下拉菜单出现该语言

---

## 10. 不做的事（YAGNI）

- 不引入 gettext/.po/.mo
- 不引入 Qt Linguist / .ts / .qm
- 不引入 YAML/JSON（纯 Python 字典最省事，AI/IDE 高亮友好）
- 不拆 `tr()` 调用方的功能代码
- 不改 features/ 目录结构
- 不改 canvas/main_window 等其他超标文件（那是另一个议题）

---

## 11. 下一步

本 spec 通过用户审阅后，进入 `writing-plans` 阶段，输出可逐步执行的实施计划（带检查点和回滚点）。
