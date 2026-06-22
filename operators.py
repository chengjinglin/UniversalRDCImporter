import os
import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, IntProperty
from bpy.types import Operator


class RDC_OT_import_universal(Operator, ImportHelper):
    bl_idname = "universal_rdc.import"
    bl_label = "导入 RDC 文件"
    bl_description = "从 RenderDoc 捕获文件 (.rdc) 导入任意 3D 模型"

    filename_ext = ".rdc"
    filter_glob: StringProperty(default="*.rdc", options={"HIDDEN"}, maxlen=1024)
    max_blocks: IntProperty(name="最大绘制调用数", default=200, min=-1, soft_max=5000,
                            description="-1 表示导入全部，大型文件可能需要较长时间")

    def invoke(self, context, event):
        try:
            self.max_blocks = context.scene.universal_rdc_max_blocks
        except Exception:
            pass
        return super().invoke(context, event)

    def execute(self, context):
        from .universal_importer import importUniversalCapture, UniversalImportError
        try:
            count = importUniversalCapture(context, self.filepath, self.max_blocks)
            if count and count > 0:
                self.report({"INFO"}, "成功导入 {} 个模型".format(count))
            else:
                self.report({"WARNING"}, "未导入任何模型")
        except UniversalImportError as err:
            self.report({"ERROR"}, str(err))
            return {"CANCELLED"}
        except Exception as e:
            self.report({"ERROR"}, "未知错误: {}".format(e))
            import traceback
            traceback.print_exc()
            return {"CANCELLED"}
        return {"FINISHED"}


class RDC_OT_cleanup_temp(Operator):
    bl_idname = "universal_rdc.cleanup"
    bl_label = "清理临时文件"
    bl_description = "删除导入过程中生成的临时文件夹（bin/texture/debug.log）"

    directory: StringProperty(subtype="DIR_PATH")

    def execute(self, context):
        from .universal_importer import cleanupTempFiles
        d = self.directory or os.path.dirname(bpy.data.filepath or "")
        if not d or not os.path.isdir(d):
            self.report({"ERROR"}, "请先指定目录")
            return {"CANCELLED"}

        count = cleanupTempFiles(d)
        if count > 0:
            self.report({"INFO"}, "已清理 {} 个临时文件夹".format(count))
        else:
            self.report({"INFO"}, "没有找到临时文件夹")
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


def menu_func_import(self, context):
    self.layout.operator(RDC_OT_import_universal.bl_idname, text="通用 RDC 文件 (.rdc)")


def register():
    bpy.utils.register_class(RDC_OT_import_universal)
    bpy.utils.register_class(RDC_OT_cleanup_temp)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(RDC_OT_cleanup_temp)
    bpy.utils.unregister_class(RDC_OT_import_universal)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
