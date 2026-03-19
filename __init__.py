"""
RigWeaver
Bone extraction and simulation proxy mesh tools.
"""

bl_info = {
    "name": "RigWeaver",
    "author": "theweapon",
    "version": (0, 1, 0),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > RigWeaver",
    "description": "Bone extraction and simulation proxy mesh tools",
    "category": "Rigging",
}

if "bpy" in locals():
    import importlib
    from . import operators, ui, translations
    importlib.reload(operators.extract_ops)
    importlib.reload(operators.mesh_gen_ops)
    importlib.reload(operators.rig_from_mesh_ops)
    importlib.reload(operators.vg_select_ops)
    importlib.reload(operators)
    importlib.reload(ui.panel)
    importlib.reload(ui)
    importlib.reload(translations)
else:
    from . import operators, ui, translations

import bpy


def register():
    bpy.app.translations.register(__name__, translations.translations_dict)
    operators.register()
    ui.register()


def unregister():
    ui.unregister()
    operators.unregister()
    bpy.app.translations.unregister(__name__)


if __name__ == "__main__":
    register()
