"""
Operator: Generate a bone cage armature from the active mesh.

Uses cylindrical decomposition:
  1. Project all vertices into (angle θ, height h) around the mesh's up axis.
  2. Bin into N_chains × N_levels grid.
  3. Centroid of each bin → one bone level position.
  4. Build an armature with N_chains radial chains, each N_bones bones long.

Intended for garment rigging workflows (skirts, sleeves, capes) where the user
wants a cage armature that can drive a cloth simulation proxy.
"""
from __future__ import annotations

import math
from types import SimpleNamespace

import bpy
from bpy.app.handlers import persistent
from bpy.types import Operator
from mathutils import Vector

try:
    import numpy as _np
    _NUMPY_AVAILABLE = True
except ImportError:
    _np = None
    _NUMPY_AVAILABLE = False

try:
    import gpu
    from gpu_extras.batch import batch_for_shader
    _GPU_AVAILABLE = True
except ImportError:
    _GPU_AVAILABLE = False


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

_AXIS_VECTORS: dict[str, Vector] = {
    '+X': Vector((1, 0, 0)),
    '-X': Vector((-1, 0, 0)),
    '+Y': Vector((0, 1, 0)),
    '-Y': Vector((0, -1, 0)),
    '+Z': Vector((0, 0, 1)),
    '-Z': Vector((0, 0, -1)),
}


def _get_up_vector(verts_world: list[Vector], axis_setting: str) -> Vector:
    """
    Return a normalised up vector.

    Explicit settings (+X … -Z) return the corresponding world axis directly.
    AUTO runs PCA via NumPy SVD (same pattern as _tree_surface_mesh) and
    returns the first principal component, flipped to the +Z hemisphere.
    """
    if axis_setting != 'AUTO':
        return _AXIS_VECTORS[axis_setting].copy()

    arr = _np.array([(v.x, v.y, v.z) for v in verts_world], dtype=float)
    centroid = arr.mean(axis=0)
    centered = arr - centroid
    _, _, Vt = _np.linalg.svd(centered, full_matrices=False)
    up = Vector(tuple(float(x) for x in Vt[0]))
    if up.z < 0:
        up = -up
    return up.normalized()


def _perpendicular_axes(up: Vector) -> tuple[Vector, Vector]:
    """Return two unit vectors (right, forward) forming a frame with up."""
    right = up.orthogonal().normalized()
    forward = up.cross(right).normalized()
    return right, forward


def _fill_missing_levels(
    levels: list[Vector | None],
    h_min: float,
    h_max: float,
    up: Vector,
    centroid: Vector,
    right: Vector,
    forward: Vector,
    sector_angle: float,
    median_radius: float,
) -> list[Vector]:
    """
    Replace None entries with interpolated / extrapolated positions.

    - Between two known neighbours: linear interpolation.
    - Leading/trailing Nones: clamp to nearest known.
    - Fully-empty chain: fall back to ideal cylindrical surface position.
    """
    n = len(levels)

    def _ideal(i: int) -> Vector:
        frac = i / max(n - 1, 1)
        h = h_min + frac * (h_max - h_min)
        return (centroid
                + up * h
                + right * (math.cos(sector_angle) * median_radius)
                + forward * (math.sin(sector_angle) * median_radius))

    for i in range(n):
        if levels[i] is not None:
            continue
        prev_i = next((j for j in range(i - 1, -1, -1) if levels[j] is not None), None)
        next_i = next((j for j in range(i + 1, n) if levels[j] is not None), None)
        if prev_i is not None and next_i is not None:
            t = (i - prev_i) / (next_i - prev_i)
            levels[i] = levels[prev_i].lerp(levels[next_i], t)  # type: ignore[union-attr]
        elif prev_i is not None:
            levels[i] = levels[prev_i]
        elif next_i is not None:
            levels[i] = levels[next_i]
        else:
            levels[i] = _ideal(i)

    return levels  # type: ignore[return-value]  — all None entries are now filled


