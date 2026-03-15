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
    Order chains by physical adjacency using a nearest-neighbour walk.

    Starting from the chain whose root is furthest from the centroid of all
    roots (a stable extreme-end seed), each step picks the closest unvisited
    chain by 3D distance between first-bone tails.  This is robust to wide
    arcs, partial circles, and any arrangement where atan2 seam detection
    fails.

    parent_bone is accepted for API compatibility but is no longer used.
    """
    if len(chains) <= 1:
        return chains

    roots = [Vector(c[0].tail) for c in chains]
    centroid = sum(roots, Vector()) / len(roots)

    # Seed from the chain whose root is most distant from the centroid so the
    # walk always starts at a natural edge of the arrangement.
    start = max(range(len(chains)), key=lambda i: (roots[i] - centroid).length)

    remaining = list(range(len(chains)))
    remaining.remove(start)
    ordered = [chains[start]]
    last_root = roots[start]

    while remaining:
        nearest = min(remaining, key=lambda i: (roots[i] - last_root).length)
        ordered.append(chains[nearest])
        last_root = roots[nearest]
        remaining.remove(nearest)

    return ordered


def _chain_levels(chain: list) -> list[Vector]:
    """
    Return N+2 world-space positions for the cross-section mesh rows (N bones).

    Top row:    0.5 bone-lengths before the first bone's root (extends outward).
    Middle rows: midpoint of each bone — each quad straddles a bone junction.
    Bottom row: 0.5 bone-lengths past  the last  bone's tip  (extends outward).

    Produces N+1 quads for N bones (one more than the previous junction scheme).
    """
    v_first = Vector(chain[0].tail)  - Vector(chain[0].head)
    v_last  = Vector(chain[-1].tail) - Vector(chain[-1].head)
    ext_top    = Vector(chain[0].head)  - v_first * 0.5
    ext_bottom = Vector(chain[-1].tail) + v_last  * 0.5
    midpoints  = [(Vector(b.head) + Vector(b.tail)) * 0.5 for b in chain]
    return [ext_top] + midpoints + [ext_bottom]


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

    Each chain owns one panel centred on itself.  Panel boundaries are at the
    midpoint between the chain and each neighbour; outer boundaries are
    extrapolated by the same half-step outward.  This gives N panels for N
    chains (vs N-1 in an edge-aligned scheme) and each bone runs through the
    centre of its panel — matching the single-chain ribbon behaviour.

    close_loop: connect last chain back to first (cylindrical surfaces, N≥3).
    resolution: quad columns per panel (1 = one column, default 2+).
    """
    N = len(chains)
    all_levels = [_chain_levels(c) for c in chains]
    use_loop = close_loop and N >= 3

    def _pos(levels, d):
        return levels[d] if d < len(levels) else levels[-1]

    def _mid_col(LA, LB, depth):
        """Midpoint column between two level-lists, truncated to `depth`."""
        return [(_pos(LA, d) + _pos(LB, d)) * 0.5 for d in range(depth)]

    def _extrap_col(L_inner, L_outer, depth):
        """Extrapolate half a step outward from L_inner away from L_outer."""
        return [_pos(L_inner, d) * 1.5 - _pos(L_outer, d) * 0.5
                for d in range(depth)]

    for i in range(N):
        depth = len(all_levels[i])

        if use_loop:
            left_col  = _mid_col(all_levels[(i - 1) % N], all_levels[i],            depth)
            right_col = _mid_col(all_levels[i],            all_levels[(i + 1) % N],  depth)
        else:
            left_col  = (_extrap_col(all_levels[0],     all_levels[1],     depth)
                         if i == 0
                         else _mid_col(all_levels[i - 1], all_levels[i],   depth))
            right_col = (_extrap_col(all_levels[N - 1], all_levels[N - 2], depth)
                         if i == N - 1
                         else _mid_col(all_levels[i],   all_levels[i + 1], depth))

        interpolated = _interpolate_levels(left_col, right_col, resolution)
        all_columns  = [left_col] + interpolated + [right_col]
        _fill_columns(all_columns, len(chains[i]), len(chains[i]), vert_list, face_list)


# ---------------------------------------------------------------------------
# Triangulation helper
# ---------------------------------------------------------------------------

def _triangulate_faces(
    faces: list[tuple[int, ...]],
) -> list[tuple[int, ...]]:
    """Split every quad into two triangles; triangles pass through unchanged."""
    result: list[tuple[int, ...]] = []
    for f in faces:
        if len(f) == 4:
            a, b, c, d = f
            result.append((a, b, c))
            result.append((a, c, d))
        else:
            result.append(f)
    return result


# ---------------------------------------------------------------------------
# Object creation helper
# ---------------------------------------------------------------------------

def _create_mesh_object(
    name: str,
    verts: list[Vector],
    faces: list[tuple[int, ...]],
    source_obj,
    context,
) -> "bpy.types.Object":
    """
    Create a named mesh object from raw geometry and link it to the same
    collections as source_obj.  Blender auto-appends .001 / .002 etc. when
    the name is already taken, so no manual collision handling is needed.
    """
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([v.to_tuple() for v in verts], [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    for coll in source_obj.users_collection:
        coll.objects.link(obj)
    obj.matrix_world = Matrix.Identity(4)
    return obj


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

        source_obj = context.object

        # ------------------------------------------------------------------
        # Individual chains, split into separate objects
        # ------------------------------------------------------------------
        if len(chains) > 1 and props.mesh_individual_chains and props.mesh_split_objects:
            created: list = []
            for chain in chains:
                verts: list[Vector] = []
                faces: list[tuple[int, ...]] = []
                _ribbon_from_chain(chain, props.mesh_ribbon_width, verts, faces)
                if props.mesh_triangulate:
                    faces = _triangulate_faces(faces)
                if faces:
                    obj = _create_mesh_object(
                        f"BoneMesh_{chain[0].name}", verts, faces, source_obj, context
                    )
                    created.append(obj)

            if not created:
                self.report({'ERROR'}, "ArmExt: No geometry could be generated.")
                return {'CANCELLED'}

            bpy.ops.pose.select_all(action='DESELECT')
            for obj in created:
                obj.select_set(True)
            context.view_layer.objects.active = created[-1]

            self.report(
                {'INFO'},
                f"ArmExt: Created {len(created)} object(s) from {len(chains)} chain(s).",
            )
            return {'FINISHED'}

        # ------------------------------------------------------------------
        # All other modes → build into a single combined object
        # ------------------------------------------------------------------
        all_verts: list[Vector] = []
        all_faces: list[tuple[int, ...]] = []

        if len(chains) == 1:
            # Single chain → ribbon using bone local X axis for width
            _ribbon_from_chain(chains[0], props.mesh_ribbon_width, all_verts, all_faces)
        elif props.mesh_individual_chains:
            # Individual mode, merged → one ribbon per chain combined
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

        if props.mesh_triangulate:
            all_faces = _triangulate_faces(all_faces)

        obj = _create_mesh_object("BoneMesh", all_verts, all_faces, source_obj, context)

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
