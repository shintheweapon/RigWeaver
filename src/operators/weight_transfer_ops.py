"""
Weight transfer for RigWeaver: copy deform bone weights from a source mesh to
the active mesh with Blender's Data Transfer.

Blender offers "Deform Pose Bones" as a Data Transfer source only while the
armature is in Pose Mode, so the transfer runs from a temporary copy of the
source that holds only the deform bone groups, with no modifiers and no
parent. The copy's rest shape is used, and same-name groups on the target are
replaced while every other target group stays.
"""
from __future__ import annotations

import bpy
from bpy.types import Operator

from .rig_from_mesh_ops import _poll_active_mesh


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _source_armatures(src: bpy.types.Object) -> list[bpy.types.Object]:
    """
    Return the armatures that deform a mesh object.

    Parameters
    ----------
    src : bpy.types.Object
        The mesh object.

    Returns
    -------
    list of bpy.types.Object
        The objects of its Armature modifiers, in stack order, then its parent
        when that is an armature with parent type Armature. No duplicates.
    """
    armatures = []
    for mod in src.modifiers:
        if mod.type == 'ARMATURE' and mod.object is not None and mod.object not in armatures:
            armatures.append(mod.object)
    parent = src.parent
    if (parent is not None and parent.type == 'ARMATURE'
            and src.parent_type == 'ARMATURE' and parent not in armatures):
        armatures.append(parent)
    return armatures


def _deform_group_names(src: bpy.types.Object) -> set[str]:
    """
    Return the source's vertex groups that belong to deform bones.

    Parameters
    ----------
    src : bpy.types.Object
        The mesh object.

    Returns
    -------
    set of str
        Names of bones with Deform on, in any armature of
        ``_source_armatures``, that are also vertex groups on ``src``.
    """
    bone_names = {
        bone.name
        for armature in _source_armatures(src)
        for bone in armature.data.bones
        if bone.use_deform
    }
    return {vg.name for vg in src.vertex_groups if vg.name in bone_names}


def _transfer_bone_weights(
    context: bpy.types.Context,
    src: bpy.types.Object,
    tgt: bpy.types.Object,
    vert_mapping: str,
) -> list[str]:
    """
    Copy the source's deform bone weights to the target by group name.

    Parameters
    ----------
    context : bpy.types.Context
        The current context; the temporary copy is linked to its scene.
    src : bpy.types.Object
        Source mesh object.
    tgt : bpy.types.Object
        Target mesh object; same-name groups are replaced, other groups stay.
    vert_mapping : str
        A ``vert_mapping`` value of ``bpy.ops.object.data_transfer``.

    Returns
    -------
    list of str
        The transferred group names, sorted.
    """
    names = _deform_group_names(src)
    tmp = src.copy()
    tmp.data = src.data.copy()
    # Rest shape in place: no deformation, same world transform
    tmp.modifiers.clear()
    matrix = src.matrix_world.copy()
    tmp.parent = None
    tmp.matrix_world = matrix
    context.scene.collection.objects.link(tmp)
    try:
        for vg in list(tmp.vertex_groups):
            if vg.name not in names:
                tmp.vertex_groups.remove(vg)
        with context.temp_override(
            active_object=tmp,
            object=tmp,
            selected_objects=[tmp, tgt],
            selected_editable_objects=[tgt],
        ):
            bpy.ops.object.data_transfer(
                data_type='VGROUP_WEIGHTS',
                use_create=True,
                vert_mapping=vert_mapping,
                layers_select_src='ALL',
                layers_select_dst='NAME',
                mix_mode='REPLACE',
            )
    finally:
        mesh = tmp.data
        bpy.data.objects.remove(tmp, do_unlink=True)
        bpy.data.meshes.remove(mesh)
    return sorted(names)


def _normalize_groups(obj: bpy.types.Object, names: list[str]) -> None:
    """
    Scale the given groups' weights on each vertex so they add up to 1.

    Parameters
    ----------
    obj : bpy.types.Object
        Mesh object, in Object Mode.
    names : list of str
        Vertex group names to normalise together. Other groups, and vertices
        with no weight in these groups, stay as they are.
    """
    groups = {obj.vertex_groups[n].index: obj.vertex_groups[n] for n in names
              if n in obj.vertex_groups}
    for v in obj.data.vertices:
        weights = [(g.group, g.weight) for g in v.groups if g.group in groups]
        total = sum(w for _, w in weights)
        if total <= 0.0:
            continue
        for index, w in weights:
            groups[index].add([v.index], w / total, 'REPLACE')


def _ensure_armature_modifier(obj: bpy.types.Object, armature: bpy.types.Object) -> None:
    """
    Make sure an Armature modifier on ``obj`` points at ``armature``.

    Parameters
    ----------
    obj : bpy.types.Object
        Mesh object.
    armature : bpy.types.Object
        The armature to deform with. An Armature modifier that already points at
        it is kept; otherwise one with no object gets it, or a new "Armature"
        modifier is added. Other Armature modifiers are not removed.
    """
    mods = [m for m in obj.modifiers if m.type == 'ARMATURE']
    if any(m.object == armature for m in mods):
        return
    empty = next((m for m in mods if m.object is None), None)
    if empty is not None:
        empty.object = armature
        return
    obj.modifiers.new(name="Armature", type='ARMATURE').object = armature


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------

class BONE_OT_transfer_weights(Operator):
    """Copy deform bone weights from the source mesh to the active mesh"""
    bl_idname = "rig_weaver.transfer_weights"
    bl_label = "Transfer Weights"
    bl_description = (
        "Copy the source mesh's deform bone weights to the active mesh, matched by "
        "group name. Other groups on the active mesh are kept."
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _poll_active_mesh(context)

    def execute(self, context):
        props = context.scene.rig_weaver_props
        tgt = context.object
        src = props.transfer_source

        if src is None:
            self.report({'ERROR'}, "RigWeaver: Choose a source mesh.")
            return {'CANCELLED'}
        if src == tgt:
            self.report({'ERROR'}, "RigWeaver: The source must be another mesh.")
            return {'CANCELLED'}
        armatures = _source_armatures(src)
        if not armatures:
            self.report({'ERROR'}, "RigWeaver: The source mesh has no armature.")
            return {'CANCELLED'}
        if not _deform_group_names(src):
            self.report({'ERROR'}, "RigWeaver: The source mesh has no deform bone weights.")
            return {'CANCELLED'}

        names = _transfer_bone_weights(context, src, tgt, props.transfer_vert_mapping)
        if props.transfer_normalize:
            _normalize_groups(tgt, names)
        if props.transfer_add_armature:
            _ensure_armature_modifier(tgt, armatures[0])

        self.report(
            {'INFO'},
            f"RigWeaver: Transferred {len(names)} group(s) from '{src.name}'.",
        )
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (BONE_OT_transfer_weights,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
