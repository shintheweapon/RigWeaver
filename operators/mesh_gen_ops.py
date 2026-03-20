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

import bmesh
import bpy
from bpy.app.handlers import persistent
from bpy.types import Operator

try:
    import gpu
    from gpu_extras.batch import batch_for_shader
    _GPU_AVAILABLE = True
except ImportError:
    _GPU_AVAILABLE = False

try:
    import numpy as _np
    _NUMPY_AVAILABLE = True
except ImportError:
    _np = None
    _NUMPY_AVAILABLE = False


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
        visited: set = set()
        while cur in selected and cur not in visited:
            visited.add(cur)
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


def _split_into_strips(chains: list[list], gap_factor: float) -> list[list[list]]:
    """
    Split a sorted chain list into strips wherever the gap between consecutive
    chain roots exceeds gap_factor * median inter-chain distance.
    Returns a list of strips (each strip is a list of chains).
    """
    if len(chains) <= 1:
        return [chains]

    roots = [Vector(c[0].tail) for c in chains]
    dists = [(roots[i + 1] - roots[i]).length for i in range(len(chains) - 1)]
    median_dist = sorted(dists)[len(dists) // 2]
    threshold = gap_factor * median_dist

    strips, current = [], [chains[0]]
    for i, d in enumerate(dists):
        if d > threshold:
            strips.append(current)
            current = [chains[i + 1]]
        else:
            current.append(chains[i + 1])
    strips.append(current)
    return strips


def _distance_to_segment(pos: Vector, head: Vector, tail: Vector) -> float:
    """Shortest distance from pos to the line segment head→tail."""
    seg = tail - head
    seg_len_sq = seg.length_squared
    if seg_len_sq < 1e-10:
        return (pos - head).length
    fac = max(0.0, min(1.0, (pos - head).dot(seg) / seg_len_sq))
    return (pos - (head + seg * fac)).length


def _assign_bone_vertex_groups(
    mesh_obj: "bpy.types.Object",
    verts: list[Vector],
    chains: list[list],
    envelope_factor: float = 1.5,
) -> None:
    """
    Create one vertex group per bone and assign envelope-style weights.

    Each bone's radius = bone_length × envelope_factor.
    Falloff: w = (1 - (d/r)²)², reaching exactly zero at the envelope boundary.
    Vertices outside all envelopes fall back to the nearest bone (weight 1.0).
    Weights are normalised to sum to 1.0 per vertex.
    """
    all_bones = [bone for chain in chains for bone in chain]

    vgs = []
    # Pre-convert bone positions to Vectors and compute lengths once (O(B) not O(V*B))
    bone_data: list[tuple[Vector, Vector, float]] = []
    for bone in all_bones:
        vg = (mesh_obj.vertex_groups.get(bone.name)
              or mesh_obj.vertex_groups.new(name=bone.name))
        vgs.append(vg)
        head = Vector(bone.head)
        tail = Vector(bone.tail)
        bone_data.append((head, tail, (tail - head).length))

    for vi, pos in enumerate(verts):
        weights = []
        for head, tail, bone_len in bone_data:
            d = _distance_to_segment(pos, head, tail)
            r = max(bone_len * envelope_factor, 1e-6)
            t = d / r
            weights.append(0.0 if t >= 1.0 else (1.0 - t * t) ** 2)

        total = sum(weights)
        if total < 1e-6:
            # Vertex outside all envelopes → assign fully to nearest bone
            nearest = min(range(len(bone_data)),
                          key=lambda i: _distance_to_segment(
                              pos, bone_data[i][0], bone_data[i][1]))
            vgs[nearest].add([vi], 1.0, 'REPLACE')
        else:
            for vg, w in zip(vgs, weights):
                weight = w / total
                if weight > 0.001:
                    vg.add([vi], weight, 'REPLACE')


def _catmull_rom_point(
    p0: Vector, p1: Vector, p2: Vector, p3: Vector, t: float
) -> Vector:
    """Evaluate a Catmull-Rom spline at t ∈ [0, 1] between p1 and p2."""
    t2 = t * t
    t3 = t2 * t
    return 0.5 * (
        (2.0 * p1)
        + (-p0 + p2) * t
        + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
        + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
    )


def _col(levels: list[Vector], depth: int) -> list[Vector]:
    """Return a column of exactly `depth` entries, clamping with _pos."""
    return [_pos(levels, d) for d in range(depth)]


def _chain_levels(
    chain: list,
    subdivisions: int = 1,
    row_interp: str = 'LINEAR',
) -> list[Vector]:
    """
    Return world-space row positions for the cross-section mesh.

    With subdivisions=1: N+2 levels for N bones — one extension before the
    first bone, one midpoint per bone, one extension after the last.
    With subdivisions>1: each segment is split into that many parts using the
    chosen row_interp method (LINEAR or CATMULL_ROM).
    Note: CATMULL_ROM is identical to LINEAR when subdivisions=1.
    """
    v_first = Vector(chain[0].tail)  - Vector(chain[0].head)
    v_last  = Vector(chain[-1].tail) - Vector(chain[-1].head)
    ext_top    = Vector(chain[0].head)  - v_first * 0.5
    ext_bottom = Vector(chain[-1].tail) + v_last  * 0.5
    midpoints  = [(Vector(b.head) + Vector(b.tail)) * 0.5 for b in chain]
    base_levels = [ext_top] + midpoints + [ext_bottom]

    if subdivisions <= 1:
        return base_levels

    result = [base_levels[0]]
    n = len(base_levels)

    if row_interp == 'CATMULL_ROM':
        for i in range(n - 1):
            p0 = base_levels[max(i - 1, 0)]
            p1 = base_levels[i]
            p2 = base_levels[i + 1]
            p3 = base_levels[min(i + 2, n - 1)]
            for s in range(1, subdivisions + 1):
                result.append(_catmull_rom_point(p0, p1, p2, p3, s / subdivisions))
    else:  # LINEAR
        for i in range(n - 1):
            a, b = base_levels[i], base_levels[i + 1]
            for s in range(1, subdivisions + 1):
                result.append(a.lerp(b, s / subdivisions))

    return result


def _ribbon_from_chain(
    chain: list,
    width: float,
    subdivisions: int,
    vert_list: list[Vector],
    face_list: list[tuple[int, ...]],
    uv_list: list[tuple[float, float]] | None = None,
) -> None:
    """
    Build a flat quad-strip ribbon along a single bone chain.

    Vertices are offset ±half_width along each bone's local X axis
    (world-space), which is perpendicular to the bone length direction.
    subdivisions controls how many rows each bone segment is split into.
    """
    half = width / 2.0
    base = len(vert_list)

    cross_sections: list[tuple[Vector, Vector]] = []
    for bone in chain:
        head_pos  = Vector(bone.head)
        tail_pos  = Vector(bone.tail)
        x_axis    = Vector(bone.x_axis)
        for s in range(subdivisions):
            t = s / subdivisions
            cross_sections.append((head_pos.lerp(tail_pos, t), x_axis))
    last = chain[-1]
    cross_sections.append((Vector(last.tail), Vector(last.x_axis)))

    n_sections = len(cross_sections)
    for idx, (pos, x_axis) in enumerate(cross_sections):
        v = idx / max(n_sections - 1, 1)
        vert_list.append(pos + x_axis * half)
        vert_list.append(pos - x_axis * half)
        if uv_list is not None:
            uv_list.append((1.0, v))  # right
            uv_list.append((0.0, v))  # left

    n = len(cross_sections)
    for i in range(n - 1):
        r0 = base + i * 2
        l0 = base + i * 2 + 1
        r1 = base + (i + 1) * 2
        l1 = base + (i + 1) * 2 + 1
        face_list.append((r0, r1, l1, l0))


def _pos(levels: list[Vector], d: int) -> Vector:
    """Return levels[d], clamping to the last entry when d is out of range."""
    return levels[d] if d < len(levels) else levels[-1]


def _interpolate_levels(
    levels_A: list[Vector],
    levels_B: list[Vector],
    resolution: int,
    lateral_interp: str = 'LINEAR',
    cr_p0: "list[Vector] | None" = None,
    cr_p3: "list[Vector] | None" = None,
) -> list[list[Vector]]:
    """
    Return (resolution - 1) intermediate level-lists interpolated between
    levels_A and levels_B.  resolution=1 returns [].

    lateral_interp:
      'LINEAR'      — straight lerp between the two columns.
      'CATMULL_ROM' — smooth Catmull-Rom spline; cr_p0 and cr_p3 must be
                      supplied as the phantom control columns that bracket the
                      segment (cr_p0 before levels_A, cr_p3 after levels_B).
                      Falls back to LINEAR when phantoms are absent.

    When one list is shorter, its last position is reused for missing depths
    so that dropout tapering is preserved in interpolated columns.
    """
    if resolution <= 1:
        return []

    max_depth = max(len(levels_A), len(levels_B))
    result: list[list[Vector]] = []

    if lateral_interp == 'CATMULL_ROM' and cr_p0 is not None and cr_p3 is not None:
        for step in range(1, resolution):
            t = step / resolution
            result.append([
                _catmull_rom_point(
                    _pos(cr_p0,     d),
                    _pos(levels_A,  d),
                    _pos(levels_B,  d),
                    _pos(cr_p3,     d),
                    t,
                )
                for d in range(max_depth)
            ])
    else:  # LINEAR (or CATMULL_ROM fallback when phantoms are absent)
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
    uv_list: list[tuple[float, float]] | None = None,
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
        u = ci / max(n_cols - 1, 1)
        for d, pos in enumerate(col):
            col_vert_map[(ci, d)] = len(vert_list)
            vert_list.append(pos)
            if uv_list is not None:
                uv_list.append((u, d / max(max_depth - 1, 1)))

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
                    col_vert_map[(ci, d + 1)],
                    col_vert_map[(ci + 1, d + 1)],
                    col_vert_map[(ci + 1, d)],
                ))
            elif l_next:
                face_list.append((
                    col_vert_map[(ci, d)],
                    col_vert_map[(ci, d + 1)],
                    col_vert_map[(ci + 1, d)],
                ))
            elif r_next:
                face_list.append((
                    col_vert_map[(ci, d)],
                    col_vert_map[(ci + 1, d + 1)],
                    col_vert_map[(ci + 1, d)],
                ))


