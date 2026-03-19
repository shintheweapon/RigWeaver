"""
Vertex-group multi-selection and weight mixing for RigProxy.

Selected group names are persisted as a JSON-encoded StringProperty on each
Object so draw() stays completely read-only.  All mutations happen inside
operators, which Blender allows unconditionally.
"""
from __future__ import annotations

import json

import bpy
import bmesh
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty
from bpy.types import Operator

# Name of the temporary vertex group used for mix preview.
_PREVIEW_GROUP = "_RigProxy_Preview"


def _load_selected(obj) -> set[str]:
    """Return the checked group names from obj, or an empty set on corrupt data."""
    try:
        return set(json.loads(obj.vg_selected_groups))
    except (json.JSONDecodeError, TypeError, ValueError):
        return set()


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
    selected_names: set[str] = _load_selected(obj)
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

    bm.select_flush_mode()
    bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)


# ---------------------------------------------------------------------------
# Mix weight helpers
# ---------------------------------------------------------------------------

def _compute_mix_weights(
    obj: bpy.types.Object,
    selected_names: set[str],
    blend_mode: str,
) -> dict[int, float]:
    """
    Return {vertex_index: weight} for the blended result.
    Must be called in Object Mode (reads obj.data.vertices).
    Vertices not in any source group are absent from the result (= weight 0).
    """
    indices: set[int] = {
        obj.vertex_groups[n].index
        for n in selected_names
        if n in obj.vertex_groups
    }
    result: dict[int, float] = {}
    for v in obj.data.vertices:
        ws = [g.weight for g in v.groups if g.group in indices]
        if not ws:
            continue
        if   blend_mode == 'MAX':     result[v.index] = max(ws)
        elif blend_mode == 'AVERAGE': result[v.index] = sum(ws) / len(ws)
        elif blend_mode == 'ADD':     result[v.index] = min(sum(ws), 1.0)
        elif blend_mode == 'MIN':     result[v.index] = min(ws)
    # Clamp all results to the valid Blender weight range [0.0, 1.0]
    result = {vi: max(0.0, min(1.0, w)) for vi, w in result.items()}
    return result


def _write_group_weights(
    obj: bpy.types.Object,
    vg: bpy.types.VertexGroup,
    weights: dict[int, float],
) -> None:
    """
    Overwrite vg entirely with the given {vertex_index: weight} dict.
    Must be called in Object Mode.
    """
    vg.remove(list(range(len(obj.data.vertices))))
    for vi, w in weights.items():
        vg.add([vi], w, 'REPLACE')


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
        selected: set[str] = _load_selected(obj)

        if self.group_name in selected:
            selected.discard(self.group_name)
        else:
            selected.add(self.group_name)

        obj.vg_selected_groups = json.dumps(sorted(selected))
        _apply_vg_selection(obj)
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Bulk select operators (All / None)
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
# Mix preview operator
# ---------------------------------------------------------------------------

class BONE_OT_vg_preview_mix(Operator):
    """Toggle a live Weight Paint preview of the blended vertex group weights"""
    bl_idname  = "bone_util.vg_preview_mix"
    bl_label   = "Preview Mix"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.object is not None
                and context.object.type == 'MESH'
                and context.object.mode in ('EDIT', 'WEIGHT_PAINT'))

    def execute(self, context):
        obj = context.object

        if obj.vg_mix_preview_active:
            # --- Toggle OFF: exit Weight Paint, remove temp group -----------
            bpy.ops.object.mode_set(mode='EDIT')
            if _PREVIEW_GROUP in obj.vertex_groups:
                obj.vertex_groups.remove(obj.vertex_groups[_PREVIEW_GROUP])
            obj.vg_mix_preview_active = False
        else:
            # --- Toggle ON: compute mix, enter Weight Paint -----------------
            selected_names: set[str] = _load_selected(obj)
            if not selected_names:
                self.report({'WARNING'}, "RigProxy: No groups checked.")
                return {'CANCELLED'}

            bpy.ops.object.mode_set(mode='OBJECT')

            weights = _compute_mix_weights(obj, selected_names,
                                           obj.vg_mix_blend_mode)

            # Replace existing preview group cleanly.
            if _PREVIEW_GROUP in obj.vertex_groups:
                obj.vertex_groups.remove(obj.vertex_groups[_PREVIEW_GROUP])
            preview_vg = obj.vertex_groups.new(name=_PREVIEW_GROUP)
            _write_group_weights(obj, preview_vg, weights)

            obj.vertex_groups.active = preview_vg
            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
            obj.vg_mix_preview_active = True

        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Mix into group operator