def _compute_rig_bone_positions(
    mesh_obj: "bpy.types.Object",
    props,
) -> "list[list[Vector]] | None":
    """
    Run the cylindrical decomposition for the given mesh and properties.

    Returns a list of N_chains chains, each a list of N_bones+1 world-space
    Vector positions ordered top→bottom (root first).  Returns None if the
    mesh has too few vertices or AUTO axis is requested without NumPy.
    """
    if props.rig_up_axis == 'AUTO' and not _NUMPY_AVAILABLE:
        return None

    verts_world: list[Vector] = [
        mesh_obj.matrix_world @ v.co for v in mesh_obj.data.vertices
    ]
    if len(verts_world) < 4:
        return None

    # Coordinate frame
    up = _get_up_vector(verts_world, props.rig_up_axis)
    centroid = sum(verts_world, Vector()) / len(verts_world)
    right, forward = _perpendicular_axes(up)

    # Cylindrical projection
    thetas: list[float] = []
    heights: list[float] = []
    radii: list[float] = []
    for v in verts_world:
        rel = v - centroid
        h = rel.dot(up)
        proj = rel - up * h
        r = proj.length
        theta = math.atan2(proj.dot(forward), proj.dot(right)) if r > 1e-6 else 0.0
        thetas.append(theta)
        heights.append(h)
        radii.append(r)

    h_min = min(heights)
    h_max = max(heights)
    median_radius = sorted(radii)[len(radii) // 2]

    # Bin vertices into (n_chains × n_levels) grid
    n_chains = props.rig_chains
    n_levels = props.rig_bones_per_chain + 1   # N bones require N+1 level positions
    bins: list[list[list[Vector]]] = [
        [[] for _ in range(n_levels)] for _ in range(n_chains)
    ]
    for v, theta, h in zip(verts_world, thetas, heights):
        ci = int((theta + math.pi) / (2 * math.pi) * n_chains) % n_chains
        if h_max > h_min:
            li = min(
                int((h - h_min) / (h_max - h_min) * n_levels),
                n_levels - 1,
            )
        else:
            li = 0
        bins[ci][li].append(v)

    # Bin centroids + fill empty bins, then reverse so root is at top
    sector_angles = [
        -math.pi + (ci + 0.5) * (2 * math.pi / n_chains)
        for ci in range(n_chains)
    ]
    bone_levels: list[list[Vector]] = []
    for ci in range(n_chains):
        raw: list[Vector | None] = [
            (sum(bins[ci][li], Vector()) / len(bins[ci][li])
             if bins[ci][li] else None)
            for li in range(n_levels)
        ]
        filled = _fill_missing_levels(
            raw, h_min, h_max, up, centroid,
            right, forward, sector_angles[ci], median_radius,
        )
        # Reverse so level[0] = h_max (waist/top) → root bone HEAD there
        bone_levels.append(list(reversed(filled)))

    return bone_levels


# ---------------------------------------------------------------------------
# Viewport preview
# ---------------------------------------------------------------------------

_rig_preview_handle = None   # SpaceView3D draw handler
_rig_preview_lines: list[tuple] = []   # flat (head_xyz, tail_xyz) pairs


def _update_rig_preview_cache(context) -> None:
    """Recompute bone line pairs and tag all VIEW_3D areas for redraw."""
    global _rig_preview_lines
    obj = context.object
    props = context.scene.rig_weaver_props

    if obj is None or obj.type != 'MESH':
        _rig_preview_lines = []
    else:
        bone_levels = _compute_rig_bone_positions(obj, props)
        if bone_levels is None:
            _rig_preview_lines = []
        else:
            lines = []
            for chain in bone_levels:
                for li in range(len(chain) - 1):
                    lines.append((chain[li].to_tuple(), chain[li + 1].to_tuple()))
            _rig_preview_lines = lines

    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


def _draw_rig_preview() -> None:
    """SpaceView3D POST_VIEW callback — draws bone cage preview lines and (optionally) envelope circles."""
    if not _GPU_AVAILABLE or not _rig_preview_lines:
        return

    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    shader.bind()
    gpu.state.blend_set('ALPHA')

    # ── Bone lines (green) ───────────────────────────────────────────────────
    line_verts = []
    for head, tail in _rig_preview_lines:
        line_verts.append(head)
        line_verts.append(tail)

    shader.uniform_float("color", (0.2, 0.9, 0.4, 0.85))
    gpu.state.line_width_set(2.0)
    batch = batch_for_shader(shader, 'LINES', {"pos": line_verts})
    batch.draw(shader)

    # ── Envelope circles (orange) — only when Assign Weights is on ──────────
    try:
        props = bpy.context.scene.rig_weaver_props
        show_envelope = props.rig_auto_weights
        factor = props.rig_envelope_factor
    except (AttributeError, ReferenceError):
        show_envelope = False

    if show_envelope:
        SEG = 32
        angles = [2.0 * math.pi * i / SEG for i in range(SEG + 1)]
        shader.uniform_float("color", (0.9, 0.5, 0.1, 0.7))
        gpu.state.line_width_set(1.5)

        for head, tail in _rig_preview_lines:
            hx, hy, hz = head
            tx, ty, tz = tail
            bone_len = math.sqrt(
                (tx - hx) ** 2 + (ty - hy) ** 2 + (tz - hz) ** 2
            )
            r = bone_len * factor
            if r < 1e-6:
                continue

            for center in (head, tail):
                cx, cy, cz = center
                for ax0, ax1 in ((0, 1), (1, 2), (0, 2)):
                    ring = []
                    for a in angles:
                        pt = [cx, cy, cz]
                        pt[ax0] += math.cos(a) * r
                        pt[ax1] += math.sin(a) * r
                        ring.append(tuple(pt))
                    b = batch_for_shader(shader, 'LINE_STRIP', {"pos": ring})
                    b.draw(shader)

    gpu.state.blend_set('NONE')
    gpu.state.line_width_set(1.0)


def deactivate_rig_preview(props, context) -> None:
    """Remove the rig preview draw handler and clear the active flag."""
    global _rig_preview_handle
    if _rig_preview_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_rig_preview_handle, 'WINDOW')
        _rig_preview_handle = None
    props.ui_rig_preview_active = False
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class BONE_OT_preview_rig_from_mesh(Operator):
    bl_idname = "rig_weaver.preview_rig_from_mesh"
    bl_label = "Preview Rig"
    bl_description = (
        "Toggle a viewport overlay showing where the generated bones will be "
        "placed. Updates live as Chains, Bones per Chain, and Up Axis change."
    )
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return (
            _GPU_AVAILABLE
            and context.object is not None
            and context.object.type == 'MESH'
            and context.object.mode == 'OBJECT'
        )

    def execute(self, context):
        global _rig_preview_handle
        props = context.scene.rig_weaver_props

        if _rig_preview_handle is not None:
            deactivate_rig_preview(props, context)
        else:
            _update_rig_preview_cache(context)
            _rig_preview_handle = bpy.types.SpaceView3D.draw_handler_add(
                _draw_rig_preview, (), 'WINDOW', 'POST_VIEW',
            )
            props.ui_rig_preview_active = True
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
        return {'FINISHED'}


