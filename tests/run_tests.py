# Runs the test suite inside Blender, with factory settings so an installed
# copy of the add-on is not loaded:
#   blender.exe --factory-startup -b -P tests/run_tests.py

import os
import sys
import unittest

import bpy

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(TESTS_DIR)
# The repo folder is the add-on package, so its parent goes on the path
PARENT_DIR = os.path.dirname(REPO_DIR)


def main() -> int:
    """
    Register the add-on, then discover and run every ``test_*.py`` module.

    Returns
    -------
    int
        0 when every test passes, otherwise 1.
    """
    for path in (PARENT_DIR, TESTS_DIR):
        if path not in sys.path:
            sys.path.insert(0, path)
    # Tests check English names and messages
    bpy.context.preferences.view.language = 'en_US'
    package = __import__(os.path.basename(REPO_DIR))
    package.register()
    suite = unittest.defaultTestLoader.discover(TESTS_DIR, pattern='test_*.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
