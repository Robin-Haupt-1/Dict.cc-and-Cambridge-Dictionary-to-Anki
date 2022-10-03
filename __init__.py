from aqt.qt import QAction
from aqt import gui_hooks

from .utils import *
from .main import ImportEwFromCambridge
from .constants import EnglishProfile, FrenchProfile, Profile

import_task = None


def start_import(profile: Profile):
    global import_task
    import_task = ImportEwFromCambridge(profile)


def init():
    profiles: [Profile] = [EnglishProfile, FrenchProfile]
    for profile in profiles:
        # add menu option to import new cards
        options_action = QAction(f"Import from Cambridge ({profile.language})...", mw)
        options_action.triggered.connect(lambda _, o=mw: start_import(profile))
        mw.form.menuTools.addAction(options_action)
        # add menu option to import new cards
        options_action = QAction(f"Update Tampermonkey list ({profile.language})", mw)
        options_action.triggered.connect(lambda _, o=mw: profile.update_tampermonkey_list())
        mw.form.menuTools.addAction(options_action)


gui_hooks.profile_did_open.append(lambda *args: init())
