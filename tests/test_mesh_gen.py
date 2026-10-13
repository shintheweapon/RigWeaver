# Tests for Generate Proxy Mesh: placement in world space

import math
import unittest

import bpy
from mathutils import Vector

from blender_bone_util.operators import mesh_gen_ops


def new_scene():
    """Empty the current file."""
    bpy.ops.wm.read_factory_settings(use_empty=True)


def armature_with_chains(chains, location=(0, 0, 0), rotation_z=0.0, scale=1.0):
    """
    Create an armature whose chains hang down from a shared root bone.

    Parameters
    ----------
    chains : list of tuple
        One ``(x, y, bone_count)`` per chain; each bone is 0.5 long and points
        down -Z from z = 2.
    location, rotation_z, scale
        The armature object's transform (rotation about Z, in radians).

    Returns
    -------
    bpy.types.Object
        The armature, active, in Pose Mode, with every chain bone selected and
        the root bone not selected.
    """
    arm_data = bpy.data.armatures.new("Arm")
    arm_obj = bpy.data.objects.new("Arm", arm_data)
    bpy.context.scene.collection.objects.link(arm_obj)
    arm_obj.location = location
    arm_obj.rotation_euler = (0.0, 0.0, rotation_z)
    arm_obj.scale = (scale, scale, scale)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    root = arm_data.edit_bones.new("root")
    root.head = (0, 0, 2.2)
    root.tail = (0, 0, 2.4)
    for ci, (x, y, count) in enumerate(chains):
        parent = root
        for li in range(count):
            eb = arm_data.edit_bones.new(f"c{ci}_{li}")
            eb.head = (x, y, 2.0 - 0.5 * li)
            eb.tail = (x, y, 1.5 - 0.5 * li)
            eb.parent = parent
            parent = eb
    bpy.ops.object.mode_set(mode='POSE')
    for bone in arm_data.bones:
        bone.select = bone.name != "root"
    return arm_obj


def generate(**settings):
    """
    Run Generate Proxy Mesh with the given RigWeaver properties.

    Returns
    -------
    bpy.types.Object
        The generated mesh object.
    """
    props = bpy.context.scene.rig_weaver_props
    for name, value in settings.items():
        setattr(props, name, value)
    assert bpy.ops.rig_weaver.generate_mesh() == {'FINISHED'}
    return bpy.context.view_layer.objects.active


class WorldSpaceTest(unittest.TestCase):
    """The proxy mesh follows the armature object's transform."""

    def setUp(self):
        new_scene()
        self.arm_obj = armature_with_chains(
            [(0.3, 0.0, 3)], location=(2, 0, 0), rotation_z=math.radians(90), scale=0.5)
        self.bones = [self.arm_obj.pose.bones[f"c0_{i}"] for i in range(3)]
        matrix = self.arm_obj.matrix_world
        self.segments = [(matrix @ pb.head, matrix @ pb.tail) for pb in self.bones]

    def test_ribbon_lies_on_bones_at_ribbon_width(self):
        obj = generate(mesh_mode='SURFACE', mesh_ribbon_width=0.1,
                       mesh_bone_subdivisions=2, mesh_auto_rig=False)
        verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
        # _ribbon_from_chain writes each cross section as a (right, left) pair
        for right, left in zip(verts[0::2], verts[1::2]):
            centre = (right + left) / 2
            distance = min(mesh_gen_ops._distance_to_segment(centre, head, tail)
                           for head, tail in self.segments)
            self.assertLess(distance, 1e-5)
            self.assertAlmostEqual((right - left).length, 0.1, places=5)

    def test_preview_lies_on_bones(self):
        bpy.context.scene.rig_weaver_props.mesh_ribbon_width = 0.1
        self.assertEqual(bpy.ops.rig_weaver.preview_proxy_mesh(), {'FINISHED'})
        obj = bpy.data.objects[mesh_gen_ops._PREVIEW_OBJ_NAME]
        for v in obj.data.vertices:
            distance = min(mesh_gen_ops._distance_to_segment(obj.matrix_world @ v.co, head, tail)
                           for head, tail in self.segments)
            self.assertLess(distance, 0.05 + 1e-5)

    def test_auto_rig_follows_posed_bone(self):
        obj = generate(mesh_mode='SURFACE', mesh_ribbon_width=0.1,
                       mesh_bone_subdivisions=2, mesh_auto_rig=True)
        posed = self.bones[1]
        posed.rotation_mode = 'XYZ'
        posed.rotation_euler = (math.radians(40), 0.0, 0.0)
        bpy.context.view_layer.update()
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
        arm_matrix = self.arm_obj.matrix_world
        moved = 0.0
        for v in obj.data.vertices:
            # Expected: the weighted sum of each bone's rest-to-pose transform
            expected = Vector()
            total = 0.0
            for g in v.groups:
                pb = self.arm_obj.pose.bones[obj.vertex_groups[g.group].name]
                skin = (arm_matrix @ pb.matrix @ pb.bone.matrix_local.inverted()
                        @ arm_matrix.inverted())
                expected += g.weight * (skin @ v.co)
                total += g.weight
            expected /= total
            actual = evaluated.vertices[v.index].co
            self.assertLess((actual - expected).length, 1e-4)
            moved = max(moved, (actual - v.co).length)
        self.assertGreater(moved, 0.05)


if __name__ == '__main__':
    unittest.main()
