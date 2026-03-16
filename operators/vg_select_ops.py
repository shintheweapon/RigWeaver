"""
Vertex-group multi-selection for RigProxy.

Selected group names are persisted as a JSON-encoded StringProperty on each
Object so draw() stays completely read-only.  All mutations happen inside
operators, which Blender allows unconditionally.
"""
from __future__ import annotations

import json

import bpy
import bmesh
from bpy.props import StringProperty
from bpy.types import Operator


# ---------------------------------------------------------------------------
# Core selection helper
# ---------------------------------------------------------------------------

def _apply_vg_selection(obj: bpy.types.Object) -> None:
    """
    Set Edit Mode vertex selection to exactly the checked vertex groups.

    A vertex is selected iff it belongs to at least one group whose name is
    in the JSON set stored on obj.vg_selected_groups.
    Requires obj to be a MESH in EDIT mode.
    """
    selected_names: set[str] = set(json.loads(obj.vg_selected_groups))
    selected_indices: set[int] = {
        obj.vertex_groups[n].index
        for n in selected_names
        if n in obj.vertex_groups
    }

    me = obj.data
    bm = bmesh.from_edit_mesh(me)
    deform_layer = bm.verts.layers.deform.active

    for vert in bm.verts:
        vert.select = (
            deform_layer is not None
            and any(gi in selected_indices for gi in vert[deform_layer].keys())
        )

    # Keep edges and faces consistent with the updated vertex selection.
    bm.select_flush_mode()
    bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)


# ---------------------------------------------------------------------------
# Per-group toggle operator
# ---------------------------------------------------------------------------

class BONE_OT_vg_toggle(Operator):
    """Toggle this vertex group in/out of the active selection set"""
    bl_idname = "bone_util.vg_toggle"
    bl_label  = "Toggle Vertex Group"
    bl_options = {'REGISTER', 'UNDO'}

    group_name: StringProperty(  # type: ignore[valid-type]
        name="Group Name",
        description="Name of the vertex group to toggle",
        default="",
    )

    @classmethod
    def poll(cls, context):
        return (context.object is not None
                and context.object.type == 'MESH'
                and context.object.mode == 'EDIT')

    def execute(self, context):
        obj = context.object
        selected: set[str] = set(json.loads(obj.vg_selected_groups))

        if self.group_name in selected:
            selected.discard(self.group_name)
        else:
            selected.add(self.group_name)

        obj.vg_selected_groups = json.dumps(sorted(selected))
        _apply_vg_selection(obj)
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Bulk operators (All / None)
# ---------------------------------------------------------------------------

class BONE_OT_vg_select_all(Operator):
    """Select vertices in all vertex groups"""
    bl_idname  = "bone_util.vg_select_all"
    bl_label   = "All"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.object is not None
                and context.object.type == 'MESH'
                and context.object.mode == 'EDIT')

    def execute(self, context):
        obj = context.object
        obj.vg_selected_groups = json.dumps(
            sorted(vg.name for vg in obj.vertex_groups)
        )
        _apply_vg_selection(obj)
        return {'FINISHED'}


class BONE_OT_vg_select_none(Operator):
    """Deselect all vertex groups"""
    bl_idname  = "bone_util.vg_select_none"
    bl_label   = "None"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.object is not None
                and context.object.type == 'MESH'
                and context.object.mode == 'EDIT')

    def execute(self, context):
        obj = context.object
        obj.vg_selected_groups = "[]"
        _apply_vg_selection(obj)
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (BONE_OT_vg_toggle, BONE_OT_vg_select_all, BONE_OT_vg_select_none)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    # JSON-encoded sorted list of selected vertex group names.
    bpy.types.Object.vg_selected_groups = StringProperty(
        name="VG Selected Groups",
        description="JSON list of vertex group names active in the RigProxy selector",
        default="[]",
    )


def unregister():
    if hasattr(bpy.types.Object, "vg_selected_groups"):
        del bpy.types.Object.vg_selected_groups
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
