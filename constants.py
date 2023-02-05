import os
import urllib.parse
from os.path import join
from dataclasses import dataclass
from aqt.qt import QAction
from aqt.utils import showInfo, tooltip
from aqt import mw
from aqt import gui_hooks
import datetime
from .utils import *
from anki.consts import *
from functools import lru_cache
import math

print("import constants")

MEDIA_FOLDER = r"/home/robin/.local/share/Anki2/Benutzer 1/collection.media"
BASE_FOLDER = r"/hdd/Software Engineering/.files/2021-09-23 Dict.cc und Cambridge Importer"


@dataclass
class DownloadedAudio:
    filename: str


@dataclass
class WordBeingImported:
    unprocessed_string: str = None
    learning: str = None
    familiar: [str] = None
    learning_scrubbed: str = None
    both_front: str = ""


@dataclass
class NewCrawledWordFileToDelete:
    filename: str


from .edit_words_dialog import EditNewWordsDialog

