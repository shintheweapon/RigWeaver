"""
Armature Extractor
Extract a reduced armature containing only the bones that deform meshes.
"""

bl_info = {
    "name": "Armature Extractor",
    "author": "theweapon",
    "version": (0, 1, 0),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > ArmExt",
    "description": "Extract a reduced armature containing only deforming bones",
    "category": "Rigging",
}

if "bpy" in locals():
    import importlib
    from . import operators, ui
    importlib.reload(operators.extract_ops)
    importlib.reload(operators)
    importlib.reload(ui.panel)
    importlib.reload(ui)
else:
    from . import operators, ui

import bpy


def register():
    operators.register()
    ui.register()


def unregister():
    ui.unregister()
    operators.unregister()


if __name__ == "__main__":
    register()