def _cross_section_mesh(
    chains: list[list],
    close_loop: bool,
    resolution: int,
    vert_list: list[Vector],
    face_list: list[tuple[int, ...]],
    subdivisions: int = 1,
    uv_list: list[tuple[float, float]] | None = None,
    row_interp: str = 'LINEAR',
    lateral_interp: str = 'LINEAR',
) -> None:
    """
    Build a connected cross-section mesh from multiple chains of any length.

    Each chain owns one panel centred on itself.  Panel boundaries are at the
    midpoint between the chain and each neighbour; outer boundaries are
    extrapolated by the same half-step outward.  This gives N panels for N
    chains (vs N-1 in an edge-aligned scheme) and each bone runs through the
    centre of its panel — matching the single-chain ribbon behaviour.

    close_loop:     connect last chain back to first (cylindrical surfaces, N≥3).
    resolution:     quad columns per panel in the lateral direction.
    subdivisions:   row subdivisions per bone segment in the longitudinal direction.
    row_interp:     interpolation along each chain ('LINEAR' or 'CATMULL_ROM').
    lateral_interp: interpolation across adjacent chains ('LINEAR' or 'CATMULL_ROM').
    """
    N = len(chains)
    all_levels = [_chain_levels(c, subdivisions, row_interp) for c in chains]
    use_loop = close_loop and N >= 3

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
            left_col  = _mid_col(all_levels[(i - 1) % N], all_levels[i],           depth)
            right_col = _mid_col(all_levels[i],            all_levels[(i + 1) % N], depth)
            # Phantom control columns for Catmull-Rom lateral spline:
            #   left half  (left_col→center_col): p0=chain[i-1], p3=right_col
            #   right half (center_col→right_col): p0=left_col,  p3=chain[i+1]
            cr_prev = _col(all_levels[(i - 1) % N], depth)
            cr_next = _col(all_levels[(i + 1) % N], depth)
        else:
            left_col  = (_extrap_col(all_levels[0],     all_levels[1],     depth)
                         if i == 0
                         else _mid_col(all_levels[i - 1], all_levels[i],   depth))
            right_col = (_extrap_col(all_levels[N - 1], all_levels[N - 2], depth)
                         if i == N - 1
                         else _mid_col(all_levels[i],   all_levels[i + 1], depth))
            # Clamp phantom columns at boundaries (produces zero tangent → clamped spline)
            cr_prev = _col(all_levels[max(i - 1, 0)],     depth)
            cr_next = _col(all_levels[min(i + 1, N - 1)], depth)

        center_col   = all_levels[i][:depth]  # actual bone positions — always a vertex
        left_interp  = _interpolate_levels(left_col,   center_col, resolution, lateral_interp,
                                           cr_p0=cr_prev,    cr_p3=right_col)
        right_interp = _interpolate_levels(center_col, right_col,  resolution, lateral_interp,
                                           cr_p0=left_col,   cr_p3=cr_next)
        all_columns  = [left_col] + left_interp + [center_col] + right_interp + [right_col]
        _fill_columns(all_columns, len(chains[i]), len(chains[i]), vert_list, face_list, uv_list)


