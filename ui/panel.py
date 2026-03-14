"""
N-panel for the Blender Bone Utility addon.
Visible in the 3D Viewport sidebar when the active object is an armature.
"""
import bpy
from bpy.types import Panel


class VIEW3D_PT_bone_util(Panel):
    bl_label = "Bone Utility"
    bl_idname = "VIEW3D_PT_bone_util"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Bone Util"

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'ARMATURE'

    def draw(self, context):
        layout = self.layout
        props = context.scene.bone_util_props
        mode = context.object.mode

        # ── Analyze ────────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Analyze Bones", icon='BONE_DATA')

        if mode != 'OBJECT':
            row = box.row(align=True)
            row.label(text="Requires Object Mode", icon='INFO')
            box.operator("object.mode_set", text="Enter Object Mode", icon='OBJECT_DATA').mode = 'OBJECT'
        else:
            box.prop(props, "color_code_bones")
            row = box.row()
            row.scale_y = 1.3
            row.operator("bone_util.analyze_unused", icon='ZOOM_ALL')

        layout.separator()

        # ── Extract ────────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Extract Used Armature", icon='ARMATURE_DATA')

        if mode != 'OBJECT':
            row = box.row(align=True)
            row.label(text="Requires Object Mode", icon='INFO')
        else:
            box.prop(props, "retarget_meshes")
            sub = box.column()
            sub.label(text="Re-analyses if no cache.", icon='INFO')
            row = box.row()
            row.scale_y = 1.3
            row.operator("bone_util.extract_used_armature", icon='LINKED')


def register():
    bpy.utils.register_class(VIEW3D_PT_bone_util)


def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_bone_util)
