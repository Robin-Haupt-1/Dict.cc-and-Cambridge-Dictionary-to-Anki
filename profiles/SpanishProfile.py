from .Profile import *

class FrenchProfile(Profile):
    language = "Spanish"
    pollyLangCode = "es"
    anki_deck_names = ["All::1) Sprachen::Spanish f. dict.cc"]
    dict_cc_list_id = "1031152-FR-DE-59911"
    already_imported_words_folder: str = None
    new_crawled_words_folder: str = None
    