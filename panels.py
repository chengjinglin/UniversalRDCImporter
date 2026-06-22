import bpy
from bpy.props import IntProperty


class VIEW3D_PT_rdc_importer(bpy.types.Panel):
    bl_label = "RDC 导入器"
    bl_idname = "VIEW3D_PT_rdc_test"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RDC Import"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # 导入
        box = layout.box()
        box.label(text="导入模型", icon="IMPORT")
        col = box.column(align=True)
        col.prop(scene, "universal_rdc_max_blocks")
        col.operator("universal_rdc.import", text="选择 .rdc 文件", icon="FILE_FOLDER")

        # 工具
        box = layout.box()
        box.label(text="工具", icon="TOOL_SETTINGS")
        col = box.column(align=True)
        col.operator("universal_rdc.cleanup", text="清理临时文件", icon="TRASH")

        # 说明
        box = layout.box()
        box.label(text="说明", icon="INFO")
        col = box.column(align=True)
        col.label(text="从任意 RenderDoc")
        col.label(text="捕获文件导入 3D 模型")
        col.separator()
        col.label(text="自动过滤：")
        col.label(text="• 2D 绘制调用")
        col.label(text="• 过小几何体 (<10面)")
        col.label(text="• 无顶点数据的调用")


def register():
    bpy.utils.register_class(VIEW3D_PT_rdc_importer)
    bpy.types.Scene.universal_rdc_max_blocks = IntProperty(
        name="最大绘制调用数",
        description="-1 = 全部",
        default=200, min=-1, soft_max=5000)


def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_rdc_importer)
    del bpy.types.Scene.universal_rdc_max_blocks
