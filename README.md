# hoi4-mod-maker

> 钢铁雄心 4 (Hearts of Iron IV) 全转换 MOD 制作工具

一个用 Python + PyQt5 写的桌面应用，从零开始画地图、生成省份、设置 state 和国家，**一键导出**完整可玩的 HOI4 Total Conversion MOD。

**当前版本**：v0.15

---

## 功能

### 地图绘制
- 大陆 / 海洋 / 湖泊画笔，支持画笔/橡皮/填充/平移
- 加载参考底图叠加描图
- 从图片提取陆海（高度图/卫星图自动转 tile_map）

### 省份系统
- Voronoi 自动生成 1000-15000 个省份，密度可调
- **合并** / **切割** / **扩张工具**（套索拖动边界）
- ID 自动安全压实（合并删省份后无 ID gap，state/VP/首都引用自动同步）

### 地形 / 高度 / 河流
- 10 种地形画刷（平原/森林/丘陵/山地/沙漠/沼泽/丛林/城市/海洋/湖泊）
- 按省份赋地形，支持自动从陆地推断
- 高度图编辑（滑块 + 5 个预设 + 自动生成 + 平滑滤镜）
- 河流绘制（12 种类型，严格按 HOI4 调色板）

### State / 国家
- 自动从省份生成 State，支持归属国家、人口、等级、VP
- 创建国家（TAG / 颜色 / 政党 / 首都）
- 双击省份设胜利点

### 验证 / 诊断
- 一键全图诊断：X-crossings (含横向 wrap) / 过小省份 / 过大省份 / ID gap / 不连通省份 / 总数预警
- 双击诊断结果跳转到地图对应位置
- 所有规则带 HOI4 官方文档行号引用

### 工程管理
- 保存 / 加载 `.hoi4proj` 工程文件（zip 格式）
- 撤销 / 重做（30 步历史，zlib 压缩）

### 一键导出
- 27 种 HOI4 文件全部生成：provinces.bmp / definition.csv / heightmap / terrain / rivers / states / countries / characters / strategicregions / replace_path...
- 导出前自动跑安全清理（ID 压实 + state/country 引用同步）

---

## 安装

```bash
git clone https://github.com/<YOUR_USERNAME>/hoi4-mod-maker.git
cd hoi4-mod-maker
pip install -r requirements.txt
python main.py
```

**系统要求**：
- Python 3.10+
- Windows / macOS / Linux（主要在 Windows 测试）

**依赖**：
- PyQt5
- NumPy
- Pillow
- SciPy
- OpenCV (cv2)

---

## 项目结构

```
hoi4_map_maker/
├── main.py                    # 入口
├── data/
│   ├── constants.py           # 全局常量
│   └── terrain_types.py       # HOI4 地形定义
├── core/
│   ├── hoi4_rules.py          # HOI4 硬规则中心（带文档行号）
│   ├── map_data.py            # 数据中心（统一封装 5 张图层）
│   ├── tools/                 # 工具框架（基类 + 注册表 + 套索）
│   ├── province_generator.py  # Voronoi 省份生成
│   ├── province_validator.py  # 验证 + 修复
│   ├── state_manager.py       # State 数据
│   ├── country_manager.py     # 国家数据
│   ├── river_manager.py       # 河流数据
│   ├── undo_manager.py        # 撤销 / 重做
│   └── project_io.py          # 保存 / 加载 .hoi4proj
├── ui/
│   ├── main_window.py         # 主窗口
│   ├── canvas_widget.py       # 画布（QGraphicsView）
│   ├── tool_panel.py          # 左侧工具面板
│   └── i18n.py                # 中英双语
└── export/
    ├── mod_exporter.py        # 一键导出 27 个文件
    ├── bmp_writer.py          # BMP 写入
    ├── csv_writer.py          # CSV / TXT 写入
    └── verify_mod.py          # 导出后验证
```

---

## 路线图

### v1.0 目标（地图工具完全体）
- [x] 大陆 / 省份 / 地形 / 高度 / 河流编辑
- [x] State / 国家系统
- [x] ID 安全压实
- [x] 套索扩张工具
- [ ] 河流编辑器实测进游戏验证
- [ ] 打包 .exe 发布

### v2.0 目标（玩法内容）
- [ ] 国家科技 / 国策树
- [ ] 顾问 / 将领系统
- [ ] 起始部队 OOB
- [ ] 事件 / 决议编辑器

---

## 许可证

本项目采用 **GNU General Public License v3.0** 开源许可。

简单说：
- ✅ 你可以自由使用、修改、分发
- ✅ 你可以用它做任何 MOD（你做出来的 MOD 不受 GPL 约束）
- ❌ 但**修改本工具的代码**之后，必须**同样以 GPL 开源**，不能闭源出售
- 详见 [LICENSE](LICENSE) 文件

---

## 贡献

欢迎提 Issue 和 Pull Request。

提交代码请遵循：
- 中文注释
- snake_case 函数名 / CamelCase 类名
- 文件 < 800 行
- NumPy 向量化，不要 Python 循环处理像素
