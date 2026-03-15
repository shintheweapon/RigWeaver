"""
N-panel for the Blender Bone Utility addon.
Visible in the 3D Viewport sidebar when the active object is an armature.
"""
import bpy
from bpy.types import Panel


class VIEW3D_PT_bone_util(Panel):
    bl_label = "RigProxy"
    bl_idname = "VIEW3D_PT_bone_util"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RigProxy"

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'ARMATURE'

    def draw(self, context):
        layout = self.layout
        props = context.scene.bone_util_props
        mode = context.object.mode

        # ── Extract ────────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Extract Used Armature", icon='ARMATURE_DATA')

        if mode != 'OBJECT':
            row = box.row(align=True)
            row.label(text="Requires Object Mode", icon='INFO')
            box.operator("object.mode_set", text="Enter Object Mode", icon='OBJECT_DATA').mode = 'OBJECT'
        else:
            box.prop(props, "retarget_meshes")
            box.prop(props, "auto_bone_orientation")
            row = box.row()
            row.scale_y = 1.3
            row.operator("bone_util.extract_used_armature", icon='LINKED')

        layout.separator()

        # ── Generate Mesh ──────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Generate Mesh", icon='MESH_DATA')

        if mode != 'POSE':
            row = box.row(align=True)
            row.label(text="Requires Pose Mode", icon='INFO')
            box.operator("object.mode_set", text="Enter Pose Mode", icon='POSE_HLT').mode = 'POSE'
        else:
            box.prop(props, "mesh_individual_chains")
            if props.mesh_individual_chains:
                box.prop(props, "mesh_split_objects")
            box.prop(props, "close_mesh_loop")
            box.prop(props, "mesh_panel_resolution")
            box.prop(props, "mesh_ribbon_width")
            box.prop(props, "mesh_triangulate")
            row = box.row()
            row.scale_y = 1.3
            row.operator("bone_util.generate_mesh", icon='OUTLINER_OB_MESH')


class VIEW3D_PT_vg_select(Panel):
    """RigProxy — Vertex Group Multi-Select (active mesh in Edit Mode)."""
    bl_label      = "Vertex Group Select"
    bl_idname     = "VIEW3D_PT_vg_select"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category    = "RigProxy"

    @classmethod
    def poll(cls, context):
        return (context.object is not None
                and context.object.type == 'MESH'
                and context.object.mode == 'EDIT')

    def draw(self, context):
        import json
        layout = self.layout
        obj = context.object

        if not obj.vertex_groups:
            layout.label(text="No vertex groups", icon='INFO')
            return

        # Read-only: no data mutations here.
        selected: set[str] = set(json.loads(obj.vg_selected_groups))

        # All / None bulk buttons.
        row = layout.row(align=True)
        row.operator("bone_util.vg_select_all",  text="All")
        row.operator("bone_util.vg_select_none", text="None")

        # Per-group toggle buttons with checkbox icons.
        col = layout.column(align=True)
        for vg in obj.vertex_groups:
            icon = 'CHECKBOX_HLT' if vg.name in selected else 'CHECKBOX_DEHLT'
            col.operator(
                "bone_util.vg_toggle",
                text=vg.name,
                icon=icon,
            ).group_name = vg.name


def register():
    bpy.utils.register_class(VIEW3D_PT_bone_util)
    bpy.utils.register_class(VIEW3D_PT_vg_select)


def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_vg_select)
    bpy.utils.unregister_class(VIEW3D_PT_bone_util)
