"""
Blender Bone Utility
Detect unused bones in an armature (categorised + colour-coded) and extract
a reduced armature containing only the bones that deform meshes.
"""

bl_info = {
    "name": "Blender Bone Utility",
    "author": "theweapon",
    "version": (0, 1, 0),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > Bone Util",
    "description": "Detect unused bones and extract a reduced armature",
    "category": "Rigging",
}

if "bpy" in locals():
    import importlib
    from . import core, operators, ui
    importlib.reload(core.bone_analysis)
    importlib.reload(core)
    importlib.reload(operators.analyze_ops)
    importlib.reload(operators.extract_ops)
    importlib.reload(operators)
    importlib.reload(ui.panel)
    importlib.reload(ui)
else:
    from . import core, operators, ui

import bpy


def register():
    operators.register()
    ui.register()


def unregister():
    ui.unregister()
    operators.unregister()


if __name__ == "__main__":
    register()
