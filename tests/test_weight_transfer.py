# Tests for Transfer Weights: deform bone weights from a source mesh to the active mesh

import math
import unittest

import bpy


def new_scene():
    """Empty the current file."""
    bpy.ops.wm.read_factory_settings(use_empty=True)


def posed_armature(location=(0.0, 0.0, 0.0)):
    """
    Create an armature with deform bones ``up`` and ``low`` and a non-deform
    bone ``ctrl``, with ``up`` rotated 50 degrees in Pose Mode.

    Returns
    -------
    bpy.types.Object
        The armature, in Object Mode.
    """
    arm_data = bpy.data.armatures.new("Arm")
    arm_obj = bpy.data.objects.new("Arm", arm_data)
    bpy.context.scene.collection.objects.link(arm_obj)
    arm_obj.location = location
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    up = arm_data.edit_bones.new("up")
    up.head, up.tail = (0, 0, 2), (0, 0, 1)
    low = arm_data.edit_bones.new("low")
    low.head, low.tail = (0, 0, 1), (0, 0, 0)
    low.parent = up
    ctrl = arm_data.edit_bones.new("ctrl")
    ctrl.head, ctrl.tail = (1, 0, 0), (1, 0, 1)
    ctrl.use_deform = False
    bpy.ops.object.mode_set(mode='POSE')
    arm_obj.pose.bones["up"].rotation_mode = 'XYZ'
    arm_obj.pose.bones["up"].rotation_euler = (math.radians(50), 0.0, 0.0)
    bpy.ops.object.mode_set(mode='OBJECT')
    return arm_obj


def source_mesh(arm_obj, total=1.0, via_parent=False):
    """
    Add an 8-sided cylinder from z = 0 to 2 under the armature.

    ``up`` runs from 0 at the bottom to ``total`` at the top and ``low`` the
    other way, so each vertex's bone weights add up to ``total``. The groups
    ``ctrl`` (a non-deform bone), ``helper`` and ``pin`` hold 0.3, 0.5 and 0.2.

    Returns
    -------
    bpy.types.Object
        The source, deformed by the armature through an Armature modifier, or
        through an armature parent when ``via_parent`` is set.
    """
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=8, depth=2, location=(arm_obj.location.x, 0.0, 1.0))
    src = bpy.context.object
    src.name = "Body"
    for name in ("up", "low", "ctrl", "helper", "pin"):
        src.vertex_groups.new(name=name)
    for v in src.data.vertices:
        z = v.co.z / 2 + 0.5
        src.vertex_groups["up"].add([v.index], total * z, 'REPLACE')
        src.vertex_groups["low"].add([v.index], total * (1 - z), 'REPLACE')
        for name, weight in (("ctrl", 0.3), ("helper", 0.5), ("pin", 0.2)):
            src.vertex_groups[name].add([v.index], weight, 'REPLACE')
    if via_parent:
        matrix = src.matrix_world.copy()
        src.parent = arm_obj
        src.parent_type = 'ARMATURE'
        src.matrix_world = matrix
    else:
        src.modifiers.new("Armature", 'ARMATURE').object = arm_obj
    return src


def target_mesh(location=(0.0, 0.0, 1.0), scale=1.0):
    """
    Add a denser cylinder around the source, with ``pin`` 0.7 on vertex 0 and a
    stale ``up`` of 0.9 on every vertex.

    Returns
    -------
    bpy.types.Object
        The target, active and selected; scaled by ``scale`` with the same
        world shape.
    """
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=32, depth=2 / scale, radius=1.05 / scale, location=location)
    tgt = bpy.context.object
    tgt.name = "Shirt"
    tgt.scale = (scale, scale, scale)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=6)
    bpy.ops.object.mode_set(mode='OBJECT')
    tgt.vertex_groups.new(name="pin").add([0], 0.7, 'REPLACE')
    tgt.vertex_groups.new(name="up").add(list(range(len(tgt.data.vertices))), 0.9, 'REPLACE')
    return tgt


def weight(obj, vertex, name):
    """Return a vertex's weight in a group, or 0.0 when it is not in the group."""
    group = obj.vertex_groups.get(name)
    if group is None:
        return 0.0
    return next((g.weight for g in vertex.groups if g.group == group.index), 0.0)


def top_and_bottom(obj):
    """Return the highest and lowest vertex in world space."""
    matrix = obj.matrix_world
    verts = obj.data.vertices
    return (max(verts, key=lambda v: (matrix @ v.co).z),
            min(verts, key=lambda v: (matrix @ v.co).z))


def transfer(tgt, src, **settings):
    """
    Run Transfer Weights on ``tgt`` with ``src`` as the source.

    Returns
    -------
    set of str
        The operator's result.
    """
    props = bpy.context.scene.rig_weaver_props
    props.transfer_source = src
    for name, value in settings.items():
        setattr(props, name, value)
    bpy.context.view_layer.objects.active = tgt
    return bpy.ops.rig_weaver.transfer_weights()


