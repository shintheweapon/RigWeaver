"""
Operator: Analyze unused bones + apply bone collections / colours.
Also hosts BoneUtilProperties (shared property group for the whole addon).
"""
from __future__ import annotations
import json

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator, PropertyGroup

from ..core.bone_analysis import (
    BoneCategory,
    CATEGORY_META,
    AnalysisResult,
    analyze_bones,
    build_weighted_set,
)

# Collection prefix — used when clearing previous runs
_COLL_PREFIX = "BoneUtil_"


class BoneUtilProperties(PropertyGroup):
    color_code_bones: BoolProperty(
        name="Color-Code Bones",
        description="Create bone collections and apply custom colours per category",
        default=True,
    )
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
    # JSON-serialised list of weighted bone names, cached for Extract operator
    last_weighted_bones: StringProperty(default="[]")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_weighted_names(armature_obj: bpy.types.Object) -> set[str]:
    """
    Scan all mesh objects whose Armature modifier targets armature_obj.
    Return the set of bone names that have at least one vertex weight > 0.
    """
    bone_names: set[str] = {b.name for b in armature_obj.data.bones}
    mesh_data: list[tuple[str, list[str]]] = []

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
                vg_names = [
                    vg.name
                    for vg in obj.vertex_groups
                    if vg.index in weighted_indices and vg.name in bone_names
                ]
                mesh_data.append((obj.name, vg_names))
                break  # only one Armature modifier needed per mesh

    return build_weighted_set(mesh_data)


def _clear_boneutil_state(armature_obj: bpy.types.Object) -> None:
    """
    Remove all BoneUtil_* collections and reset custom colours on bones
    that were previously tagged by this addon.
    Must be called in Pose Mode (for pose_bone.color access).
    """
    arm_data = armature_obj.data

    # Identify collections to remove
    to_remove = [
        c for c in list(arm_data.collections)
        if c.name.startswith(_COLL_PREFIX)
    ]

    # Reset colours on bones that belong to any BoneUtil collection
    for coll in to_remove:
        try:
            for bone in list(coll.bones):
                pb = armature_obj.pose.bones.get(bone.name)
                if pb and pb.color.palette == 'CUSTOM':
                    pb.color.palette = 'DEFAULT'
        except (RuntimeError, AttributeError):
            pass

    # Remove the collections (does not delete bones)
    for coll in to_remove:
        try:
            arm_data.collections.remove(coll)
        except (RuntimeError, AttributeError):
            pass


def _apply_colors(
    armature_obj: bpy.types.Object,
    result: AnalysisResult,
) -> None:
    """
    Create BoneUtil_* bone collections and apply custom pose-bone colours.
    Must be called in Pose Mode.
    """
    arm_data = armature_obj.data

    # Pre-create all needed collections keyed by category
    cat_to_coll: dict[BoneCategory, bpy.types.BoneCollection] = {}
    for cat, (coll_name, _colour, _prob) in CATEGORY_META.items():
        coll = arm_data.collections.get(coll_name)
        if coll is None:
            coll = arm_data.collections.new(coll_name)
        cat_to_coll[cat] = coll

    # Assign each bone to its collection and set colour
    for cb in result.bones:
        coll_name, colour, _prob = CATEGORY_META[cb.category]
        coll = cat_to_coll[cb.category]

        # Link bone to collection (Object/Pose mode — safe)
        try:
            arm_data.bones[cb.name].collections.link(coll)
        except (KeyError, RuntimeError, AttributeError):
            pass

        # Apply pose-bone custom colour
        pb = armature_obj.pose.bones.get(cb.name)
        if pb:
            try:
                pb.color.palette = 'CUSTOM'
                pb.color.custom.normal = colour
                # Lighter tints for select / active states
                pb.color.custom.select = tuple(min(c + 0.3, 1.0) for c in colour)
                pb.color.custom.active = tuple(min(c + 0.5, 1.0) for c in colour)
            except (AttributeError, TypeError):
                pass


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------

class BONE_OT_analyze_unused(Operator):
    """Scan connected meshes and categorise bones by vertex weight usage"""
    bl_idname = "bone_util.analyze_unused"
    bl_label = "Analyze Unused Bones"
    bl_description = (
        "Categorise every bone by vertex-weight usage and optionally "
        "colour-code them with bone collections"
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
        armature_obj = context.object
        props: BoneUtilProperties = context.scene.bone_util_props

        # --- Analyse ---
        weighted_names = _collect_weighted_names(armature_obj)
        all_names = [b.name for b in armature_obj.data.bones]
        result = analyze_bones(all_names, weighted_names)

        # Cache weighted names for Extract operator
        props.last_weighted_bones = json.dumps(list(weighted_names))

        # --- Colour-code ---
        if props.color_code_bones:
            original_mode = context.object.mode
            bpy.ops.object.mode_set(mode='POSE')
            _clear_boneutil_state(armature_obj)
            _apply_colors(armature_obj, result)
            bpy.ops.object.mode_set(mode=original_mode)

        # --- Report ---
        self._report(result)
        return {'FINISHED'}

    def _report(self, result: AnalysisResult) -> None:
        cat_labels = {
            BoneCategory.USED:         "Used (weighted)",
            BoneCategory.DEFORM:       "DEF- (no weights — check!)",
            BoneCategory.MECHANISM:    "MCH- (weightless — OK)",
            BoneCategory.ORGANIZATION: "ORG- (weightless — OK)",
            BoneCategory.CONTROL:      "Control/IK (weightless — OK)",
            BoneCategory.OTHER:        "Other (weightless — review)",
        }
        for cat, label in cat_labels.items():
            count = result.counts.get(cat, 0)
            if count:
                self.report({'INFO'}, f"Bone Util: {count}x {label}")

        for cb in result.problematic:
            self.report({'WARNING'}, f"Bone Util: '{cb.name}' has no vertex weights")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (BoneUtilProperties, BONE_OT_analyze_unused)


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