# ---------------------------------------------------------------------------
# Tree Surface helpers (Bowyer-Watson Delaunay + alpha-shape filter)
# ---------------------------------------------------------------------------

def _bowyer_watson(pts2d: list[tuple[float, float]]) -> list[tuple[int, int, int]]:
    """
    Incremental Bowyer-Watson Delaunay triangulation.
    Returns a list of (i, j, k) index triples into pts2d.
    """
    import math

    def _circumcircle(ax, ay, bx, by, cx, cy):
        D = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
        if abs(D) < 1e-10:
            return None
        ux = ((ax*ax + ay*ay)*(by - cy) + (bx*bx + by*by)*(cy - ay) + (cx*cx + cy*cy)*(ay - by)) / D
        uy = ((ax*ax + ay*ay)*(cx - bx) + (bx*bx + by*by)*(ax - cx) + (cx*cx + cy*cy)*(bx - ax)) / D
        r2 = (ax - ux)**2 + (ay - uy)**2
        return ux, uy, r2

    n = len(pts2d)
    if n < 3:
        return []

    xs = [p[0] for p in pts2d]
    ys = [p[1] for p in pts2d]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    dx = (max_x - min_x) or 1.0
    dy = (max_y - min_y) or 1.0
    delta = max(dx, dy) * 10.0
    mid_x = (min_x + max_x) / 2.0
    # Super-triangle vertex indices: n, n+1, n+2
    pts = list(pts2d) + [
        (mid_x - 20.0 * delta, min_y - delta),
        (mid_x,                max_y + 20.0 * delta),
        (mid_x + 20.0 * delta, min_y - delta),
    ]
    super_idx = {n, n + 1, n + 2}

    cc = _circumcircle(*pts[n], *pts[n + 1], *pts[n + 2])
    triangles: list[list] = [[n, n + 1, n + 2, cc[0], cc[1], cc[2]]] if cc else []

    for pi in range(n):
        px, py = pts[pi]
        bad = [t for t in triangles
               if t[5] is not None and (px - t[3])**2 + (py - t[4])**2 < t[5]]

        edge_count: dict[tuple[int, int], int] = {}
        for t in bad:
            for edge in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                key = (min(edge), max(edge))
                edge_count[key] = edge_count.get(key, 0) + 1
        boundary = [e for e, cnt in edge_count.items() if cnt == 1]

        for t in bad:
            triangles.remove(t)

        for (ei, ej) in boundary:
            c = _circumcircle(*pts[ei], *pts[ej], px, py)
            if c is None:
                continue
            triangles.append([ei, ej, pi, c[0], c[1], c[2]])

    result = []
    for t in triangles:
        if super_idx & {t[0], t[1], t[2]}:
            continue
        i, j, k = t[0], t[1], t[2]
        ax, ay = pts[i]
        bx, by = pts[j]
        cx, cy = pts[k]
        # Signed area positive = CCW; swap i,j to enforce CCW winding
        if (bx - ax) * (cy - ay) - (by - ay) * (cx - ax) < 0:
            i, j = j, i
        result.append((i, j, k))
    return result


