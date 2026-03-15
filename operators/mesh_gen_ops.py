"""
Operator: Generate a low-poly surface mesh from selected pose bones.

Intended for cloth / softbody simulation setups. No vertex groups or
weights are created — the mesh is plain geometry that follows the bone
positions at the moment of generation.

Single chain → flat quad-strip ribbon (width = mesh_ribbon_width).
Multiple chains → connected cross-section surface with graduated dropout
for chains of unequal length.
"""
from __future__ import annotations

import math
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


def _sort_chains(chains: list[list], parent_bone) -> list[list]:
    """
    Sort chains by their angular position around the parent bone's axis.
    When no parent exists, sort by angle around the centroid of chain roots
    projected onto the XY plane.
    """
    if len(chains) <= 1:
        return chains

    if parent_bone is not None:
        axis = Vector(parent_bone.tail) - Vector(parent_bone.head)
        axis = axis.normalized() if axis.length > 1e-6 else Vector((0.0, 0.0, 1.0))
        origin = Vector(parent_bone.tail)
    else:
        axis = Vector((0.0, 0.0, 1.0))
        roots = [Vector(c[0].head) for c in chains]
        origin = sum(roots, Vector()) / len(roots)

    z = axis
    arbitrary = Vector((1.0, 0.0, 0.0))
    if abs(z.dot(arbitrary)) > 0.99:
        arbitrary = Vector((0.0, 1.0, 0.0))
    x = z.cross(arbitrary).normalized()
    y = z.cross(x).normalized()

    def angle_key(chain):
        delta = Vector(chain[0].head) - origin
        return math.atan2(delta.dot(y), delta.dot(x))

    return sorted(chains, key=angle_key)


def _chain_levels(chain: list) -> list[Vector]:
    """Return N+1 world-space positions for an N-bone chain."""
    return [Vector(b.head) for b in chain] + [Vector(chain[-1].tail)]


def _ribbon_from_chain(
    chain: list,
    width: float,
    vert_list: list[Vector],
    face_list: list[tuple[int, ...]],
) -> None:
    """
    Build a flat quad-strip ribbon along a single bone chain.

    Vertices are offset ±half_width along each bone's local X axis
    (world-space), which is perpendicular to the bone length direction.
    """
    half = width / 2.0
    base = len(vert_list)

    cross_sections: list[tuple[Vector, Vector]] = [
        (Vector(b.head), Vector(b.x_axis)) for b in chain
    ]
    last = chain[-1]
    cross_sections.append((Vector(last.tail), Vector(last.x_axis)))

    for pos, x_axis in cross_sections:
        vert_list.append(pos + x_axis * half)
        vert_list.append(pos - x_axis * half)

    n = len(cross_sections)
    for i in range(n - 1):
        r0 = base + i * 2
        l0 = base + i * 2 + 1
        r1 = base + (i + 1) * 2
        l1 = base + (i + 1) * 2 + 1
        face_list.append((r0, r1, l1, l0))


def _cross_section_mesh(
    chains: list[list],
    close_loop: bool,
    vert_list: list[Vector],
    face_list: list[tuple[int, ...]],
) -> None:
    """
    Build a connected cross-section mesh from multiple chains of any length.

    Each chain contributes one vertex per depth level (bone heads + last tail).
    Adjacent chain pairs are connected with quads at each level.  When one
    chain of a pair ends before the other, a collapse triangle is emitted
    instead so shorter chains taper cleanly rather than leaving gaps.

    close_loop: if True, also connects the last chain back to the first
    (for cylindrical surfaces like skirts).
    """
    N = len(chains)

    # Build vertex table: vert_map[(chain_idx, level)] = index in vert_list
    vert_map: dict[tuple[int, int], int] = {}
    for i, chain in enumerate(chains):
        for l, pos in enumerate(_chain_levels(chain)):
            vert_map[(i, l)] = len(vert_list)
            vert_list.append(pos)

    max_level = max(len(c) for c in chains)

    # Determine which adjacent pairs to process
    pairs = [(i, i + 1) for i in range(N - 1)]
    if close_loop and N >= 3:
        pairs.append((N - 1, 0))

    for i, j in pairs:
        len_i = len(chains[i])
        len_j = len(chains[j])

        for l in range(max_level):
            i_curr = l <= len_i       # chain i has a vertex at level l
            j_curr = l <= len_j       # chain j has a vertex at level l
            i_next = (l + 1) <= len_i  # chain i has a vertex at level l+1
            j_next = (l + 1) <= len_j  # chain j has a vertex at level l+1

            if not i_curr or not j_curr:
                continue  # at least one chain has no vertex at this level

            if i_next and j_next:
                # Both chains continue → quad
                face_list.append((
                    vert_map[(i, l)],
                    vert_map[(j, l)],
                    vert_map[(j, l + 1)],
                    vert_map[(i, l + 1)],
                ))
            elif i_next and not j_next:
                # Chain j ends at l → collapse triangle
                face_list.append((
                    vert_map[(i, l)],
                    vert_map[(j, l)],
                    vert_map[(i, l + 1)],
                ))
            elif j_next and not i_next:
                # Chain i ends at l → collapse triangle
                face_list.append((
                    vert_map[(i, l)],
                    vert_map[(j, l)],
                    vert_map[(j, l + 1)],
                ))
            # Both end at l: no face needed


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------

class BONE_OT_generate_mesh(Operator):
    """Generate a low-poly quad mesh from the selected pose bones"""
    bl_idname = "bone_util.generate_mesh"
    bl_label = "Generate Bone Mesh"
    bl_description = (
        "Create a surface mesh from the selected bone chains in Pose Mode. "
        "Single chain produces a ribbon; multiple chains produce a connected "
        "cross-section surface. Intended as a low-poly simulation cage."
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

        # --- Build and sort chains ---
        chains = _build_chains(selected)
        if not chains:
            self.report({'ERROR'}, "ArmExt: No chains found in selection.")
            return {'CANCELLED'}

        all_verts: list[Vector] = []
        all_faces: list[tuple[int, ...]] = []

        if len(chains) == 1:
            # Single chain → ribbon using bone local X axis for width
            _ribbon_from_chain(chains[0], props.mesh_ribbon_width, all_verts, all_faces)
        else:
            # Multiple chains → sort angularly, then cross-section mesh.
            # Use the shared parent bone as the sort axis when all chains
            # have the same immediate parent (skirt / hair); fall back to
            # centroid-based sorting otherwise.
            first_parent = chains[0][0].parent
            common_parent = (
                first_parent
                if all(c[0].parent == first_parent for c in chains)
                else None
            )
            sorted_chains = _sort_chains(chains, common_parent)
            _cross_section_mesh(
                sorted_chains,
                props.close_mesh_loop,
                all_verts,
                all_faces,
            )

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

        obj.matrix_world = Matrix.Identity(4)

        bpy.ops.pose.select_all(action='DESELECT')
        context.view_layer.objects.active = obj
        obj.select_set(True)

        self.report(
            {'INFO'},
            f"ArmExt: Created '{obj.name}' with {len(all_faces)} face(s) "
            f"from {len(chains)} chain(s).",
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
