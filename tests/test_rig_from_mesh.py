# Tests for Generate Rig and Update Rig: vertex groups on the source mesh

import unittest

import bpy


def new_scene():
    """Empty the current file."""
    bpy.ops.wm.read_factory_settings(use_empty=True)


def skirt_with_pin():
    """
    Add a cylinder mesh with a ``pin`` vertex group weighted 0.7 on vertex 0.

    Returns
    -------
    bpy.types.Object
        The cylinder, active and selected, in Object Mode.
    """
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, depth=2)
    mesh_obj = bpy.context.object
    mesh_obj.name = "Skirt"
    mesh_obj.vertex_groups.new(name="pin").add([0], 0.7, 'REPLACE')
    return mesh_obj


def group_weight(mesh_obj, vertex_index, group_name):
    """
    Return the weight of one vertex in one group.

    Returns
    -------
    float or None
        The weight, or None when the vertex is not in the group.
    """
    group_index = mesh_obj.vertex_groups[group_name].index
    for g in mesh_obj.data.vertices[vertex_index].groups:
        if g.group == group_index:
            return g.weight
    return None


class UpdateRigVertexGroupsTest(unittest.TestCase):
    """Update Rig replaces the bone groups and keeps every other group."""

    def setUp(self):
        new_scene()
        self.props = bpy.context.scene.rig_weaver_props
        self.props.rig_chains = 8
        self.props.rig_auto_weights = True
        self.mesh_obj = skirt_with_pin()
        self.assertEqual(bpy.ops.rig_weaver.generate_rig_from_mesh(), {'FINISHED'})
        self.arm_obj = next(o for o in bpy.data.objects
                            if o.get("rig_weaver_source_mesh") == "Skirt")
        self.old_bones = {b.name for b in self.arm_obj.data.bones}
        # Fewer chains, so some old bone names do not come back
        self.props.rig_chains = 4
        bpy.context.view_layer.objects.active = self.mesh_obj
        self.assertEqual(bpy.ops.rig_weaver.update_rig_from_mesh(), {'FINISHED'})
        self.new_bones = {b.name for b in self.arm_obj.data.bones}

    def test_other_group_keeps_its_weight(self):
        self.assertIn("pin", self.mesh_obj.vertex_groups)
        self.assertAlmostEqual(group_weight(self.mesh_obj, 0, "pin"), 0.7, places=5)

    def test_old_bone_groups_are_gone(self):
        groups = {g.name for g in self.mesh_obj.vertex_groups}
        self.assertTrue(self.old_bones - self.new_bones)
        self.assertFalse((self.old_bones - self.new_bones) & groups)
        self.assertEqual(groups - self.new_bones, {"pin"})

    def test_bone_weights_add_up_to_one(self):
        bone_indices = {self.mesh_obj.vertex_groups[n].index for n in self.new_bones}
        for v in self.mesh_obj.data.vertices:
            total = sum(g.weight for g in v.groups if g.group in bone_indices)
            self.assertAlmostEqual(total, 1.0, places=4)


if __name__ == '__main__':
    unittest.main()
