"""
Vertex-group multi-selection for RigProxy.

Stores a per-object checkbox state for every vertex group and updates the
Edit Mode vertex selection via bmesh whenever a checkbox is toggled.
"""
from __future__ import annotations

import bpy
import bmesh
from bpy.props import BoolProperty, CollectionProperty
from bpy.types import Operator, PropertyGroup


# ---------------------------------------------------------------------------
# Core selection helper
# ---------------------------------------------------------------------------

def _apply_vg_selection(obj: bpy.types.Object) -> None:
    """
    Set Edit Mode vertex selection to match the checked vertex groups.

    A vertex is selected if it belongs to at least one checked group.
    All vertices not in any checked group are deselected.
    Requires the object to be a MESH in EDIT mode.
    """
    me = obj.data
    bm = bmesh.from_edit_mesh(me)
    deform_layer = bm.verts.layers.deform.active

    selected_indices: set[int] = {
        obj.vertex_groups[item.name].index
        for item in obj.vg_selection_items
        if item.selected and item.name in obj.vertex_groups
    }

    for vert in bm.verts:
        if deform_layer is not None:
            vert.select = any(gi in selected_indices
                              for gi in vert[deform_layer].keys())
        else:
            vert.select = False

    # Keep edges and faces consistent with the updated vertex selection.
    bm.select_flush_mode()
    bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)


# ---------------------------------------------------------------------------
# Per-group state PropertyGroup
# ---------------------------------------------------------------------------

def _on_toggle(self, context: bpy.types.Context) -> None:  # type: ignore[override]
    obj = context.object
    if obj and obj.type == 'MESH' and obj.mode == 'EDIT':
        _apply_vg_selection(obj)


class VGSelectionItem(PropertyGroup):
    """Checkbox state for one vertex group on an object."""
    # `name` is the built-in StringProperty inherited from PropertyGroup.
    # It is used as the vertex group name key — no extra field needed.
    selected: BoolProperty(  # type: ignore[valid-type]
        name="",
        description="Include this vertex group in the selection",
        default=False,
        update=_on_toggle,
    )


# ---------------------------------------------------------------------------
# Bulk operators (All / None)
# ---------------------------------------------------------------------------

class BONE_OT_vg_select_all(Operator):
    """Select all vertex groups"""
    bl_idname = "bone_util.vg_select_all"
    bl_label = "All"
    bl_description = "Select vertices in all vertex groups"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.object is not None
                and context.object.type == 'MESH'
                and context.object.mode == 'EDIT')

    def execute(self, context):
        obj = context.object
        # Silence per-item update callbacks; apply once at the end.
        for item in obj.vg_selection_items:
            # Bypass update by writing to the underlying RNA directly.
            item["selected"] = True
        _apply_vg_selection(obj)
        # Force panel redraw so checkboxes update visually.
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}


class BONE_OT_vg_select_none(Operator):
    """Deselect all vertex groups"""
    bl_idname = "bone_util.vg_select_none"
    bl_label = "None"
    bl_description = "Deselect vertices in all vertex groups"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.object is not None
                and context.object.type == 'MESH'
                and context.object.mode == 'EDIT')

    def execute(self, context):
        obj = context.object
        for item in obj.vg_selection_items:
            item["selected"] = False
        _apply_vg_selection(obj)
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (VGSelectionItem, BONE_OT_vg_select_all, BONE_OT_vg_select_none)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.vg_selection_items = CollectionProperty(
        type=VGSelectionItem,
    )


def unregister():
    if hasattr(bpy.types.Object, "vg_selection_items"):
        del bpy.types.Object.vg_selection_items
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
