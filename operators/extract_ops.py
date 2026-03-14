"""
Operator: Extract a reduced armature containing only the bones that
have vertex weights (i.e. actually deform a mesh).

NOTE: edit_bone.collections is NOT accessed at all in this operator.
Calling len(edit_bone.collections) triggers EditBone_collections_begin ->
rna_Bone_collections_get which causes a C-level EXCEPTION_ACCESS_VIOLATION
that cannot be caught by Python try/except. The reduced armature is a clean
skeleton; run Analyze afterward to get BoneUtil_* collections on it.
"""
from __future__ import annotations
import json

import bpy
from bpy.types import Operator
from mathutils import Vector

from .analyze_ops import _collect_weighted_names


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _topo_sort(
    used_names: set[str],
    parent_name_map: dict[str, str | None],
) -> list[str]:
    """Return used bone names in parent-before-child order."""
    ordered: list[str] = []
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        visited.add(name)
        parent_name = parent_name_map.get(name)
        if parent_name and parent_name in used_names:
            visit(parent_name)
        ordered.append(name)

    for name in used_names:
        visit(name)
    return ordered


def _find_used_parent(
    name: str,
    parent_name_map: dict[str, str | None],
    used_names: set[str],
) -> str | None:
    """
    Walk up the hierarchy from `name` and return the nearest ancestor
    whose name is in used_names, or None if no such ancestor exists.
    The bone itself is not considered.
    """
    current = parent_name_map.get(name)
    while current is not None:
        if current in used_names:
            return current
        current = parent_name_map.get(current)
    return None


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------

