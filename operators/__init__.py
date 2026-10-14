from . import extract_ops, mesh_gen_ops, rig_from_mesh_ops, vg_select_ops, weight_transfer_ops


def register():
    extract_ops.register()
    mesh_gen_ops.register()
    rig_from_mesh_ops.register()
    vg_select_ops.register()
    weight_transfer_ops.register()


def unregister():
    weight_transfer_ops.unregister()
    vg_select_ops.unregister()
    rig_from_mesh_ops.unregister()
    mesh_gen_ops.unregister()
    extract_ops.unregister()