class BONE_OT_generate_rig_from_mesh(Operator):
    bl_idname = "rig_weaver.generate_rig_from_mesh"
    bl_label = "Generate Rig from Mesh"
    bl_description = (
        "Generate a bone cage armature from the active mesh using cylindrical "
        "decomposition. Bones radiate around the mesh's up axis from top to bottom."
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.object is not None
                and context.object.type == 'MESH'
                and context.object.mode == 'OBJECT')

    def execute(self, context):
        # ── NumPy guard ───────────────────────────────────────────────────────
        props = context.scene.rig_weaver_props
        if not _NUMPY_AVAILABLE and props.rig_up_axis == 'AUTO':
            self.report(
                {'ERROR'},
                "RigWeaver: AUTO axis detection requires NumPy — "
                "not available in this Blender build. Choose an explicit axis.",
            )
            return {'CANCELLED'}

        mesh_obj = context.object

        # ── Steps 1–5: cylindrical decomposition ─────────────────────────────
        bone_levels = _compute_rig_bone_positions(mesh_obj, props)
        if bone_levels is None:
            self.report({'ERROR'}, "RigWeaver: Mesh has too few vertices.")
            return {'CANCELLED'}

        n_chains = props.rig_chains
        n_levels = props.rig_bones_per_chain + 1

        # World-space verts needed later for weight assignment
        verts_world: list[Vector] = [
            mesh_obj.matrix_world @ v.co for v in mesh_obj.data.vertices
        ]

        # ── 6. Create armature at world origin ────────────────────────────────
        arm_data = bpy.data.armatures.new(props.rig_output_name)
        arm_obj = bpy.data.objects.new(props.rig_output_name, arm_data)
        arm_obj.location = Vector((0.0, 0.0, 0.0))
        for coll in mesh_obj.users_collection:
            coll.objects.link(arm_obj)
        arm_obj.show_in_front = True
        arm_obj["rig_weaver_source_mesh"] = mesh_obj.name

        bpy.ops.object.select_all(action='DESELECT')
        arm_obj.select_set(True)
        context.view_layer.objects.active = arm_obj

        if 'FINISHED' not in bpy.ops.object.mode_set(mode='EDIT'):
            self.report({'ERROR'}, "RigWeaver: Could not enter Edit Mode on new armature.")
            bpy.data.objects.remove(arm_obj)
            bpy.data.armatures.remove(arm_data)
            return {'CANCELLED'}

        # ── 7. Create bones ───────────────────────────────────────────────────
        # Build proxy objects alongside name lists so we never need to look up
        # arm_obj.pose.bones after Edit Mode — that lookup is unreliable for
        # freshly created armatures on some mesh topologies (e.g. cube).
        all_bone_name_chains: list[list[str]] = []
        all_bone_proxy_chains: list[list] = []
        for ci in range(n_chains):
            levels = bone_levels[ci]   # already reversed (top → bottom)
            chain_names: list[str] = []
            chain_proxies: list = []
            prev_eb = None
            for li in range(n_levels - 1):
                bone_name = f"{props.rig_output_name}_{ci:02d}_{li:02d}"
                eb = arm_data.edit_bones.new(bone_name)
                eb.head = levels[li]
                eb.tail = levels[li + 1]
                if prev_eb is not None:
                    eb.parent = prev_eb
                    eb.use_connect = True
                prev_eb = eb
                chain_names.append(eb.name)
                # Capture head/tail while still in Edit Mode (.copy() required —
                # EditBone Vector references become invalid after mode switch).
                chain_proxies.append(SimpleNamespace(
                    name=eb.name,
                    head=eb.head.copy(),
                    tail=eb.tail.copy(),
                ))
            if chain_names:
                all_bone_name_chains.append(chain_names)
                all_bone_proxy_chains.append(chain_proxies)

        if not all_bone_name_chains:
            bpy.ops.object.mode_set(mode='OBJECT')
            self.report({'ERROR'}, "RigWeaver: No bones could be generated.")
            return {'CANCELLED'}

        if 'FINISHED' not in bpy.ops.object.mode_set(mode='OBJECT'):
            self.report({'ERROR'}, "RigWeaver: Could not return to Object Mode.")
            return {'CANCELLED'}

        # ── 8. Auto-weights ───────────────────────────────────────────────────
        # Use proxy chain data captured during Edit Mode — avoids any dependency
        # on arm_obj.pose.bones which is unreliable for newly created armatures.
        if props.rig_auto_weights:
            from . import mesh_gen_ops
            mesh_gen_ops._assign_bone_vertex_groups(
                mesh_obj, verts_world, all_bone_proxy_chains, props.rig_envelope_factor,
            )
            arm_mods = [m for m in mesh_obj.modifiers if m.type == 'ARMATURE']
            if arm_mods:
                arm_mods[0].object = arm_obj
                for m in arm_mods[1:]:
                    mesh_obj.modifiers.remove(m)
            else:
                mod = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
                mod.object = arm_obj

        # ── 9. Optional re-parent ─────────────────────────────────────────────
        if props.rig_set_parent:
            mesh_obj.parent = arm_obj
            mesh_obj.parent_type = 'OBJECT'
            mesh_obj.matrix_parent_inverse = arm_obj.matrix_world.inverted()

        # ── 10. Restore selection + deactivate preview ────────────────────────
        context.view_layer.objects.active = arm_obj
        arm_obj.select_set(True)
        if props.ui_rig_preview_active:
            deactivate_rig_preview(props, context)
        bone_count = sum(len(c) for c in all_bone_name_chains)
        self.report(
            {'INFO'},
            f"RigWeaver: Created '{arm_obj.name}' with {bone_count} bone(s).",
        )
        return {'FINISHED'}