def _alpha_filter(
    pts2d: list[tuple[float, float]],
    triangles: list[tuple[int, int, int]],
    alpha: float,
) -> list[tuple[int, int, int]]:
    """Remove triangles whose circumradius exceeds alpha."""
    import math

    def _circumradius(ax, ay, bx, by, cx, cy) -> float:
        a = math.hypot(bx - cx, by - cy)
        b = math.hypot(ax - cx, ay - cy)
        c = math.hypot(ax - bx, ay - by)
        area2 = abs((bx - ax) * (cy - ay) - (cx - ax) * (by - ay))
        if area2 < 1e-10:
            return float('inf')
        return (a * b * c) / (2.0 * area2)

    return [(i, j, k) for (i, j, k) in triangles
            if _circumradius(*pts2d[i], *pts2d[j], *pts2d[k]) <= alpha]


def _tree_surface_mesh(
    chains: list[list],
    subdivisions: int,
    alpha_factor: float,
    vert_list: list[Vector],
    face_list: list[tuple[int, ...]],
    uv_list: list[tuple[float, float]] | None = None,
) -> None:
    """
    Sample-point Delaunay triangulation for irregular/branching chain layouts.

    1. Collect 3D level positions from all chains via _chain_levels.
    2. Project to 2D via PCA (NumPy SVD on centred points).
    3. Bowyer-Watson Delaunay on the 2D projection.
    4. Alpha-shape filter: remove triangles with circumradius >
       alpha_factor × median edge length.
    5. Emit to vert_list / face_list.
    """
    pts3d: list[Vector] = []
    for chain in chains:
        pts3d.extend(_chain_levels(chain, subdivisions))

    if len(pts3d) < 3:
        return

    arr = _np.array([(v.x, v.y, v.z) for v in pts3d], dtype=float)
    centroid = arr.mean(axis=0)
    centered = arr - centroid
    _, _, Vt = _np.linalg.svd(centered, full_matrices=False)
    pts2d = [(float(row[0]), float(row[1])) for row in centered @ Vt[:2].T]

    tris = _bowyer_watson(pts2d)
    if not tris:
        return

    edge_lengths = []
    for (i, j, k) in tris:
        for (a, b) in ((i, j), (j, k), (k, i)):
            dx = pts2d[a][0] - pts2d[b][0]
            dy = pts2d[a][1] - pts2d[b][1]
            edge_lengths.append(math.hypot(dx, dy))
    if not edge_lengths:
        return
    median_edge = sorted(edge_lengths)[len(edge_lengths) // 2]
    alpha = alpha_factor * median_edge

    tris = _alpha_filter(pts2d, tris, alpha)
    if not tris:
        return

    if uv_list is not None:
        xs2 = [p[0] for p in pts2d]
        ys2 = [p[1] for p in pts2d]
        u_min, u_range = min(xs2), (max(xs2) - min(xs2)) or 1.0
        v_min, v_range = min(ys2), (max(ys2) - min(ys2)) or 1.0

    base = len(vert_list)
    for i, pt in enumerate(pts3d):
        vert_list.append(pt)
        if uv_list is not None:
            uv_list.append(((pts2d[i][0] - u_min) / u_range,
                            (pts2d[i][1] - v_min) / v_range))
    for (i, j, k) in tris:
        face_list.append((base + i, base + j, base + k))


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
    mesh.validate(verbose=False)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    for coll in source_obj.users_collection:
        coll.objects.link(obj)
    obj.matrix_world = Matrix.Identity(4)
    obj["rig_weaver_source"] = source_obj.name
    return obj


def _assign_uvs(
    mesh_obj: "bpy.types.Object",
    uv_list: list[tuple[float, float]],
) -> None:
    """Assign per-vertex UV coordinates to a newly created mesh object."""
    uv_layer = mesh_obj.data.uv_layers.new(name="UVMap")
    for loop in mesh_obj.data.loops:
        uv_layer.data[loop.index].uv = uv_list[loop.vertex_index]


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------

def _replace_mesh_data(
    obj: "bpy.types.Object",
    verts: list[Vector],
    faces: list[tuple[int, ...]],
) -> None:
    """Swap the geometry of an existing mesh object in-place, preserving the object."""
    old_mesh = obj.data
    new_mesh = bpy.data.meshes.new(old_mesh.name)
    new_mesh.from_pydata([v.to_tuple() for v in verts], [], faces)
    new_mesh.validate(verbose=False)
    new_mesh.update()
    bm = bmesh.new()
    bm.from_mesh(new_mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(new_mesh)
    bm.free()
    obj.data = new_mesh
    bpy.data.meshes.remove(old_mesh)
    # Clear vertex groups so auto-rig re-assignment starts from a clean slate
    obj.vertex_groups.clear()


def _build_geometry(
    props,
    chains: list[list],
) -> "tuple[list, list, list | None, list] | None":
    """
    Run the mode-switch geometry generation for combined-object modes.
    Returns (verts, faces, uvs, chains_used), or None if no geometry produced.
    Triangulation is applied when props.mesh_triangulate is set.
    """
    mode = props.mesh_mode
    all_verts: list[Vector] = []
    all_faces: list[tuple[int, ...]] = []
    all_uvs: "list[tuple[float, float]] | None" = (
        [] if props.mesh_generate_uvs else None
    )
    chains_used: list[list] = []

    if mode == 'INDIVIDUAL':
        for chain in chains:
            _ribbon_from_chain(chain, props.mesh_ribbon_width,
                               props.mesh_bone_subdivisions,
                               all_verts, all_faces, all_uvs)
        chains_used.extend(chains)

    elif mode in ('SURFACE', 'SURFACE_LOOP', 'SURFACE_SPLIT'):
        first_parent = chains[0][0].parent
        common_parent = (
            first_parent
            if all(c[0].parent == first_parent for c in chains)
            else None
        )
        sorted_chains = _sort_chains(chains, common_parent)
        strips = (
            _split_into_strips(sorted_chains, props.mesh_strip_gap_factor)
            if mode == 'SURFACE_SPLIT'
            else [sorted_chains]
        )
        loop = (mode == 'SURFACE_LOOP')
        for strip in strips:
            if len(strip) == 1:
                _ribbon_from_chain(strip[0], props.mesh_ribbon_width,
                                   props.mesh_bone_subdivisions,
                                   all_verts, all_faces, all_uvs)
            else:
                _cross_section_mesh(
                    strip, loop, props.mesh_panel_resolution,
                    all_verts, all_faces,
                    subdivisions=props.mesh_bone_subdivisions,
                    uv_list=all_uvs,
                    row_interp=props.mesh_row_interpolation,
                    lateral_interp=props.mesh_lateral_interpolation,
                )
            chains_used.extend(strip)

    elif mode == 'TREE':
        _tree_surface_mesh(
            chains, props.mesh_bone_subdivisions, props.mesh_tree_alpha_factor,
            all_verts, all_faces, all_uvs,
        )
        chains_used.extend(chains)

    if not all_faces:
        return None

    if props.mesh_triangulate:
        all_faces = _triangulate_faces(all_faces)

    return all_verts, all_faces, all_uvs, chains_used


def _apply_subsurf(obj: "bpy.types.Object", levels: int) -> None:
    """
    Add a Subdivision Surface modifier at the given level, or update the existing
    one.  Always positioned before any Armature modifier in the stack so the
    deformation order is Subsurf → Armature.
    """
    existing = next((m for m in obj.modifiers if m.type == 'SUBSURF'), None)
    if existing:
        existing.levels = levels
        existing.render_levels = levels
        mod = existing
    else:
        mod = obj.modifiers.new(name="Subdivision", type='SUBSURF')
        mod.levels = levels
        mod.render_levels = levels

    # Move Subsurf before any Armature modifier
    mod_names = [m.name for m in obj.modifiers]
    mod_idx = mod_names.index(mod.name)
    armature_idx = next(
        (i for i, m in enumerate(obj.modifiers) if m.type == 'ARMATURE'), None
    )
    if armature_idx is not None and mod_idx > armature_idx:
        obj.modifiers.move(mod_idx, armature_idx)


def _apply_post_processing(
    obj: "bpy.types.Object",
    verts: list[Vector],
    uvs: "list[tuple[float, float]] | None",
    chains_used: list[list],
    props,
    source_obj: "bpy.types.Object",
    *,
    reuse_armature_mod: bool = False,
) -> None:
    """Assign subdivision, UVs, and auto-rig to a mesh object."""
    if props.mesh_add_subsurf:
        _apply_subsurf(obj, props.mesh_subsurf_levels)
    if uvs:
        _assign_uvs(obj, uvs)
    if props.mesh_auto_rig:
        _assign_bone_vertex_groups(obj, verts, chains_used, props.mesh_envelope_factor)
        if not reuse_armature_mod or not any(
            m.type == 'ARMATURE' for m in obj.modifiers
        ):
            obj.modifiers.new(name="Armature", type='ARMATURE').object = source_obj


class BONE_OT_generate_mesh(Operator):
    """Generate a low-poly quad mesh from the selected pose bones"""
    bl_idname = "rig_weaver.generate_mesh"
    bl_label = "Generate Proxy Mesh"
    bl_description = (
        "Create a surface mesh from the selected bone chains in Pose Mode. "
        "Single chain produces a ribbon; multiple chains produce a connected "
        "cross-section surface. Intended as a low-poly simulation cage."
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.object is None or context.object.type != 'ARMATURE':
            return False
        if context.mode != 'POSE' or not context.selected_pose_bones:
            return False
        try:
            props = context.scene.rig_weaver_props
            if props.mesh_mode == 'TREE' and not _NUMPY_AVAILABLE:
                return False
        except AttributeError:
            pass
        return True

    def execute(self, context):
        props = context.scene.rig_weaver_props

        if props.mesh_mode == 'TREE' and not _NUMPY_AVAILABLE:
            self.report({'ERROR'}, "RigWeaver: TREE mode requires NumPy — not available in this Blender build.")
            return {'CANCELLED'}

        selected = set(context.selected_pose_bones)
        chains = _build_chains(selected)
        if not chains:
            self.report({'ERROR'}, "RigWeaver: No chains found in selection.")
            return {'CANCELLED'}

        source_obj = context.object
        mode = props.mesh_mode

        # ------------------------------------------------------------------
        # Single chain → always a ribbon regardless of mode
        # ------------------------------------------------------------------
        if len(chains) == 1:
            verts: list[Vector] = []
            faces: list[tuple[int, ...]] = []
            uvs: list[tuple[float, float]] | None = ([] if props.mesh_generate_uvs else None)
            _ribbon_from_chain(chains[0], props.mesh_ribbon_width,
                               props.mesh_bone_subdivisions, verts, faces, uvs)
            if not faces:
                self.report({'ERROR'}, "RigWeaver: No geometry could be generated.")
                return {'CANCELLED'}
            if props.mesh_triangulate:
                faces = _triangulate_faces(faces)
            obj = _create_mesh_object(props.mesh_output_name, verts, faces, source_obj, context)
            _apply_post_processing(obj, verts, uvs, chains, props, source_obj)
            if props.mesh_set_parent:
                obj.parent = source_obj
                obj.parent_type = 'OBJECT'
                obj.matrix_parent_inverse = source_obj.matrix_world.inverted()
            bpy.ops.pose.select_all(action='DESELECT')
            context.view_layer.objects.active = obj
            obj.select_set(True)
            self.report({'INFO'}, f"RigWeaver: Created '{obj.name}'.")
            return {'FINISHED'}

        # ------------------------------------------------------------------
        # INDIVIDUAL + Separate Objects → one object per chain
        # ------------------------------------------------------------------
        if mode == 'INDIVIDUAL' and props.mesh_split_objects:
            created: list = []
            for chain in chains:
                verts = []
                faces = []
                uvs = [] if props.mesh_generate_uvs else None
                _ribbon_from_chain(chain, props.mesh_ribbon_width,
                                   props.mesh_bone_subdivisions, verts, faces, uvs)
                if props.mesh_triangulate:
                    faces = _triangulate_faces(faces)
                if faces:
                    obj = _create_mesh_object(
                        f"{props.mesh_output_name}_{chain[0].name}", verts, faces, source_obj, context
                    )
                    _apply_post_processing(obj, verts, uvs, [chain], props, source_obj)
                    if props.mesh_set_parent:
                        obj.parent = source_obj
                        obj.parent_type = 'OBJECT'
                        obj.matrix_parent_inverse = source_obj.matrix_world.inverted()
                    created.append(obj)
            if not created:
                self.report({'ERROR'}, "RigWeaver: No geometry could be generated.")
                return {'CANCELLED'}
            bpy.ops.pose.select_all(action='DESELECT')
            for obj in created:
                obj.select_set(True)
            context.view_layer.objects.active = created[-1]
            self.report({'INFO'},
                        f"RigWeaver: Created {len(created)} object(s) from {len(chains)} chain(s).")
            return {'FINISHED'}

        # ------------------------------------------------------------------
        # All other modes → single combined object
        # ------------------------------------------------------------------
        result = _build_geometry(props, chains)
        if result is None:
            self.report({'ERROR'}, "RigWeaver: No geometry could be generated.")
            return {'CANCELLED'}
        all_verts, all_faces, all_uvs, chains_used = result

        obj = _create_mesh_object(props.mesh_output_name, all_verts, all_faces, source_obj, context)
        _apply_post_processing(obj, all_verts, all_uvs, chains_used, props, source_obj)
        if props.mesh_set_parent:
            obj.parent = source_obj
            obj.parent_type = 'OBJECT'
            obj.matrix_parent_inverse = source_obj.matrix_world.inverted()

        bpy.ops.pose.select_all(action='DESELECT')
        context.view_layer.objects.active = obj
        obj.select_set(True)
        self.report({'INFO'},
                    f"RigWeaver: Created '{obj.name}' with {len(all_faces)} face(s) "
                    f"from {len(chains)} chain(s).")
        return {'FINISHED'}


class BONE_OT_update_mesh(Operator):
    """Regenerate geometry of existing proxy mesh object(s) in-place, preserving modifiers"""
    bl_idname = "rig_weaver.update_mesh"
    bl_label = "Update Mesh"
    bl_description = (
        "Regenerate geometry of existing proxy mesh object(s) from this armature "
        "using current settings and selected bones, preserving modifiers and transforms"
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode != 'POSE':
            return False
        obj = context.object
        if obj is None or obj.type != 'ARMATURE':
            return False
        if not context.selected_pose_bones:
            return False
        try:
            props = context.scene.rig_weaver_props
            if props.mesh_mode == 'TREE' and not _NUMPY_AVAILABLE:
                return False
        except AttributeError:
            pass
        name = obj.name
        return any(
            o.get("rig_weaver_source") == name
            for o in bpy.data.objects
            if o.type == 'MESH'
        )

    def execute(self, context):
        props = context.scene.rig_weaver_props

        if props.mesh_mode == 'TREE' and not _NUMPY_AVAILABLE:
            self.report({'ERROR'}, "RigWeaver: TREE mode requires NumPy — not available in this Blender build.")
            return {'CANCELLED'}

        selected = set(context.selected_pose_bones)
        chains = _build_chains(selected)
        if not chains:
            self.report({'ERROR'}, "RigWeaver: No chains found in selection.")
            return {'CANCELLED'}

        source_obj = context.object
        mode = props.mesh_mode

        tagged = [
            o for o in bpy.data.objects
            if o.type == 'MESH' and o.get("rig_weaver_source") == source_obj.name
        ]

        # ------------------------------------------------------------------
        # INDIVIDUAL + Separate Objects → match by name, create if missing
        # ------------------------------------------------------------------
        if mode == 'INDIVIDUAL' and props.mesh_split_objects:
            updated, created = 0, 0
            for chain in chains:
                verts: list[Vector] = []
                faces: list[tuple[int, ...]] = []
                uvs: list[tuple[float, float]] | None = (
                    [] if props.mesh_generate_uvs else None
                )
                _ribbon_from_chain(chain, props.mesh_ribbon_width,
                                   props.mesh_bone_subdivisions, verts, faces, uvs)
                if props.mesh_triangulate:
                    faces = _triangulate_faces(faces)
                if not faces:
                    continue
                target_name = f"{props.mesh_output_name}_{chain[0].name}"
                existing = next((o for o in tagged if o.name == target_name), None)
                if existing:
                    _replace_mesh_data(existing, verts, faces)
                    _apply_post_processing(
                        existing, verts, uvs, [chain], props, source_obj,
                        reuse_armature_mod=True)
                    if props.mesh_set_parent:
                        existing.parent = source_obj
                        existing.parent_type = 'OBJECT'
                        existing.matrix_parent_inverse = source_obj.matrix_world.inverted()
                    updated += 1
                else:
                    obj = _create_mesh_object(
                        target_name, verts, faces, source_obj, context)
                    _apply_post_processing(obj, verts, uvs, [chain], props, source_obj)
                    if props.mesh_set_parent:
                        obj.parent = source_obj
                        obj.parent_type = 'OBJECT'
                        obj.matrix_parent_inverse = source_obj.matrix_world.inverted()
                    created += 1
            self.report(
                {'INFO'},
                f"RigWeaver: Updated {updated}, created {created} object(s).")
            return {'FINISHED'}

        # ------------------------------------------------------------------
        # All other modes → update the first tagged object in-place
        # ------------------------------------------------------------------
        if not tagged:
            self.report({'ERROR'}, "RigWeaver: No proxy mesh found to update. Use Generate Proxy Mesh instead.")
            return {'CANCELLED'}

        result = _build_geometry(props, chains)
        if result is None:
            self.report({'ERROR'}, "RigWeaver: No geometry could be generated.")
            return {'CANCELLED'}
        all_verts, all_faces, all_uvs, chains_used = result

        target = tagged[0]
        _replace_mesh_data(target, all_verts, all_faces)
        target.name = props.mesh_output_name
        target.data.name = props.mesh_output_name
        _apply_post_processing(
            target, all_verts, all_uvs, chains_used, props, source_obj,
            reuse_armature_mod=True)
        if props.mesh_set_parent:
            target.parent = source_obj
            target.parent_type = 'OBJECT'
            target.matrix_parent_inverse = source_obj.matrix_world.inverted()

        bpy.ops.pose.select_all(action='DESELECT')
        context.view_layer.objects.active = target
        target.select_set(True)
        self.report(
            {'INFO'},
            f"RigWeaver: Updated '{target.name}' with {len(all_faces)} face(s) "
            f"from {len(chains)} chain(s).")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Envelope preview — viewport draw overlay
# ---------------------------------------------------------------------------

_envelope_draw_handle = None  # module-level handle; one active per Blender session


def deactivate_envelope_preview(props, context) -> None:
    """Remove the envelope draw handler and clear the active flag."""
    global _envelope_draw_handle
    if _envelope_draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_envelope_draw_handle, 'WINDOW')
        _envelope_draw_handle = None
    props.ui_envelope_preview_active = False
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


def _draw_envelope_circles() -> None:
    """
    SpaceView3D POST_VIEW callback.

    Draws three orthogonal wire circles at each selected pose bone's head and
    tail in world space.  Radius = bone_length × mesh_envelope_factor, matching
    the weight calculation in _assign_bone_vertex_groups exactly.
    """
    if not _GPU_AVAILABLE:
        return

    context = bpy.context
    obj = context.object
    if obj is None or obj.type != 'ARMATURE' or obj.mode != 'POSE':
        return

    props = context.scene.rig_weaver_props
    factor = props.mesh_envelope_factor
    matrix = obj.matrix_world

    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    shader.bind()
    shader.uniform_float("color", (0.9, 0.5, 0.1, 0.7))
    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(1.5)

    N = 32
    angles = [2.0 * math.pi * i / N for i in range(N + 1)]

    for pb in obj.pose.bones:
        if not pb.bone.select:
            continue
        head_w = matrix @ pb.head
        tail_w = matrix @ pb.tail
        r = (tail_w - head_w).length * factor
        if r < 1e-6:
            continue

        for center in (head_w, tail_w):
            for ax0, ax1 in ((0, 1), (1, 2), (0, 2)):
                verts = []
                for a in angles:
                    v = [0.0, 0.0, 0.0]
                    v[ax0] = math.cos(a) * r
                    v[ax1] = math.sin(a) * r
                    verts.append((center[0] + v[0],
                                  center[1] + v[1],
                                  center[2] + v[2]))
                batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": verts})
                batch.draw(shader)

    gpu.state.blend_set('NONE')
    gpu.state.line_width_set(1.0)


class BONE_OT_preview_envelope_weights(Operator):
    bl_idname = "rig_weaver.preview_envelope_weights"
    bl_label = "Preview Weight Radius"
    bl_description = (
        "Toggle a wireframe overlay in the viewport showing the weight radius "
        "used for bone weight assignment. Radius = bone length × Weight Radius"
    )
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        if not _GPU_AVAILABLE:
            return False
        return (context.object is not None
                and context.object.type == 'ARMATURE')

    def execute(self, context):
        global _envelope_draw_handle
        props = context.scene.rig_weaver_props

        if _envelope_draw_handle is not None:
            deactivate_envelope_preview(props, context)
        else:
            _envelope_draw_handle = bpy.types.SpaceView3D.draw_handler_add(
                _draw_envelope_circles, (), 'WINDOW', 'POST_VIEW')
            props.ui_envelope_preview_active = True

        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    BONE_OT_generate_mesh,
    BONE_OT_update_mesh,
    BONE_OT_preview_envelope_weights,
)


@persistent
def _on_load_post_envelope_preview(_filepath):
    """Clear stale envelope preview draw handler when a new file is loaded."""
    global _envelope_draw_handle
    if _envelope_draw_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_envelope_draw_handle, 'WINDOW')
        except Exception:
            pass
        _envelope_draw_handle = None
    try:
        bpy.context.scene.rig_weaver_props.ui_envelope_preview_active = False
    except Exception:
        pass


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.app.handlers.load_post.append(_on_load_post_envelope_preview)


def unregister():
    global _envelope_draw_handle
    if _envelope_draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_envelope_draw_handle, 'WINDOW')
        _envelope_draw_handle = None
    if _on_load_post_envelope_preview in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post_envelope_preview)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