class BONE_OT_extract_used_armature(Operator):
    """Create a new armature containing only bones that have vertex weights"""
    bl_idname = "bone_util.extract_used_armature"
    bl_label = "Extract Used Armature"
    bl_description = (
        "Build a reduced armature from bones that actually deform meshes. "
        "Optionally retarget mesh Armature modifiers to the new armature."
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            context.object is not None
            and context.object.type == 'ARMATURE'
            and context.object.mode == 'OBJECT'
        )

    def execute(self, context):
        source_obj = context.object
        props = context.scene.bone_util_props

        # --- Determine used bone names ---
        # Reuse cached result if available, otherwise re-analyse
        cached = json.loads(props.last_weighted_bones)
        if cached:
            used_names: set[str] = set(cached)
        else:
            used_names = _collect_weighted_names(source_obj)

        if not used_names:
            self.report({'ERROR'}, "Bone Util: No bones with vertex weights found.")
            return {'CANCELLED'}

        # Filter to bones that actually exist in the armature
        existing = {b.name for b in source_obj.data.bones}
        used_names = used_names & existing

        if not used_names:
            self.report({'ERROR'}, "Bone Util: No matching bones found in armature.")
            return {'CANCELLED'}

        # --- Build parent name map and topo-sorted list BEFORE any mode switches ---
        # bpy.types.Bone references become stale after mode_set(); snapshot as
        # plain Python strings now so helpers never touch live Blender data later.
        parent_name_map: dict[str, str | None] = {
            b.name: b.parent.name if b.parent else None
            for b in source_obj.data.bones
        }
        ordered = _topo_sort(used_names, parent_name_map)

        # --- Snapshot source edit-bone data ---
        # Must enter Edit Mode on source to read edit_bones (roll is only on EditBone).
        bpy.ops.object.select_all(action='DESELECT')
        source_obj.select_set(True)
        context.view_layer.objects.active = source_obj
        bpy.ops.object.mode_set(mode='EDIT')

        source_edit_data: dict[str, dict] = {}
        for name in ordered:
            try:
                eb = source_obj.data.edit_bones[name]
                source_edit_data[name] = {
                    'head': eb.head.copy(),
                    'tail': eb.tail.copy(),
                    'roll': eb.roll,
                    'use_connect': eb.use_connect,
                    'parent_name': eb.parent.name if eb.parent else None,
                }
            except (KeyError, AttributeError):
                pass

        bpy.ops.object.mode_set(mode='OBJECT')

        # --- Create new armature object ---
        new_arm_data = bpy.data.armatures.new(f"{source_obj.data.name}_Reduced")
        new_obj = bpy.data.objects.new(f"{source_obj.name}_Reduced", new_arm_data)

        for coll in source_obj.users_collection:
            coll.objects.link(new_obj)

        new_obj.location = source_obj.location.copy()
        new_obj.rotation_euler = source_obj.rotation_euler.copy()
        new_obj.rotation_quaternion = source_obj.rotation_quaternion.copy()
        new_obj.scale = source_obj.scale.copy()

        # --- Populate bones in Edit Mode on the new armature ---
        bpy.ops.object.select_all(action='DESELECT')
        new_obj.select_set(True)
        context.view_layer.objects.active = new_obj
        bpy.ops.object.mode_set(mode='EDIT')

        new_bone_map: dict[str, bpy.types.EditBone] = {}

        for name in ordered:
            data = source_edit_data.get(name)
            if data is None:
                continue

            new_eb = new_arm_data.edit_bones.new(name)
            new_eb.head = data['head']
            new_eb.tail = data['tail']
            new_eb.roll = data['roll']

            # Find nearest weighted ancestor (may skip non-weighted intermediates)
            direct_parent = data['parent_name']
            used_parent = _find_used_parent(name, parent_name_map, used_names)
            if used_parent and used_parent in new_bone_map:
                new_eb.parent = new_bone_map[used_parent]
                # Keep use_connect only when the direct parent is the used parent
                # (no intermediate bones were skipped)
                new_eb.use_connect = (
                    data['use_connect'] if used_parent == direct_parent else False
                )
            else:
                new_eb.use_connect = False

            # NOTE: edit_bone.collections is deliberately NOT accessed here.
            # Any access (len, iteration) triggers a C-level crash in Blender 4.5.

            new_bone_map[name] = new_eb

        # --- Auto bone orientation (optional) ---
        # Matches Blender FBX import "Automatic Bone Orientation":
        # Step 1: point non-end bone tails toward the average child head position.
        # Step 2: recalculate roll so local Z aligns with global +Z.
        if props.auto_bone_orientation:
            for name, new_eb in new_bone_map.items():
                children = [c for c in new_arm_data.edit_bones if c.parent == new_eb]
                if not children:
                    continue
                avg_child_head = sum(
                    (c.head for c in children), Vector((0.0, 0.0, 0.0))
                ) / len(children)
                direction = avg_child_head - new_eb.head
                if direction.length > 1e-6:
                    bone_len = (new_eb.tail - new_eb.head).length
                    new_eb.tail = new_eb.head + direction.normalized() * bone_len

            for eb in new_arm_data.edit_bones:
                eb.select = True
            with context.temp_override(active_object=new_obj):
                bpy.ops.armature.calculate_roll(type='GLOBAL_POS_Z')

        # --- Return to Object Mode ---
        bpy.ops.object.mode_set(mode='OBJECT')

        bpy.ops.object.select_all(action='DESELECT')
        new_obj.select_set(True)
        context.view_layer.objects.active = new_obj

        bone_count = len(new_bone_map)
        self.report({'INFO'}, f"Bone Util: Created '{new_obj.name}' with {bone_count} bone(s).")

        # --- Retarget meshes ---
        if props.retarget_meshes:
            retarget_count = 0
            for obj in context.scene.objects:
                if obj.type != 'MESH':
                    continue
                for mod in obj.modifiers:
                    if mod.type == 'ARMATURE' and mod.object == source_obj:
                        mod.object = new_obj
                        retarget_count += 1
                        # Also reparent the mesh if it is currently parented
                        # to the source armature, preserving world transform.
                        if obj.parent == source_obj:
                            world_mat = obj.matrix_world.copy()
                            obj.parent = new_obj
                            obj.matrix_parent_inverse = (
                                new_obj.matrix_world.inverted() @ world_mat
                            )
                        break
            if retarget_count:
                self.report(
                    {'INFO'},
                    f"Bone Util: Retargeted {retarget_count} mesh(es) to '{new_obj.name}'.",
                )

        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (BONE_OT_extract_used_armature,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