class TransferWeightsTest(unittest.TestCase):
    """The target receives the source's deform bone groups by name."""

    def setUp(self):
        new_scene()
        self.arm_obj = posed_armature()
        self.src = source_mesh(self.arm_obj)
        self.tgt = target_mesh()

    def assert_rest_shape_weights(self, tgt):
        top, bottom = top_and_bottom(tgt)
        self.assertAlmostEqual(weight(tgt, top, "up"), 1.0, places=4)
        self.assertAlmostEqual(weight(tgt, top, "low"), 0.0, places=4)
        self.assertAlmostEqual(weight(tgt, bottom, "up"), 0.0, places=4)
        self.assertAlmostEqual(weight(tgt, bottom, "low"), 1.0, places=4)

    def test_only_deform_groups_arrive(self):
        self.assertEqual(transfer(self.tgt, self.src), {'FINISHED'})
        self.assertEqual({g.name for g in self.tgt.vertex_groups}, {"up", "low", "pin"})
        self.assertAlmostEqual(weight(self.tgt, self.tgt.data.vertices[0], "pin"), 0.7, places=5)

    def test_stale_group_is_replaced_from_the_rest_shape(self):
        # The armature is posed; the weights still follow the rest shape
        transfer(self.tgt, self.src)
        self.assert_rest_shape_weights(self.tgt)

    def test_scaled_target(self):
        tgt = target_mesh(scale=2.0)
        transfer(tgt, self.src)
        self.assert_rest_shape_weights(tgt)

    def test_selection_and_scene_unchanged(self):
        for obj in bpy.context.scene.objects:
            obj.select_set(obj == self.tgt)
        names = {o.name for o in bpy.data.objects}
        meshes = len(bpy.data.meshes)
        transfer(self.tgt, self.src)
        self.assertEqual({o.name for o in bpy.data.objects}, names)
        self.assertEqual(len(bpy.data.meshes), meshes)
        self.assertEqual([o.name for o in bpy.context.selected_objects], ["Shirt"])
        self.assertEqual(bpy.context.view_layer.objects.active, self.tgt)

    def test_armature_modifier_added_once(self):
        transfer(self.tgt, self.src, transfer_add_armature=True)
        transfer(self.tgt, self.src, transfer_add_armature=True)
        mods = [m for m in self.tgt.modifiers if m.type == 'ARMATURE']
        self.assertEqual([(m.name, m.object) for m in mods], [("Armature", self.arm_obj)])

    def test_no_armature_modifier_when_off(self):
        transfer(self.tgt, self.src, transfer_add_armature=False)
        self.assertFalse([m for m in self.tgt.modifiers if m.type == 'ARMATURE'])


class NormalizeTest(unittest.TestCase):
    """Normalize Weights makes the copied bone weights add up to 1."""

    def setUp(self):
        new_scene()
        arm_obj = posed_armature()
        self.src = source_mesh(arm_obj, total=0.8)
        self.tgt = target_mesh()

    def totals(self):
        return [weight(self.tgt, v, "up") + weight(self.tgt, v, "low")
                for v in self.tgt.data.vertices]

    def test_normalize_on(self):
        transfer(self.tgt, self.src, transfer_normalize=True)
        for total in self.totals():
            self.assertAlmostEqual(total, 1.0, places=4)

    def test_normalize_off(self):
        transfer(self.tgt, self.src, transfer_normalize=False)
        for total in self.totals():
            self.assertAlmostEqual(total, 0.8, places=4)


class ParentDeformedSourceTest(unittest.TestCase):
    """A source deformed through an armature parent is handled too."""

    def test_parent_deformed_source(self):
        new_scene()
        arm_obj = posed_armature(location=(0.5, 0.0, 0.0))
        src = source_mesh(arm_obj, via_parent=True)
        tgt = target_mesh(location=(0.5, 0.0, 1.0))
        self.assertEqual(transfer(tgt, src), {'FINISHED'})
        top, bottom = top_and_bottom(tgt)
        self.assertAlmostEqual(weight(tgt, top, "up"), 1.0, places=4)
        self.assertAlmostEqual(weight(tgt, bottom, "low"), 1.0, places=4)
        self.assertEqual(src.parent, arm_obj)


class TransferErrorsTest(unittest.TestCase):
    """Missing or unusable sources are reported and nothing changes."""

    def setUp(self):
        new_scene()
        self.arm_obj = posed_armature()
        self.src = source_mesh(self.arm_obj)
        self.tgt = target_mesh()

    def assert_cancelled(self, src):
        with self.assertRaises(RuntimeError):
            transfer(self.tgt, src)
        self.assertEqual({g.name for g in self.tgt.vertex_groups}, {"pin", "up"})

    def test_no_source(self):
        self.assert_cancelled(None)

    def test_source_is_target(self):
        self.assert_cancelled(self.tgt)

    def test_source_without_armature(self):
        self.src.modifiers.clear()
        self.assert_cancelled(self.src)

    def test_source_without_deform_groups(self):
        for name in ("up", "low"):
            self.src.vertex_groups.remove(self.src.vertex_groups[name])
        self.assert_cancelled(self.src)


if __name__ == '__main__':
    unittest.main()
