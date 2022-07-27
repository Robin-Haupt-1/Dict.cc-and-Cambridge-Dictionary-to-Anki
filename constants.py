import sys
from os.path import join


def get_os_name():
    """Get the name of the running OS. Returns 'Linux', 'Windows' or 'Mac'"""
    if sys.platform in ['linux', 'linux2']:
        return "Linux"
    if sys.platform in ['Windows', 'win32', 'cygwin']:
        return "Windows"
    if sys.platform in ['Mac', 'darwin', 'os2', 'os2emx']:
        return "Mac"

    raise Exception(f"Unknown OS {sys.platform}")


# save OS name to variable. It doesn't change
os_name = get_os_name()

NOTE_TYPE_NAME = "__English (from Dict.cc) (new)"
NOTE_TYPE_FIELDS = {"Englisch", "Deutsch 1", "Bild", "Audio", "IPA", "Häufigkeit"}

# Folders and paths
LIST_IDENTIFIER = "978781-EN-DE-09926"
BASE_FOLDER = r"/hdd/Software Engineering/.files/2021-09-23 Dict.cc und Cambridge Importer"
DONE_FOLDER = join(BASE_FOLDER, "imported_done", LIST_IDENTIFIER)
EW_FOLDER = join(BASE_FOLDER, "dict cc crawled vocabulary", LIST_IDENTIFIER)
MEDIA_FOLDER = r"/home/robin/.local/share/Anki2/Benutzer 1/collection.media"

EDIT_WORDS_SEPERATOR = "    ~    "
EDIT_WORDS_SEPERATOR_BASIC = "~"
