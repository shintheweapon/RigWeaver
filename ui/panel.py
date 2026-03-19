"""
N-panel for the Blender Bone Utility addon.
Visible in the 3D Viewport sidebar when the active object is an armature.
"""
import json

import bpy
from bpy.types import Panel


class BONE_UL_vg_list(bpy.types.UIList):
    """Scrollable vertex-group list with checkbox toggle buttons."""
    bl_idname = "BONE_UL_vg_list"
    use_filter_show = True

    def draw_filter(self, context, layout):
        layout.prop(self, "filter_name", text="", icon='VIEWZOOM')

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index=0):
        obj = data
        vg = item
        selected = set(json.loads(obj.vg_selected_groups))
        chk = 'CHECKBOX_HLT' if vg.name in selected else 'CHECKBOX_DEHLT'
        layout.operator(
            "bone_util.vg_toggle",
            text=vg.name, icon=chk, emboss=False,
        ).group_name = vg.name


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
        row = box.row()
        row.prop(
            props, "ui_expand_extract",
            icon='TRIA_DOWN' if props.ui_expand_extract else 'TRIA_RIGHT',
            icon_only=True, emboss=False,
        )
        row.label(text="Extract Used Armature", icon='ARMATURE_DATA')

        if props.ui_expand_extract:
            if mode != 'OBJECT':
                box.label(text="Requires Object Mode", icon='INFO')
                box.operator(
                    "object.mode_set", text="Enter Object Mode",
                    icon='OBJECT_DATA',
                ).mode = 'OBJECT'
            else:
                box.prop(props, "retarget_meshes")
                box.prop(props, "auto_bone_orientation")
                box.prop(props, "connect_child_bones")
                row = box.row()
                row.scale_y = 1.3
                row.operator("bone_util.extract_used_armature", icon='LINKED')

        layout.separator()

        # ── Generate Mesh ──────────────────────────────────────────────────
        box = layout.box()
        row = box.row()
        row.prop(
            props, "ui_expand_generate",
            icon='TRIA_DOWN' if props.ui_expand_generate else 'TRIA_RIGHT',
            icon_only=True, emboss=False,
        )
        row.label(text="Generate Mesh", icon='MESH_DATA')

        if props.ui_expand_generate:
            if mode != 'POSE':
                box.label(text="Requires Pose Mode", icon='INFO')
                box.operator(
                    "object.mode_set", text="Enter Pose Mode",
                    icon='POSE_HLT',
                ).mode = 'POSE'
            else:
                mesh_mode = props.mesh_mode
                box.prop(props, "mesh_mode")

                # Mode-specific options
                if mesh_mode == 'INDIVIDUAL':
                    box.prop(props, "mesh_split_objects")
                elif mesh_mode == 'SURFACE_SPLIT':
                    box.prop(props, "mesh_strip_gap_factor")
                elif mesh_mode == 'TREE':
                    box.prop(props, "mesh_tree_alpha_factor")

                # Resolution — compact two-column row when both apply
                if mesh_mode not in ('INDIVIDUAL', 'TREE'):
                    row = box.row(align=True)
                    row.prop(props, "mesh_panel_resolution")
                    row.prop(props, "mesh_bone_subdivisions")
                else:
                    box.prop(props, "mesh_bone_subdivisions")

                # Ribbon width — not used in TREE mode
                if mesh_mode != 'TREE':
                    box.prop(props, "mesh_ribbon_width")

                # Output options — compact two-column toggle row
                row = box.row(align=True)
                row.prop(props, "mesh_triangulate", toggle=True)
                row.prop(props, "mesh_generate_uvs", toggle=True)

                # Envelope preview toggle
                preview_icon = 'HIDE_OFF' if props.ui_envelope_preview_active else 'HIDE_ON'
                box.operator(
                    "bone_util.preview_envelope_weights",
                    text="Preview Weight Radius",
                    icon=preview_icon,
                )

                # Rigging
                box.prop(props, "mesh_auto_rig")
                if props.mesh_auto_rig:
                    box.prop(props, "mesh_envelope_factor")

                # Action buttons
                row = box.row(align=True)
                row.scale_y = 1.3
                row.operator("bone_util.generate_mesh", icon='OUTLINER_OB_MESH')
                row.operator("bone_util.update_mesh", text="Update", icon='FILE_REFRESH')


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
                and context.object.mode in ('EDIT', 'WEIGHT_PAINT'))

    def draw(self, context):
        layout = self.layout
        obj = context.object

        # ── Weight Paint mode: preview is active ───────────────────────────
        if obj.mode == 'WEIGHT_PAINT':
            layout.label(text="Previewing mixed weights", icon='HIDE_OFF')
            layout.operator(
                "bone_util.vg_preview_mix",
                text="Exit Preview",
                icon='LOOP_BACK',
            )
            layout.separator()
            layout.operator(
                "bone_util.vg_mix_groups",
                text="Mix into Group",
                icon='AUTOMERGE_ON',
            )
            return

        # ── Edit Mode ──────────────────────────────────────────────────────
        if not obj.vertex_groups:
            layout.label(text="No vertex groups", icon='INFO')
            return

        # All / None bulk buttons.
        row = layout.row(align=True)
        row.operator("bone_util.vg_select_all",  text="All")
        row.operator("bone_util.vg_select_none", text="None")

        # Scrollable group list (filter rendered inside list header by draw_filter).
        layout.template_list(
            "BONE_UL_vg_list", "",
            obj, "vertex_groups",
            obj, "vg_active_index",
            rows=6, maxrows=12,
        )

        # ── Mix Checked Groups ─────────────────────────────────────────────
        layout.separator()
        box = layout.box()
        box.label(text="Mix Checked Groups", icon='AUTOMERGE_ON')
        box.prop(obj, "vg_mix_blend_mode")
        preview_icon = 'HIDE_OFF' if obj.vg_mix_preview_active else 'HIDE_ON'
        box.operator(
            "bone_util.vg_preview_mix",
            text="Preview Mix",
            icon=preview_icon,
        )
        box.prop_search(obj, "vg_mix_target_name", obj, "vertex_groups",
                        text="Target")
        box.prop(obj, "vg_mix_remove_srcs")
        row = box.row()
        row.scale_y = 1.3
        row.operator("bone_util.vg_mix_groups", text="Mix into Group",
                     icon='AUTOMERGE_ON')


def register():
    bpy.utils.register_class(BONE_UL_vg_list)
    bpy.utils.register_class(VIEW3D_PT_bone_util)
    bpy.utils.register_class(VIEW3D_PT_vg_select)


def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_vg_select)
    bpy.utils.unregister_class(VIEW3D_PT_bone_util)
    bpy.utils.unregister_class(BONE_UL_vg_list)
