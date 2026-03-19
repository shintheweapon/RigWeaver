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

import bpy
from bpy.types import Operator
from mathutils import Vector

try:
    import numpy as _np
    _NUMPY_AVAILABLE = True
except ImportError:
    _np = None
    _NUMPY_AVAILABLE = False


# ---------------------------------------------------------------------------
# Helpers
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


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------

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
        if not _NUMPY_AVAILABLE and context.scene.rig_weaver_props.rig_up_axis == 'AUTO':
            self.report(
                {'ERROR'},
                "RigWeaver: AUTO axis detection requires NumPy — "
                "not available in this Blender build. Choose an explicit axis.",
            )
            return {'CANCELLED'}

        mesh_obj = context.object
        props = context.scene.rig_weaver_props

        # ── 1. World-space vertices ───────────────────────────────────────────
        verts_world: list[Vector] = [
            mesh_obj.matrix_world @ v.co for v in mesh_obj.data.vertices
        ]
        if len(verts_world) < 4:
            self.report({'ERROR'}, "RigWeaver: Mesh has too few vertices.")
            return {'CANCELLED'}

        # ── 2. Coordinate frame ───────────────────────────────────────────────
        up = _get_up_vector(verts_world, props.rig_up_axis)
        centroid = sum(verts_world, Vector()) / len(verts_world)
        right, forward = _perpendicular_axes(up)

        # ── 3. Cylindrical projection ─────────────────────────────────────────
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

        # ── 4. Bin vertices into (n_chains × n_levels) grid ───────────────────
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

        # ── 5. Bin centroids + fill empty bins ────────────────────────────────
        # Pre-compute the representative angle of each sector's centre line
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
            bone_levels.append(filled)

        # ── 6. Create armature at world origin ────────────────────────────────
        # Placing at origin means armature-local space == world space,
        # which lets us set edit-bone positions directly from world coords.
        arm_data = bpy.data.armatures.new(props.rig_output_name)
        arm_obj = bpy.data.objects.new(props.rig_output_name, arm_data)
        arm_obj.location = Vector((0.0, 0.0, 0.0))
        for coll in mesh_obj.users_collection:
            coll.objects.link(arm_obj)
        arm_obj.show_in_front = True

        bpy.ops.object.select_all(action='DESELECT')
        arm_obj.select_set(True)
        context.view_layer.objects.active = arm_obj

        if 'FINISHED' not in bpy.ops.object.mode_set(mode='EDIT'):
            self.report({'ERROR'}, "RigWeaver: Could not enter Edit Mode on new armature.")
            bpy.data.objects.remove(arm_obj)
            bpy.data.armatures.remove(arm_data)
            return {'CANCELLED'}

        # ── 7. Create bones ───────────────────────────────────────────────────
        all_bone_name_chains: list[list[str]] = []
        for ci in range(n_chains):
            # Reverse so level[0] = h_max (waist/top) → root bone HEAD there,
            # and level[-1] = h_min (hem/bottom) → chain tips point downward.
            levels = list(reversed(bone_levels[ci]))
            chain_names: list[str] = []
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
                chain_names.append(bone_name)
            if chain_names:
                all_bone_name_chains.append(chain_names)

        if not all_bone_name_chains:
            bpy.ops.object.mode_set(mode='OBJECT')
            self.report({'ERROR'}, "RigWeaver: No bones could be generated.")
            return {'CANCELLED'}

        if 'FINISHED' not in bpy.ops.object.mode_set(mode='OBJECT'):
            self.report({'ERROR'}, "RigWeaver: Could not return to Object Mode.")
            return {'CANCELLED'}

        # ── 8. Auto-weights ───────────────────────────────────────────────────
        # Armature is at world origin so pose_bone.head/.tail == world space.
        if props.rig_auto_weights:
            pose_chains = [
                [arm_obj.pose.bones[name] for name in chain]
                for chain in all_bone_name_chains
            ]
            from . import mesh_gen_ops
            mesh_gen_ops._assign_bone_vertex_groups(
                mesh_obj, verts_world, pose_chains, props.rig_envelope_factor,
            )
            mod = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
            mod.object = arm_obj

        # ── 9. Restore selection ──────────────────────────────────────────────
        context.view_layer.objects.active = arm_obj
        arm_obj.select_set(True)
        bone_count = sum(len(c) for c in all_bone_name_chains)
        self.report(
            {'INFO'},
            f"RigWeaver: Created '{arm_obj.name}' with {bone_count} bone(s).",
        )
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (BONE_OT_generate_rig_from_mesh,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
