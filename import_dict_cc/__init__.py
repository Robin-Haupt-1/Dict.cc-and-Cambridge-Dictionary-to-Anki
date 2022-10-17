import importlib
import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
print(sys.path)

import constants
import edit_words_dialog
import utils

importlib.reload(constants)
importlib.reload(edit_words_dialog)
importlib.reload(utils)


import constants
import edit_words_dialog
import utils

from aqt.qt import QAction
from aqt import gui_hooks
import importlib
import os
import sys
from aqt import mw

import_task = None
print("loaded module")


def start_import(profile: constants.Profile):
    global import_task
    import_task = profile.start_import()


currently_added_actions: [QAction] = []


def add_action_items(profile: constants.Profile):
    # add menu option to import new cards
    options_action = QAction(f"Import from Cambridge ({profile.language})...", mw)
    options_action.triggered.connect(lambda _, o=mw: start_import(profile))
    mw.form.menuTools.addAction(options_action)
    currently_added_actions.append(options_action)

    # add menu option to import new cards
    options_action = QAction(f"Update Tampermonkey list ({profile.language})", mw)
    options_action.triggered.connect(lambda _, o=mw: profile.update_tampermonkey_list())
    mw.form.menuTools.addAction(options_action)
    currently_added_actions.append(options_action)


def remove_menu_items ():
    global currently_added_actions
    for action in currently_added_actions:
        print("unloading")
        mw.form.menuTools.removeAction(action)
    currently_added_actions = []


def add_menu_items():
    # reload()
    profiles: [constants.Profile] = [constants.EnglishProfile(), constants.FrenchProfile()]
    for profile in profiles:
        add_action_items(profile)
