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
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import Operator, PropertyGroup
from mathutils import Vector


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

class BoneUtilProperties(PropertyGroup):
    retarget_meshes: BoolProperty(
        name="Retarget Meshes",
        description=(
            "Update Armature modifiers on connected meshes to point to "
            "the new reduced armature instead of the original"
        ),
        default=False,
    )
    auto_bone_orientation: BoolProperty(
        name="Auto Bone Orientation",
        description=(
            "Recalculate bone rolls on the reduced armature so the local Z axis "
            "aligns with global +Z (same as FBX import 'Automatic Bone Orientation')"
        ),
        default=False,
    )
    mesh_mode: EnumProperty(
        name="Mode",
        items=[
            ('INDIVIDUAL',    "Individual Strips",
             "One ribbon per chain (hair, fur, loose strands)"),
            ('SURFACE',       "Connected Surface",
             "Panels between sorted adjacent chains (flat panels, even chain spacing)"),
            ('SURFACE_LOOP',  "Connected Loop",
             "Closed surface, last chain connects back to first (skirts, rings, cylinders)"),
            ('SURFACE_SPLIT', "Auto-Split Surface",
             "Connected surface with automatic gap detection (inner/outer loop layouts, box pleats)"),
        ('TREE',          "Tree Surface",
             "Sample-point triangulation for branching or irregular layouts (capes, fans)"),
        ],
        default='SURFACE',
    )
    mesh_split_objects: BoolProperty(
        name="Separate Objects",
        description=(
            "Create one mesh object per chain instead of merging all ribbons "
            "into a single object (only active when Individual Chains is on)"
        ),
        default=False,
    )
    mesh_triangulate: BoolProperty(
        name="Triangulate",
        description="Convert all quad faces to triangles in the generated mesh",
        default=False,
    )
    mesh_panel_resolution: IntProperty(
        name="Column Resolution",
        description=(
            "Quad columns per panel in the lateral direction (between adjacent chains). "
            "1 = single column."
        ),
        default=2,
        min=1,
        max=16,
    )
    mesh_bone_subdivisions: IntProperty(
        name="Row Resolution",
        description=(
            "Subdivisions per bone segment in the longitudinal direction (along the chain). "
            "1 = one row per bone, 2+ = interpolated rows within each segment."
        ),
        default=1,
        min=1,
        max=16,
    )
    mesh_ribbon_width: FloatProperty(
        name="Ribbon Width",
        description="Width of the ribbon mesh generated from a single bone chain",
        default=0.1,
        min=0.001,
        soft_max=1.0,
        unit='LENGTH',
    )
    mesh_strip_gap_factor: FloatProperty(
        name="Gap Factor",
        description=(
            "A gap larger than this multiple of the median inter-chain distance "
            "is treated as a strip boundary"
        ),
        default=2.0,
        min=1.1,
        soft_max=10.0,
    )
    mesh_tree_alpha_factor: FloatProperty(
        name="Bridge Filter",
        description=(
            "Circumradius threshold as a multiple of the median edge length. "
            "Higher values keep more triangles; lower values prune long bridging edges."
        ),
        default=2.0,
        min=0.1,
        soft_max=10.0,
    )
    mesh_envelope_factor: FloatProperty(
        name="Weight Radius",
        description=(
            "Radius of each bone's weight influence as a multiple of the bone's length. "
            "Vertices outside all influence zones fall back to the nearest bone."
        ),
        default=1.5,
        min=0.1,
        soft_max=5.0,
    )
    mesh_auto_rig: BoolProperty(
        name="Auto-Rig",
        description=(
            "Create one vertex group per bone (inverse-distance weights) and add "
            "an Armature modifier pointing to the source armature, making the "
            "generated mesh immediately deform-ready."
        ),
        default=False,
    )
    mesh_generate_uvs: BoolProperty(
        name="Generate UVs",
        description="Create a UVMap layer on the generated mesh (U=lateral, V=longitudinal)",
        default=False,
    )
    # JSON-serialised list of weighted bone names, cached between runs
    last_weighted_bones: StringProperty(default="[]")

    # UI state — collapsed/expanded section headers
    ui_expand_extract: BoolProperty(name="Extract Used Armature", default=True)
    ui_expand_generate: BoolProperty(name="Generate Mesh", default=True)

    # UI state — envelope preview overlay active
    ui_envelope_preview_active: BoolProperty(
        name="Envelope Preview Active",
        description="Whether the viewport envelope radius overlay is currently displayed",
        default=False,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_weighted_names(armature_obj: bpy.types.Object) -> set[str]:
    """
    Scan all mesh objects whose Armature modifier targets armature_obj.
    Return the set of bone names that have at least one vertex weight > 0.
    """
    bone_names: set[str] = {b.name for b in armature_obj.data.bones}
    weighted: set[str] = set()

    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object == armature_obj:
                weighted_indices = {
                    g.group
                    for v in obj.data.vertices
                    for g in v.groups
                    if g.weight > 0.0
                }
                for vg in obj.vertex_groups:
                    if vg.index in weighted_indices and vg.name in bone_names:
                        weighted.add(vg.name)
                break  # only one Armature modifier needed per mesh

    return weighted

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
        # Walk up past any non-weighted intermediates to the nearest used ancestor
        current = parent_name_map.get(name)
        while current is not None:
            if current in used_names:
                visit(current)  # ensure ancestor is ordered before this bone
                break
            current = parent_name_map.get(current)
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
            self.report({'ERROR'}, "RigProxy: No bones with vertex weights found.")
            return {'CANCELLED'}

        # Filter to bones that actually exist in the armature
        existing = {b.name for b in source_obj.data.bones}
        used_names = used_names & existing

        if not used_names:
            self.report({'ERROR'}, "RigProxy: No matching bones found in armature.")
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
        if 'FINISHED' not in bpy.ops.object.mode_set(mode='EDIT'):
            self.report({'ERROR'}, "RigProxy: Could not enter Edit Mode on source armature.")
            return {'CANCELLED'}

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

        if 'FINISHED' not in bpy.ops.object.mode_set(mode='OBJECT'):
            self.report({'ERROR'}, "RigProxy: Could not return to Object Mode after reading source armature.")
            return {'CANCELLED'}

        # --- Create new armature object ---
        new_arm_data = bpy.data.armatures.new(f"{source_obj.data.name}_Reduced")
        new_obj = bpy.data.objects.new(f"{source_obj.name}_Reduced", new_arm_data)

        for coll in source_obj.users_collection:
            coll.objects.link(new_obj)

        new_obj.location = source_obj.location.copy()
        new_obj.rotation_euler = source_obj.rotation_euler.copy()
        new_obj.rotation_quaternion = source_obj.rotation_quaternion.copy()
        new_obj.scale = source_obj.scale.copy()
        new_obj.show_in_front = True

        # --- Populate bones in Edit Mode on the new armature ---
        bpy.ops.object.select_all(action='DESELECT')
        new_obj.select_set(True)
        context.view_layer.objects.active = new_obj
        if 'FINISHED' not in bpy.ops.object.mode_set(mode='EDIT'):
            self.report({'ERROR'}, "RigProxy: Could not enter Edit Mode on new armature.")
            return {'CANCELLED'}

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
        # Matches Blender FBX import "Automatic Bone Orientation".
        # Step 1: non-end bones → tail toward average child head.
        # Step 2: end bones with a parent → inherit parent's corrected direction.
        # Step 3: recalculate roll so local Z aligns with global +Z.
        if props.auto_bone_orientation:
            # Step 1: non-end bones
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

            # Step 2: end bones — inherit parent's already-corrected direction
            for name, new_eb in new_bone_map.items():
                children = [c for c in new_arm_data.edit_bones if c.parent == new_eb]
                if children or not new_eb.parent:
                    continue  # not an end bone, or no parent to inherit from
                parent_dir = new_eb.parent.tail - new_eb.parent.head
                if parent_dir.length > 1e-6:
                    bone_len = (new_eb.tail - new_eb.head).length
                    new_eb.tail = new_eb.head + parent_dir.normalized() * bone_len

            # Step 3: recalculate rolls
            for eb in new_arm_data.edit_bones:
                eb.select = True
            with context.temp_override(active_object=new_obj):
                bpy.ops.armature.calculate_roll(type='GLOBAL_POS_Z')

        # --- Return to Object Mode ---
        if 'FINISHED' not in bpy.ops.object.mode_set(mode='OBJECT'):
            self.report({'ERROR'}, "RigProxy: Could not return to Object Mode after building new armature.")
            return {'CANCELLED'}

        bpy.ops.object.select_all(action='DESELECT')
        new_obj.select_set(True)
        context.view_layer.objects.active = new_obj

        bone_count = len(new_bone_map)
        self.report({'INFO'}, f"RigProxy: Created '{new_obj.name}' with {bone_count} bone(s).")

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
                    f"RigProxy: Retargeted {retarget_count} mesh(es) to '{new_obj.name}'.",
                )

        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (BoneUtilProperties, BONE_OT_extract_used_armature)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bone_util_props = bpy.props.PointerProperty(
        type=BoneUtilProperties
    )


def unregister():
    if hasattr(bpy.types.Scene, "bone_util_props"):
        del bpy.types.Scene.bone_util_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
