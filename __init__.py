from aqt.qt import QAction
from aqt import gui_hooks
import importlib
import os
import sys
from aqt import mw

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
print(sys.path)
import import_dict_cc

# add menu option to import new cards
options_action = QAction(f"Reload 1", mw)
options_action.triggered.connect(lambda _, o=mw: reload_addon())
mw.form.menuTools.addAction(options_action)


def reload_addon():
    import_dict_cc.remove_menu_items()
    importlib.reload(import_dict_cc)
    # import import_dict_cc
    import_dict_cc.add_menu_items()
