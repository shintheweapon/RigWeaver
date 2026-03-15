"""
Operator: Generate a low-poly surface mesh from selected pose bones.

Intended for cloth / softbody simulation setups. No vertex groups or
weights are created — the mesh is plain geometry that follows the bone
positions at the moment of generation.

Each selected bone chain produces one quad-strip ribbon. Multiple chains
are all merged into a single mesh object.
"""
from __future__ import annotations

from mathutils import Matrix, Vector

import bpy
from bpy.types import Operator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_chains(selected: set) -> list[list]:
    """
    Decompose the selected pose-bone set into chains.

    A chain is a maximal path of selected bones where every bone except the
    last has exactly one selected child.  A bone is a chain start when:
      - its parent is not in the selected set  (root of selection), OR
      - its parent has more than one selected child  (branch point)
    """
    chain_starts = [
        b for b in selected
        if (b.parent not in selected)
        or (sum(1 for c in b.parent.children if c in selected) > 1)
    ]

    chains: list[list] = []
    for start in chain_starts:
        chain: list = []
        cur = start
        while cur in selected:
            chain.append(cur)
            sel_children = [c for c in cur.children if c in selected]
            cur = sel_children[0] if len(sel_children) == 1 else None
        if chain:
            chains.append(chain)

    return chains


def _ribbon_from_chain(
    chain: list,
    width: float,
    vert_list: list[Vector],
    face_list: list[tuple[int, ...]],
) -> None:
    """
    Build a flat quad-strip ribbon along a bone chain.

    Each bone contributes a cross-section at its head; the last bone adds
    one at its tail too.  Vertices are offset ±half_width along the bone's
    local X axis (world-space), which is perpendicular to the bone length.
    """
    half = width / 2.0
    base = len(vert_list)

    cross_sections: list[tuple[Vector, Vector]] = [
        (Vector(b.head), Vector(b.x_axis)) for b in chain
    ]
    last = chain[-1]
    cross_sections.append((Vector(last.tail), Vector(last.x_axis)))

    for pos, x_axis in cross_sections:
        vert_list.append(pos + x_axis * half)   # right
        vert_list.append(pos - x_axis * half)   # left

    n = len(cross_sections)
    for i in range(n - 1):
        r0 = base + i * 2
        l0 = base + i * 2 + 1
        r1 = base + (i + 1) * 2
        l1 = base + (i + 1) * 2 + 1
        face_list.append((r0, r1, l1, l0))


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------

class BONE_OT_generate_mesh(Operator):
    """Generate a low-poly quad mesh from the selected pose bones"""
    bl_idname = "bone_util.generate_mesh"
    bl_label = "Generate Bone Mesh"
    bl_description = (
        "Create a ribbon quad-mesh for each selected bone chain in Pose Mode, "
        "merged into one object. Intended as a low-poly simulation cage."
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            context.object is not None
            and context.object.type == 'ARMATURE'
            and context.mode == 'POSE'
            and bool(context.selected_pose_bones)
        )

    def execute(self, context):
        props = context.scene.bone_util_props
        selected = set(context.selected_pose_bones)

        # --- Build chains ---
        chains = _build_chains(selected)
        if not chains:
            self.report({'ERROR'}, "ArmExt: No chains found in selection.")
            return {'CANCELLED'}

        # --- Build geometry: one ribbon per chain, all merged ---
        all_verts: list[Vector] = []
        all_faces: list[tuple[int, ...]] = []

        for chain in chains:
            _ribbon_from_chain(chain, props.mesh_ribbon_width, all_verts, all_faces)

        if not all_faces:
            self.report({'ERROR'}, "ArmExt: No geometry could be generated.")
            return {'CANCELLED'}

        # --- Create mesh object ---
        mesh = bpy.data.meshes.new("BoneMesh")
        mesh.from_pydata([v.to_tuple() for v in all_verts], [], all_faces)
        mesh.update()

        obj = bpy.data.objects.new("BoneMesh", mesh)
        for coll in context.object.users_collection:
            coll.objects.link(obj)

        # Verts are already in world space — no parent transform needed
        obj.matrix_world = Matrix.Identity(4)

        # Select the new mesh
        bpy.ops.pose.select_all(action='DESELECT')
        context.view_layer.objects.active = obj
        obj.select_set(True)

        face_count = len(all_faces)
        self.report(
            {'INFO'},
            f"ArmExt: Created '{obj.name}' with {face_count} face(s) from "
            f"{len(chains)} chain(s).",
        )
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (BONE_OT_generate_mesh,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
