# Tests for the Simplified Chinese interface of Transfer Weights: every text it
# shows has a translation in the context Blender looks it up in

import unittest

import bpy

# Texts the panel passes through iface_ (default context)
PANEL_LABELS = ("Transfer Weights", "Requires Object Mode", "Enter Object Mode")


def missing_translations():
    """
    List the Transfer Weights texts that stay English in Chinese.

    Option names and tooltips and their choices are looked up in the option's
    own context, the command label under 'Operator', the command tooltip and
    panel labels with no context.

    Returns
    -------
    list of str
        "kind: text" for each text without a translation.
    """
    tr = bpy.app.translations
    missing = []

    def check(kind, text, translate):
        if text and translate(text) == text:
            missing.append(f"{kind}: {text}")

    for prop in bpy.context.scene.rig_weaver_props.bl_rna.properties:
        if not prop.identifier.startswith('transfer_'):
            continue
        ctx = prop.translation_context
        check('option', prop.name, lambda t: tr.pgettext_iface(t, ctx))
        check('option tooltip', prop.description, lambda t: tr.pgettext_tip(t, ctx))
        if prop.type == 'ENUM':
            for item in prop.enum_items:
                check('choice', item.name, lambda t: tr.pgettext_iface(t, ctx))
                check('choice tooltip', item.description, lambda t: tr.pgettext_tip(t, ctx))
    rna = bpy.ops.rig_weaver.transfer_weights.get_rna_type()
    check('command', rna.name, lambda t: tr.pgettext_iface(t, 'Operator'))
    check('command tooltip', rna.description, tr.pgettext_tip)
    for label in PANEL_LABELS:
        check('panel', label, tr.pgettext_iface)
    return sorted(set(missing))


class ChineseTests(unittest.TestCase):

    def setUp(self):
        view = bpy.context.preferences.view
        self.saved = (view.language, view.use_translate_interface, view.use_translate_tooltips)
        view.language = 'zh_HANS'
        view.use_translate_interface = True
        view.use_translate_tooltips = True

    def tearDown(self):
        view = bpy.context.preferences.view
        view.language, view.use_translate_interface, view.use_translate_tooltips = self.saved

    def test_transfer_weights_texts_have_chinese(self):
        self.assertEqual(missing_translations(), [])


if __name__ == '__main__':
    unittest.main()
