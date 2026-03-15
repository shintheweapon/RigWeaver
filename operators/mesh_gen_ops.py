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


def _interpolate_levels(
    levels_A: list[Vector],
    levels_B: list[Vector],
    resolution: int,
) -> list[list[Vector]]:
    """
    Return (resolution - 1) intermediate level-lists linearly interpolated
    between levels_A and levels_B.  resolution=1 returns [].

    When one list is shorter, its last position is reused for missing depths
    so that dropout tapering is preserved in interpolated columns.
    """
    if resolution <= 1:
        return []

    max_depth = max(len(levels_A), len(levels_B))

    def _pos(levels: list[Vector], d: int) -> Vector:
        return levels[d] if d < len(levels) else levels[-1]

    result: list[list[Vector]] = []
    for step in range(1, resolution):
        t = step / resolution
        result.append([_pos(levels_A, d).lerp(_pos(levels_B, d), t)
                        for d in range(max_depth)])
    return result


def _fill_columns(
    all_columns: list[list[Vector]],
    real_len_left: int,
    real_len_right: int,
    vert_list: list[Vector],
    face_list: list[tuple[int, ...]],
) -> None:
    """
    Build vertices and faces for a sequence of level-columns.

    all_columns: ordered list of level-position lists (first = left real chain,
                 last = right real chain, middle = interpolated).
    real_len_left / real_len_right: bone-count of the two bounding real chains,
        used to determine dropout depth for each column.
    """
    n_cols = len(all_columns)
    max_depth = max(len(c) for c in all_columns)

    # Build local vertex map: (col_idx, depth) → index in vert_list
    col_vert_map: dict[tuple[int, int], int] = {}
    for ci, col in enumerate(all_columns):
        for d, pos in enumerate(col):
            col_vert_map[(ci, d)] = len(vert_list)
            vert_list.append(pos)

    for ci in range(n_cols - 1):
        len_left  = len(all_columns[ci])
        len_right = len(all_columns[ci + 1])

        for d in range(max_depth):
            l_curr = d <= len_left - 1
            r_curr = d <= len_right - 1
            l_next = (d + 1) <= len_left - 1
            r_next = (d + 1) <= len_right - 1

            if not l_curr or not r_curr:
                continue

            if l_next and r_next:
                face_list.append((
                    col_vert_map[(ci, d)],
                    col_vert_map[(ci + 1, d)],
                    col_vert_map[(ci + 1, d + 1)],
                    col_vert_map[(ci, d + 1)],
                ))
            elif l_next:
                face_list.append((
                    col_vert_map[(ci, d)],
                    col_vert_map[(ci + 1, d)],
                    col_vert_map[(ci, d + 1)],
                ))
            elif r_next:
                face_list.append((
                    col_vert_map[(ci, d)],
                    col_vert_map[(ci + 1, d)],
                    col_vert_map[(ci + 1, d + 1)],
                ))


def _cross_section_mesh(
    chains: list[list],
    close_loop: bool,
    resolution: int,
    vert_list: list[Vector],
    face_list: list[tuple[int, ...]],
) -> None:
    """
    Build a connected cross-section mesh from multiple chains of any length.

    Each adjacent chain pair is expanded into `resolution` columns by linear
    interpolation, giving denser geometry for simulation without changing shape.
    Shorter chains taper with collapse triangles at their dropout depth.

    close_loop: connect last chain back to first (cylindrical surfaces).
    resolution: quad columns per panel (1 = one column, default 2+).
    """
    N = len(chains)
    pairs = [(i, i + 1) for i in range(N - 1)]
    if close_loop and N >= 3:
        pairs.append((N - 1, 0))

    for i, j in pairs:
        levels_i = _chain_levels(chains[i])
        levels_j = _chain_levels(chains[j])
        interpolated = _interpolate_levels(levels_i, levels_j, resolution)
        all_columns = [levels_i] + interpolated + [levels_j]
        _fill_columns(
            all_columns,
            len(chains[i]),
            len(chains[j]),
            vert_list,
            face_list,
        )


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
        elif props.mesh_individual_chains:
            # Individual mode → one ribbon per chain, all merged
            for chain in chains:
                _ribbon_from_chain(chain, props.mesh_ribbon_width, all_verts, all_faces)
        else:
            # Connected mode → cross-section surface between adjacent chains.
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
                props.mesh_panel_resolution,
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
