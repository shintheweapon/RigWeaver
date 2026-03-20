"""
N-panel for the RigWeaver addon.
Visible in the 3D Viewport sidebar when the active object is an armature.
"""
import json

import bpy
from bpy.app.translations import pgettext_iface as iface_
from bpy.types import Panel

try:
    import numpy as _np
    _PANEL_NUMPY_OK = True
except ImportError:
    _PANEL_NUMPY_OK = False


class RIG_WEAVER_UL_vg_list(bpy.types.UIList):
    """Scrollable vertex-group list with checkbox toggle buttons."""
    bl_idname = "RIG_WEAVER_UL_vg_list"
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
            "rig_weaver.vg_toggle",
            text=vg.name, icon=chk, emboss=False,
        ).group_name = vg.name


class VIEW3D_PT_rig_weaver(Panel):
    bl_label = "RigWeaver"
    bl_idname = "VIEW3D_PT_rig_weaver"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RigWeaver"

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'ARMATURE'

    def draw(self, context):
        layout = self.layout
        props = context.scene.rig_weaver_props
        mode = context.object.mode

        # ── Extract ────────────────────────────────────────────────────────
        box = layout.box()
        row = box.row()
        row.prop(
            props, "ui_expand_extract",
            icon='TRIA_DOWN' if props.ui_expand_extract else 'TRIA_RIGHT',
            icon_only=True, emboss=False,
        )
        row.label(text=iface_("Extract Used Armature"), icon='ARMATURE_DATA')

        if props.ui_expand_extract:
            if mode != 'OBJECT':
                box.label(text=iface_("Requires Object Mode"), icon='INFO')
                box.operator(
                    "object.mode_set", text=iface_("Enter Object Mode"),
                    icon='OBJECT_DATA',
                ).mode = 'OBJECT'
            else:
                box.prop(props, "retarget_meshes")
                box.prop(props, "auto_bone_orientation")
                box.prop(props, "connect_child_bones")
                row = box.row()
                row.scale_y = 1.3
                row.operator("rig_weaver.extract_used_armature",
                             text=iface_("Extract Used Armature"), icon='LINKED')

        layout.separator()

        # ── Generate Mesh ──────────────────────────────────────────────────
        box = layout.box()
        row = box.row()
        row.prop(
            props, "ui_expand_generate",
            icon='TRIA_DOWN' if props.ui_expand_generate else 'TRIA_RIGHT',
            icon_only=True, emboss=False,
        )
        row.label(text=iface_("Generate Mesh"), icon='MESH_DATA')

        if props.ui_expand_generate:
            if mode != 'POSE':
                box.label(text=iface_("Requires Pose Mode"), icon='INFO')
                box.operator(
                    "object.mode_set", text=iface_("Enter Pose Mode"),
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

                # U/V resolution + interpolation controls (grouped by axis)
                if mesh_mode not in ('INDIVIDUAL', 'TREE'):
                    col = box.column()
                    col.use_property_split = True
                    col.prop(props, "mesh_bone_subdivisions")       # U Subdivisions (along chain)
                    col.prop(props, "mesh_row_interpolation")       # U Interpolation (along chain)
                    col.separator(factor=0.5)
                    col.prop(props, "mesh_panel_resolution")        # V Columns (between chains)
                    col.prop(props, "mesh_lateral_interpolation")   # V Interpolation (between chains)
                    if props.mesh_lateral_interpolation != 'LINEAR':
                        col.prop(props, "mesh_lateral_cr_strength", slider=True)  # V Strength
                else:
                    box.prop(props, "mesh_bone_subdivisions")

                # Ribbon width — not used in TREE mode
                if mesh_mode != 'TREE':
                    box.prop(props, "mesh_ribbon_width")

                # Output options — compact two-column toggle row
                row = box.row(align=True)
                row.prop(props, "mesh_triangulate", toggle=True)
                row.prop(props, "mesh_generate_uvs", toggle=True)

                box.separator(factor=0.5)

                # Rigging
                box.prop(props, "mesh_auto_rig")
                if props.mesh_auto_rig:
                    box.prop(props, "mesh_envelope_factor")
                    preview_icon = 'HIDE_OFF' if props.ui_envelope_preview_active else 'HIDE_ON'
                    box.operator(
                        "rig_weaver.preview_envelope_weights",
                        text=iface_("Preview Weight Radius"),
                        icon=preview_icon,
                    )

                # Subdivision Surface
                row = box.row(align=True)
                row.prop(props, "mesh_add_subsurf", toggle=True)
                if props.mesh_add_subsurf:
                    row.prop(props, "mesh_subsurf_levels")

                # Output name + action buttons
                box.prop(props, "mesh_output_name")
                box.prop(props, "mesh_set_parent")
                row = box.row(align=True)
                row.scale_y = 1.3
                row.operator("rig_weaver.generate_mesh",
                             text=iface_("Generate Proxy Mesh"), icon='OUTLINER_OB_MESH')
                row.operator("rig_weaver.update_mesh", text=iface_("Update Mesh"), icon='FILE_REFRESH')


class VIEW3D_PT_rig_from_mesh(Panel):
    """RigWeaver — Generate a bone cage armature from the active mesh."""
    bl_label      = "RigWeaver"
    bl_idname     = "VIEW3D_PT_rig_from_mesh"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category    = "RigWeaver"

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def draw(self, context):
        layout = self.layout
        props = context.scene.rig_weaver_props
        obj = context.object

        box = layout.box()
        row = box.row()
        row.prop(
            props, "ui_expand_rig_from_mesh",
            icon='TRIA_DOWN' if props.ui_expand_rig_from_mesh else 'TRIA_RIGHT',
            icon_only=True, emboss=False,
        )
        row.label(text=iface_("Generate Rig from Mesh"), icon='ARMATURE_DATA')

        if not props.ui_expand_rig_from_mesh:
            return

        if obj.mode != 'OBJECT':
            box.label(text=iface_("Requires Object Mode"), icon='INFO')
            box.operator(
                "object.mode_set", text=iface_("Enter Object Mode"),
                icon='OBJECT_DATA',
            ).mode = 'OBJECT'
            return

        # ── Algorithm ──────────────────────────────────────────────────────
        row = box.row(align=True)
        row.prop(props, "rig_chains")
        row.prop(props, "rig_bones_per_chain")

        box.prop(props, "rig_up_axis")

        if props.rig_up_axis == 'AUTO' and not _PANEL_NUMPY_OK:
            row = box.row()
            row.alert = True
            row.label(text=iface_("AUTO requires NumPy"), icon='ERROR')

        box.separator(factor=0.5)

        # ── Source mesh ────────────────────────────────────────────────────
        box.prop(props, "rig_auto_weights")
        if props.rig_auto_weights:
            box.prop(props, "rig_envelope_factor")
        box.prop(props, "rig_set_parent")

        box.separator(factor=0.5)

        # ── Output + actions ───────────────────────────────────────────────
        box.prop(props, "rig_output_name")

        preview_icon = 'HIDE_OFF' if props.ui_rig_preview_active else 'HIDE_ON'
        box.operator(
            "rig_weaver.preview_rig_from_mesh",
            text=iface_("Preview Rig"),
            icon=preview_icon,
        )

        row = box.row(align=True)
        row.scale_y = 1.3
        row.operator(
            "rig_weaver.generate_rig_from_mesh",
            text=iface_("Generate Rig"),
            icon='ARMATURE_DATA',
        )
        row.operator(
            "rig_weaver.update_rig_from_mesh",
            text=iface_("Update Rig"),
            icon='FILE_REFRESH',
        )


class VIEW3D_PT_vg_select(Panel):
    """RigWeaver — Vertex Group Multi-Select (active mesh in Edit Mode)."""
    bl_label      = "Vertex Group Select"
    bl_idname     = "VIEW3D_PT_vg_select"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category    = "RigWeaver"

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
            layout.label(text=iface_("Previewing mixed weights"), icon='HIDE_OFF')
            layout.operator(
                "rig_weaver.vg_preview_mix",
                text=iface_("Exit Preview"),
                icon='LOOP_BACK',
            )
            layout.separator()
            layout.operator(
                "rig_weaver.vg_mix_groups",
                text=iface_("Mix into Group"),
                icon='AUTOMERGE_ON',
            )
            return

        # ── Edit Mode ──────────────────────────────────────────────────────
        if not obj.vertex_groups:
            layout.label(text=iface_("No vertex groups"), icon='INFO')
            return

        # All / None bulk buttons.
        row = layout.row(align=True)
        row.operator("rig_weaver.vg_select_all",  text=iface_("All"))
        row.operator("rig_weaver.vg_select_none", text=iface_("None"))

        # Scrollable group list (filter rendered inside list header by draw_filter).
        layout.template_list(
            "RIG_WEAVER_UL_vg_list", "",
            obj, "vertex_groups",
            obj, "vg_active_index",
            rows=6, maxrows=12,
        )

        # ── Mix Checked Groups ─────────────────────────────────────────────
        layout.separator()
        box = layout.box()
        box.label(text=iface_("Mix Checked Groups"), icon='AUTOMERGE_ON')
        box.prop(obj, "vg_mix_blend_mode")
        preview_icon = 'HIDE_OFF' if obj.vg_mix_preview_active else 'HIDE_ON'
        box.operator(
            "rig_weaver.vg_preview_mix",
            text=iface_("Preview Mix"),
            icon=preview_icon,
        )
        box.prop_search(obj, "vg_mix_target_name", obj, "vertex_groups",
                        text="Target")
        box.prop(obj, "vg_mix_remove_srcs")
        row = box.row()
        row.scale_y = 1.3
        row.operator("rig_weaver.vg_mix_groups", text=iface_("Mix into Group"),
                     icon='AUTOMERGE_ON')


def register():
    bpy.utils.register_class(RIG_WEAVER_UL_vg_list)
    bpy.utils.register_class(VIEW3D_PT_rig_weaver)
    bpy.utils.register_class(VIEW3D_PT_rig_from_mesh)
    bpy.utils.register_class(VIEW3D_PT_vg_select)


def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_vg_select)
    bpy.utils.unregister_class(VIEW3D_PT_rig_from_mesh)
    bpy.utils.unregister_class(VIEW3D_PT_rig_weaver)
    bpy.utils.unregister_class(RIG_WEAVER_UL_vg_list)
