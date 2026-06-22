# Universal RDC Importer

[![Blender](https://img.shields.io/badge/Blender-4.1-orange?logo=blender)](https://www.blender.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows-blue)]()

> 🎮 从 RenderDoc 捕获文件 (.rdc) 导入任意 3D 模型到 Blender

基于 [MapsModelsImporter](https://github.com/eliemichel/MapsModelsImporter) 扩展，突破仅支持 Google Maps 的限制，支持从**任意应用/游戏**的 RenderDoc 捕获中提取 3D 模型。

## ✨ 功能

| 功能 | 说明 |
|------|------|
| 🎯 **通用导入** | 不限来源——游戏、软件、网页的 3D 模型均可导入 |
| 📐 **完整几何** | 顶点位置、索引缓冲、三角面重建 |
| 🖼️ **UV 贴图** | 自动提取 UV 坐标并映射纹理 |
| 🧠 **智能过滤** | 自动跳过 2D 绘制调用和过小几何体 |
| 📊 **进度条** | 大型模型导入时显示进度 |
| 🧹 **临时清理** | 一键清理导入产生的中间文件 |
| 🌐 **中文界面** | 全中文菜单和面板 |

## 📦 安装

1. 安装 [RenderDoc](https://renderdoc.org/)
2. Blender → `Edit` → `Preferences` → `Add-ons` → `Install`
3. 选择 `UniversalRDCImporter-v1.0.0.zip`
4. 勾选启用

## 🚀 使用

### 菜单入口
`File` → `Import` → `通用 RDC 文件 (.rdc)`

### 侧边栏面板
3D 视图按 `N` → `RDC Import` 标签

### 工作流程

| 步骤 | 操作 |
|:--:|------|
| 1 | 启动 RenderDoc，注入目标应用 |
| 2 | 在 3D 模型渲染时按 `Print Screen` 抓帧 |
| 3 | 保存为 `.rdc` 文件 |
| 4 | 在 Blender 中导入 `.rdc` |

> 💡 **提示**：导入后进入编辑模式（Tab）即可在 UV 编辑器中查看 UV 布局。

## 🔧 设置

| 设置 | 说明 |
|------|------|
| 临时目录 | 中间文件存放位置，默认使用 rdc 文件所在目录 |
| 最大绘制调用数 | 限制导入数量（-1 = 全部） |
| 调试信息 | 控制台输出详细日志 |

## 🗂️ 文件结构

```
UniversalRDCImporter/
├── __init__.py              # 插件入口
├── operators.py             # 导入操作符
├── panels.py                # 侧边栏面板
├── preferences.py           # 偏好设置
├── universal_importer.py    # Blender 端导入逻辑
├── universal_rd.py          # RenderDoc 提取（子进程）
├── meshdata.py              # 网格数据解析
├── rdutils.py               # RenderDoc 工具
├── profiling.py             # 性能统计
├── utils.py                 # 通用工具
└── bin/win64/               # RenderDoc 依赖库
    ├── renderdoc.pyd
    ├── renderdoc.dll
    └── ...
```

## 📋 系统要求

| 组件 | 版本 |
|------|------|
| Blender | 4.1+ |
| RenderDoc | 1.x |
| 操作系统 | Windows 64-bit |

## 🙏 致谢

- [MapsModelsImporter](https://github.com/eliemichel/MapsModelsImporter) by [Élie Michel](https://github.com/eliemichel)
- [RenderDoc](https://renderdoc.org/) by Baldur Karlsson

## 📄 许可

MIT License — 详见 [LICENSE](LICENSE)
