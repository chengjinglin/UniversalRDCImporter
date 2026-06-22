# Universal RDC Importer - 通用 RenderDoc 3D 模型导入器
# 基于 MapsModelsImporter (Elie Michel)，扩展通用导入 + 汉化

bl_info = {
    "name": "Universal RDC Importer (通用RDC导入)",
    "author": "基于 Elie Michel 的 MapsModelsImporter 扩展",
    "version": (1, 0, 0),
    "blender": (4, 1, 0),
    "location": "文件 > 导入 > 通用 RDC / 3D视图 > 侧边栏 > RDC Import",
    "description": "从 RenderDoc 捕获文件 (.rdc) 导入任意 3D 模型到 Blender",
    "warning": "",
    "wiki_url": "",
    "category": "Import-Export",
}

from . import preferences
from . import operators
from . import panels

def register():
    preferences.register()
    operators.register()
    panels.register()

def unregister():
    panels.unregister()
    operators.unregister()
    preferences.unregister()

if __name__ == "__main__":
    register()

