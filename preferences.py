import bpy

addon_idname = __package__


def getPreferences(context):
    return context.preferences.addons[addon_idname].preferences


class UniversalRDCAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = addon_idname

    tmp_dir: bpy.props.StringProperty(
        name="临时目录",
        subtype="DIR_PATH",
        default="",
        description="存放中间文件的目录，留空则使用 rdc 文件所在目录"
    )

    debug_info: bpy.props.BoolProperty(
        name="调试信息",
        default=False,
        description="在控制台输出详细调试信息"
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="临时目录用于存放中间文件和纹理贴图。")
        layout.prop(self, "tmp_dir")
        layout.prop(self, "debug_info")


classes = (UniversalRDCAddonPreferences,)

register, unregister = bpy.utils.register_classes_factory(classes)