# ---------------------------------------------------------------------------

class BONE_OT_vg_mix_groups(Operator):
    """Merge checked vertex groups into a single target group"""
    bl_idname  = "bone_util.vg_mix_groups"
    bl_label   = "Mix into Group"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.object is not None
                and context.object.type == 'MESH'
                and context.object.mode in ('EDIT', 'WEIGHT_PAINT'))

    def execute(self, context):
        obj = context.object
        selected_names: set[str] = _load_selected(obj)

        if not selected_names:
            self.report({'WARNING'}, "RigProxy: No groups checked.")
            return {'CANCELLED'}

        bpy.ops.object.mode_set(mode='OBJECT')

        weights = _compute_mix_weights(obj, selected_names,
                                       obj.vg_mix_blend_mode)

        target_name = obj.vg_mix_target_name.strip() or "Mixed"
        target_vg = (obj.vertex_groups.get(target_name)
                     or obj.vertex_groups.new(name=target_name))
        _write_group_weights(obj, target_vg, weights)

        # Clean up preview group and flag.
        if _PREVIEW_GROUP in obj.vertex_groups:
            obj.vertex_groups.remove(obj.vertex_groups[_PREVIEW_GROUP])
        obj.vg_mix_preview_active = False

        if obj.vg_mix_remove_srcs:
            for name in selected_names:
                if name in obj.vertex_groups and name != target_name:
                    obj.vertex_groups.remove(obj.vertex_groups[name])
            obj.vg_selected_groups = "[]"

        bpy.ops.object.mode_set(mode='EDIT')
        self.report(
            {'INFO'},
            f"RigProxy: Mixed {len(selected_names)} group(s) into '{target_name}'.",
        )
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    BONE_OT_vg_toggle,
    BONE_OT_vg_select_all,
    BONE_OT_vg_select_none,
    BONE_OT_vg_preview_mix,
    BONE_OT_vg_mix_groups,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # JSON-encoded sorted list of selected vertex group names.
    bpy.types.Object.vg_selected_groups = StringProperty(
        name="VG Selected Groups",
        description="JSON list of vertex group names active in the RigProxy selector",
        default="[]",
    )
    bpy.types.Object.vg_mix_blend_mode = EnumProperty(
        name="Blend Mode",
        description="How to combine weights from multiple groups",
        items=[
            ('MAX',     "Max",     "Strongest weight wins"),
            ('AVERAGE', "Average", "Mean of all weights"),
            ('ADD',     "Add",     "Sum, clamped to 1.0"),
            ('MIN',     "Min",     "Weakest weight wins"),
        ],
        default='ADD',
    )
    bpy.types.Object.vg_mix_target_name = StringProperty(
        name="Target Group",
        description="Name for the new merged vertex group",
        default="Mixed",
    )
    bpy.types.Object.vg_mix_remove_srcs = BoolProperty(
        name="Remove Source Groups",
        description="Delete the checked source groups after mixing",
        default=False,
    )
    bpy.types.Object.vg_mix_preview_active = BoolProperty(
        name="Preview Active",
        description="Whether the mix preview is currently displayed",
        default=False,
    )
    bpy.types.Object.vg_active_index = IntProperty(
        name="VG Active Index",
        description="Active index for vertex group UIList",
        default=0,
    )


def unregister():
    for attr in (
        "vg_selected_groups",
        "vg_mix_blend_mode",
        "vg_mix_target_name",
        "vg_mix_remove_srcs",
        "vg_mix_preview_active",
        "vg_active_index",
    ):
        if hasattr(bpy.types.Object, attr):
            delattr(bpy.types.Object, attr)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
