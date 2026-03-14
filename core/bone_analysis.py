"""
Pure-Python bone analysis logic. No bpy dependency at module level.
Operators extract data from Blender and pass plain Python types here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING


class BoneCategory(Enum):
    USED = auto()         # has vertex weights — deforms a mesh
    DEFORM = auto()       # DEF- prefix but no weights — problematic
    MECHANISM = auto()    # MCH- prefix — intentionally weightless
    ORGANIZATION = auto() # ORG- prefix — intentionally weightless
    CONTROL = auto()      # CTR-/CTRL-/IK — intentionally weightless
    OTHER = auto()        # unknown — flag for review


# BoneCategory → (collection_name, colour_rgb, is_problematic)
CATEGORY_META: dict[BoneCategory, tuple[str, tuple[float, float, float], bool]] = {
    BoneCategory.USED:         ("BoneUtil_Used",         (0.2, 1.0, 0.2), False),
    BoneCategory.DEFORM:       ("BoneUtil_Deform",       (1.0, 0.2, 0.2), True),
    BoneCategory.MECHANISM:    ("BoneUtil_MCH",          (0.2, 0.8, 0.8), False),
    BoneCategory.ORGANIZATION: ("BoneUtil_ORG",          (0.3, 0.5, 1.0), False),
    BoneCategory.CONTROL:      ("BoneUtil_Control",      (1.0, 0.9, 0.2), False),
    BoneCategory.OTHER:        ("BoneUtil_Other",        (1.0, 0.5, 0.1), True),
}

# Regex to detect IK as a standalone word/suffix (not just a substring)
_IK_RE = re.compile(r'(^|[-_.])IK($|[-_.])', re.IGNORECASE)


def categorize_bone(name: str, is_weighted: bool) -> BoneCategory:
    """
    Classify a bone by whether it has weights and by its name prefix.

    Prefix checks are case-sensitive (Blender/Rigify convention).
    IK detection is case-insensitive and matches word-boundary patterns.
    """
    if is_weighted:
        return BoneCategory.USED

    if name.startswith("DEF-"):
        return BoneCategory.DEFORM
    if name.startswith("MCH-"):
        return BoneCategory.MECHANISM
    if name.startswith("ORG-"):
        return BoneCategory.ORGANIZATION
    if name.startswith(("CTR-", "CTRL-")) or _IK_RE.search(name):
        return BoneCategory.CONTROL

    return BoneCategory.OTHER


@dataclass
class CategorizedBone:
    name: str
    category: BoneCategory
    is_problematic: bool


@dataclass
class AnalysisResult:
    bones: list[CategorizedBone] = field(default_factory=list)
    # Count per category for quick reporting
    counts: dict[BoneCategory, int] = field(default_factory=dict)

    def __post_init__(self):
        if not self.counts and self.bones:
            self._recount()

    def _recount(self):
        self.counts = {}
        for cb in self.bones:
            self.counts[cb.category] = self.counts.get(cb.category, 0) + 1

    @property
    def problematic(self) -> list[CategorizedBone]:
        return [cb for cb in self.bones if cb.is_problematic]

    def by_category(self, cat: BoneCategory) -> list[CategorizedBone]:
        return [cb for cb in self.bones if cb.category == cat]


def analyze_bones(
    all_bone_names: list[str],
    weighted_names: set[str],
) -> AnalysisResult:
    """
    Categorise every bone in the armature.

    Args:
        all_bone_names: All bone names from armature.bones.
        weighted_names: Bone names that influence at least one vertex.

    Returns:
        AnalysisResult with every bone categorised.
    """
    bones: list[CategorizedBone] = []
    counts: dict[BoneCategory, int] = {}

    for name in all_bone_names:
        is_weighted = name in weighted_names
        cat = categorize_bone(name, is_weighted)
        meta = CATEGORY_META[cat]
        cb = CategorizedBone(name=name, category=cat, is_problematic=meta[2])
        bones.append(cb)
        counts[cat] = counts.get(cat, 0) + 1

    return AnalysisResult(bones=bones, counts=counts)


def build_weighted_set(
    mesh_vertex_data: list[tuple[str, list[str]]],
) -> set[str]:
    """
    Build the set of bone names that have at least one vertex weight > 0.

    Args:
        mesh_vertex_data: List of (mesh_name, [weighted_vg_names]).
            Each tuple represents one mesh object. The operator is responsible
            for filtering to only vertex groups with actual non-zero weights
            before passing data here.

    Returns:
        Set of bone/vertex-group names with actual weights.
    """
    result: set[str] = set()
    for _mesh_name, vg_names in mesh_vertex_data:
        result.update(vg_names)
    return result
