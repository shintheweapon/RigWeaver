"""
Operator: Generate a low-poly surface mesh from selected pose bones.

Intended for cloth / softbody simulation setups. No vertex groups or
weights are created — the mesh is plain geometry that follows the bone
positions at the moment of generation.

Supports:
  - Simple single chains  → a quad strip
  - Branching hierarchies (hair, skirt) → quad grid between adjacent chains
  - Optional loop closure (skirt ring)
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


def _chain_verts(chain: list) -> list[Vector]:
    """
    Return world-space vertex positions for a chain.
    N bones → N+1 positions: head of each bone + tail of the last one.
    """
    positions = [Vector(b.head) for b in chain]
    positions.append(Vector(chain[-1].tail))
    return positions


def _sort_chains(chains: list[list], parent_bone) -> list[list]:
    """
    Sort chains by their angular position around the parent bone's axis.
    When no parent exists, sort by the angle of the chain root projected
    onto the XY plane (fallback for root-level selections).
    """
    if len(chains) <= 1:
        return chains

    if parent_bone is not None:
        # Use parent bone axis as the sorting axis
        axis = (Vector(parent_bone.tail) - Vector(parent_bone.head))
        if axis.length < 1e-6:
            axis = Vector((0.0, 0.0, 1.0))
        else:
            axis.normalize()
        origin = Vector(parent_bone.tail)  # where all chains start from
    else:
        axis = Vector((0.0, 0.0, 1.0))
        # Centroid of all chain roots as origin
        roots = [Vector(c[0].head) for c in chains]
        origin = sum(roots, Vector()) / len(roots)

    # Build a local frame: axis = Z, pick arbitrary perpendicular X
    z = axis
    arbitrary = Vector((1.0, 0.0, 0.0))
    if abs(z.dot(arbitrary)) > 0.99:
        arbitrary = Vector((0.0, 1.0, 0.0))
    x = z.cross(arbitrary)
    x.normalize()
    y = z.cross(x)
    y.normalize()

    def angle_key(chain):
        head = Vector(chain[0].head)
        delta = head - origin
        px = delta.dot(x)
        py = delta.dot(y)
        return math.atan2(py, px)

    return sorted(chains, key=angle_key)


def _fill_between(
    verts_A: list[Vector],
    verts_B: list[Vector],
    vert_list: list[Vector],
    face_list: list[tuple[int, ...]],
) -> None:
    """
    Fill quads between two vertex sequences A and B.
    Appends new vertices to vert_list and faces to face_list.
    Stops at the shorter sequence depth.
    """
    depth = min(len(verts_A), len(verts_B))
    if depth < 2:
        return

    base = len(vert_list)

    # Append all vertices for both chains (deduplicated later if needed)
    for v in verts_A[:depth]:
        vert_list.append(v)
    for v in verts_B[:depth]:
        vert_list.append(v)

    # Indices: A occupies [base .. base+depth-1], B [base+depth .. base+2*depth-1]
    for i in range(depth - 1):
        a0 = base + i
        a1 = base + i + 1
        b0 = base + depth + i
        b1 = base + depth + i + 1
        face_list.append((a0, a1, b1, b0))


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------

class BONE_OT_generate_mesh(Operator):
    """Generate a low-poly quad mesh from the selected pose bones"""
    bl_idname = "bone_util.generate_mesh"
    bl_label = "Generate Bone Mesh"
    bl_description = (
        "Create a quad-mesh surface from the selected bones in Pose Mode. "
        "Intended as a low-poly simulation cage (cloth, softbody)."
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

        if len(chains) == 1:
            self.report(
                {'WARNING'},
                "ArmExt: Only one chain selected — cannot fill a surface with a single chain."
            )
            return {'CANCELLED'}

        # --- Group chains by their immediate parent bone ---
        groups: dict = {}
        for chain in chains:
            key_bone = chain[0].parent  # may be None
            key = key_bone.name if key_bone else "__root__"
            groups.setdefault(key, (key_bone, []))
            groups[key][1].append(chain)

        # --- Build geometry ---
        all_verts: list[Vector] = []
        all_faces: list[tuple[int, ...]] = []

        for key, (parent_bone, group_chains) in groups.items():
            sorted_chains = _sort_chains(group_chains, parent_bone)
            chain_verts = [_chain_verts(c) for c in sorted_chains]

            # Fill between each consecutive pair
            pairs = list(zip(chain_verts, chain_verts[1:]))
            if props.close_mesh_loop and len(chain_verts) >= 3:
                pairs.append((chain_verts[-1], chain_verts[0]))

            for verts_A, verts_B in pairs:
                _fill_between(verts_A, verts_B, all_verts, all_faces)

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
            f"ArmExt: Created '{obj.name}' with {face_count} face(s).",
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