class BONE_OT_update_rig_from_mesh(Operator):
    bl_idname = "rig_weaver.update_rig_from_mesh"
    bl_label = "Update Rig"
    bl_description = (
        "Regenerate the existing bone cage armature in-place using the current "
        "settings, preserving the Armature modifier on the source mesh."
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.object is None or context.object.type != 'MESH':
            return False
        if context.object.mode != 'OBJECT':
            return False
        name = context.object.name
        return any(
            o.get("rig_weaver_source_mesh") == name
            for o in bpy.data.objects
            if o.type == 'ARMATURE'
        )

    def execute(self, context):
        props = context.scene.rig_weaver_props
        if not _NUMPY_AVAILABLE and props.rig_up_axis == 'AUTO':
            self.report(
                {'ERROR'},
                "RigWeaver: AUTO axis detection requires NumPy — "
                "not available in this Blender build. Choose an explicit axis.",
            )
            return {'CANCELLED'}

        mesh_obj = context.object

        # ── Re-compute bone positions ─────────────────────────────────────────
        bone_levels = _compute_rig_bone_positions(mesh_obj, props)
        if bone_levels is None:
            self.report({'ERROR'}, "RigWeaver: Mesh has too few vertices.")
            return {'CANCELLED'}

        n_chains = props.rig_chains
        n_levels = props.rig_bones_per_chain + 1

        verts_world: list[Vector] = [
            mesh_obj.matrix_world @ v.co for v in mesh_obj.data.vertices
        ]

        # ── Find the tagged armature ──────────────────────────────────────────
        arm_obj = next(
            (o for o in bpy.data.objects
             if o.type == 'ARMATURE'
             and o.get("rig_weaver_source_mesh") == mesh_obj.name),
            None,
        )
        if arm_obj is None:
            self.report({'ERROR'}, "RigWeaver: No tagged armature found for this mesh.")
            return {'CANCELLED'}
        arm_data = arm_obj.data

        # ── Enter Edit Mode and rebuild bones ─────────────────────────────────
        bpy.ops.object.select_all(action='DESELECT')
        arm_obj.select_set(True)
        context.view_layer.objects.active = arm_obj

        if 'FINISHED' not in bpy.ops.object.mode_set(mode='EDIT'):
            self.report({'ERROR'}, "RigWeaver: Could not enter Edit Mode on armature.")
            return {'CANCELLED'}

        for eb in list(arm_data.edit_bones):
            arm_data.edit_bones.remove(eb)

        all_bone_name_chains: list[list[str]] = []
        all_bone_proxy_chains: list[list] = []
        for ci in range(n_chains):
            levels = bone_levels[ci]
            chain_names: list[str] = []
            chain_proxies: list = []
            prev_eb = None
            for li in range(n_levels - 1):
                bone_name = f"{props.rig_output_name}_{ci:02d}_{li:02d}"
                eb = arm_data.edit_bones.new(bone_name)
                eb.head = levels[li]
                eb.tail = levels[li + 1]
                if prev_eb is not None:
                    eb.parent = prev_eb
                    eb.use_connect = True
                prev_eb = eb
                chain_names.append(eb.name)
                chain_proxies.append(SimpleNamespace(
                    name=eb.name,
                    head=eb.head.copy(),
                    tail=eb.tail.copy(),
                ))
            if chain_names:
                all_bone_name_chains.append(chain_names)
                all_bone_proxy_chains.append(chain_proxies)

        if not all_bone_name_chains:
            bpy.ops.object.mode_set(mode='OBJECT')
            self.report({'ERROR'}, "RigWeaver: No bones could be generated.")
            return {'CANCELLED'}

        if 'FINISHED' not in bpy.ops.object.mode_set(mode='OBJECT'):
            self.report({'ERROR'}, "RigWeaver: Could not return to Object Mode.")
            return {'CANCELLED'}

        # ── Rename armature to match current output name ──────────────────────
        arm_obj.name = props.rig_output_name
        arm_data.name = props.rig_output_name

        # ── Re-assign weights if enabled ──────────────────────────────────────
        if props.rig_auto_weights:
            mesh_obj.vertex_groups.clear()
            from . import mesh_gen_ops
            mesh_gen_ops._assign_bone_vertex_groups(
                mesh_obj, verts_world, all_bone_proxy_chains, props.rig_envelope_factor,
            )
            arm_mods = [m for m in mesh_obj.modifiers if m.type == 'ARMATURE']
            if arm_mods:
                arm_mods[0].object = arm_obj
                for m in arm_mods[1:]:
                    mesh_obj.modifiers.remove(m)
            else:
                mod = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
                mod.object = arm_obj

        # ── Optional re-parent ────────────────────────────────────────────────
        if props.rig_set_parent:
            mesh_obj.parent = arm_obj
            mesh_obj.parent_type = 'OBJECT'
            mesh_obj.matrix_parent_inverse = arm_obj.matrix_world.inverted()

        # ── Restore selection + deactivate preview ────────────────────────────
        context.view_layer.objects.active = arm_obj
        arm_obj.select_set(True)
        if props.ui_rig_preview_active:
            deactivate_rig_preview(props, context)
        bone_count = sum(len(c) for c in all_bone_name_chains)
        self.report(
            {'INFO'},
            f"RigWeaver: Updated '{arm_obj.name}' with {bone_count} bone(s).",
        )
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    BONE_OT_preview_rig_from_mesh,
    BONE_OT_generate_rig_from_mesh,
    BONE_OT_update_rig_from_mesh,
)


@persistent
def _on_load_post_rig_preview(_filepath):
    """Clear stale rig preview draw handler when a new file is loaded."""
    global _rig_preview_handle, _rig_preview_lines
    if _rig_preview_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_rig_preview_handle, 'WINDOW')
        except Exception:
            pass
        _rig_preview_handle = None
    _rig_preview_lines = []
    try:
        bpy.context.scene.rig_weaver_props.ui_rig_preview_active = False
    except Exception:
        pass


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.app.handlers.load_post.append(_on_load_post_rig_preview)


def unregister():
    global _rig_preview_handle
    if _rig_preview_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_rig_preview_handle, 'WINDOW')
        _rig_preview_handle = None
    if _on_load_post_rig_preview in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post_rig_preview)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
