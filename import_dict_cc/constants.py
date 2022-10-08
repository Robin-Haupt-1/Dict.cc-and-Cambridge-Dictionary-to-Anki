import os
import urllib.parse
from os.path import join
from dataclasses import dataclass
from aqt.qt import QAction
from aqt.utils import showInfo, tooltip
from edit_words_dialog import EditNewWordsDialog
from aqt import mw
from aqt import gui_hooks
import datetime
from utils import *
from anki.consts import *
from functools import lru_cache
import math

print("import constants")

BASE_FOLDER = r"/hdd/Software Engineering/.files/2021-09-23 Dict.cc und Cambridge Importer"
MEDIA_FOLDER = r"/home/robin/.local/share/Anki2/Benutzer 1/collection.media"


@dataclass
class DownloadedAudio:
    filename: str


@dataclass
class WordBeingImported:
    unprocessed_string: str = None
    learning: str = None
    familiar: [str] = None
    learning_scrubbed: str = None


@dataclass
class NewCrawledWordFileToDelete:
    filename: str


class Profile:
    language: str
    note_type_name: str = "Dict.cc imported"
    anki_deck_names: [str] = None
    dict_cc_list_id: str
    already_imported_words_folder: str
    new_crawled_words_folder: str
    new_crawled_words_to_delete: [NewCrawledWordFileToDelete]
    words_being_imported: [WordBeingImported] = []
    words_being_imported_raw: [WordBeingImported] = []

    def scrub_word(self, word: str) -> str:
        pass

    def __init__(self):
        self.already_imported_words_folder = join(BASE_FOLDER, "imported_done", self.dict_cc_list_id)
        self.new_crawled_words_folder = join(BASE_FOLDER, "dict cc crawled vocabulary", self.dict_cc_list_id)
        print("init on Profile")

    def start_import(self):
        self.new_crawled_words_to_delete = [NewCrawledWordFileToDelete(file.path) for file in os.scandir(self.new_crawled_words_folder)]

        already_imported_words = self._load_imported_words()
        log(f"Scanning folder {self.new_crawled_words_folder}")
        with os.scandir(self.new_crawled_words_folder) as files:
            files = sorted(files, key=lambda x: x.name)  # why?

            for file in files:
                with open(file.path, "r", encoding="utf-8") as _file:
                    print(file.path)
                    word = _file.read()
                    if word not in already_imported_words:
                        self.words_being_imported_raw.append(WordBeingImported(unprocessed_string=word))
                    else:
                        log(f"already imported: {word}", color="red")

        print(self.words_being_imported_raw)
        # show to user to clean them into matching patterns

        self.edit_dialog = EditNewWordsDialog(self)
        self.edit_dialog.show()
        self.edit_dialog.exec()

    def _load_imported_words(self):
        """Return all words that have already been imported into Anki"""
        with os.scandir(self.already_imported_words_folder) as files:
            files = [open(file.path, "r", encoding="utf-8").read().split("\n") for file in files]
            words = [x.strip() for file in files for x in file if (x and not x[0] == "#")]
            return list(set(words))

    def load_new_crawled_words(self):
        pass

    def update_tampermonkey_list(self):
        """Refresh the list of all imported words that the tampermonkey script reads"""

        # update the json of all ew anki cards for forgetting them through dict.cc Tampermonkey
        with open(fr"/hdd/Software Engineering/.files/2021-09-23 Dict.cc und Cambridge Importer/imported dict.cc card {self.dict_cc_list_id}.json", "w+", encoding="utf-8") as file:
            new_json = {}
            cards = []
            for deck_name in self.anki_deck_names:
                cards += [mw.col.get_card(card_id) for card_id in mw.col.find_cards(f'"deck:{deck_name}"')]
            cards = list(set(cards))
            for card in cards:
                note = card.note()
                cards = [card.id for card in note.cards()]
                learning = ""
                familiar = []
                for (name, value) in note.items():
                    if name == "Learning":
                        learning = value
                    if name.startswith("Familiar") and value and "<img" not in value:
                        familiar.append(value)
                familiar = "   /   ".join(familiar)
                new_json[learning] = {"de": familiar, "ids": cards}

            file.write(json.dumps(new_json, indent=2))

    def get_tts(self, word):
        log(f"Downloading Polly TTS of {word}...")

        audio_path = os.path.join(MEDIA_FOLDER, f"aws-polly-{word}.ogg")
        tts = requests.get(f"http://localhost:5231/get_ogg_bytes_aws?text={urllib.parse.quote(word)}&lang=en-US").content
        with open(audio_path, "wb") as file:
            file.write(tts)
            return DownloadedAudio(f'[sound:aws-tts-{word}.ogg]')

    def create_cards(self):
        log("Creating cards")

        for word in self.words_being_imported:

            needs_image = False
            reverse_card = True

            for count, this_word in enumerate(word.familiar):
                if this_word.endswith("+"):
                    needs_image = True
                    # Chop + needs image marker off word
                    word.familiar[count] = this_word[:-1].strip()

                if this_word.endswith("-"):
                    reverse_card = False
                    # Chop - no reverse marker off word
                    word.familiar[count] = this_word[:-1].strip()

            log(f"Importing {word.learning} - {' - '.join(word.familiar)}")

            fields = {"Learning": word.learning, "Bild": "needsimage" if needs_image else "", "Audio": "", "IPA": "", "Häufigkeit": str(self.get_prevalence_rate(word.learning_scrubbed)).zfill(6), "Learning scrubbed": word.learning_scrubbed,
                      "reverse card disabled": "3" if not reverse_card else ""}

            # Assign familiar words to their fields
            for i, x in enumerate(word.familiar[:10]):
                fields[f"Familiar {i + 1}"] = x

            # Download audio from Cambridge
            # check if there are any results for the word (if not, scrubbing[english] will be "False"
            # todo: detect if there is ipa but no audio (results in absurd url now)

            if self.get_ipa(word.learning_scrubbed):
                fields["IPA"] = self.get_ipa(word.learning_scrubbed)

            if audio := self.get_audio(word.learning_scrubbed):
                fields["Audio"] = audio.filename

            """log("Downloading TTS instead...")

            try:
                audio_path = os.path.join(MEDIA_FOLDER, f"google-tts-{scrubbed}.ogg")
                google_tts = requests.get(f"http://localhost:5231/get_ogg_bytes_aws?text={urllib.parse.quote(scrubbed)}&lang=en-US").content
                with open(audio_path, "wb") as file:
                    file.write(google_tts)
                    fields["Audio"] = f'[sound:aws-tts-{scrubbed}.ogg]'

            except Exception as e:
                print(e)"""

            # Create the new notes
            # Set the right deck (according to how common the word is) and model
            if self.language == "English":
                selected_deck_id = mw.col.decks.id(self.anki_deck_names[0] if self.get_prevalence_rate(word.learning_scrubbed) >= 100 else self.anki_deck_names[1])
            else:
                selected_deck_id = mw.col.decks.id(self.anki_deck_names[0])

            mw.col.decks.select(selected_deck_id)
            model = mw.col.models.by_name(self.note_type_name)
            deck = mw.col.decks.get(selected_deck_id)
            deck['mid'] = model['id']
            mw.col.decks.save(deck)
            model['did'] = selected_deck_id
            mw.col.models.save(model)

            note = mw.col.newNote()
            for (name, value) in note.items():
                if name in fields:
                    note[name] = fields[name]
            mw.col.addNote(note)

        tooltip("All words imported!")
        log("All words imported!", color="green")

        # Save a list of all the words that have just been imported
        with open(os.path.join(self.already_imported_words_folder, f"{datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S imported.txt')}"), "w+", encoding="utf-8") as file:
            file.write("\n".join([word.unprocessed_string for word in self.words_being_imported_raw]))

        # Refresh the list of all imported words that the tampermonkey script reads
        self.update_tampermonkey_list()

        # empty the folder that holds the crawled words before they get imported
        [os.remove(word.filename) for word in self.new_crawled_words_to_delete]

    def get_prevalence_rate(self, word: str) -> int:
        pass

    def get_ipa(self, word: str) -> str:
        pass

    def get_audio(self, word_scrubbed: str) -> DownloadedAudio | None:
        pass


class EnglishProfile(Profile):
    language = "English"

    dict_cc_list_id = "978781-EN-DE-09926"
    anki_deck_names = ["All::1) Sprachen::🇺🇸 Englisch::_New", "All::1) Sprachen::🇺🇸 Englisch::_New (rare)", "All::1) Sprachen::🇺🇸 Englisch::*"]
    already_imported_words_folder: str = None
    new_crawled_words_folder: str = None

    def __init__(self):
        super(EnglishProfile, self).__init__()

    @lru_cache
    def _cambridge_html(self, word) -> str | None:
        """"""
        log(f"looking up '{word}' on cambridge dictionary...", end="\t")
        html = load_url('https://dictionary.cambridge.org/de/worterbuch/englisch/' + word, True).text

        # check if there are any results for the word
        if "Die beliebtesten Suchbegriffe" not in html:
            log("found", color="green", start="")
            return html
        else:
            log("not found", color="red", start="")

    @lru_cache
    def get_audio(self, word_scrubbed: str) -> DownloadedAudio | None:
        """return ogg"""
        if html := self._cambridge_html(word_scrubbed):
            # Extract american pronunciation and IPA
            if any(html.find(x) == -1 for x in ["us dpron-i", 'type="audio/ogg" src="', '<span class="ipa dipa lpr-2 lpl-1">']):
                log("Does not have audio or IPA information!")
            else:
                american_part = html[html.find("us dpron-i"):]
                audio_url = american_part[american_part.find('type="audio/ogg" src="') + len('type="audio/ogg" src="'):]
                audio_url = "https://dictionary.cambridge.org" + audio_url[:audio_url.find('"/>')]

                try:
                    audio_path = os.path.join(MEDIA_FOLDER, f"cambridge-{word_scrubbed}.ogg")
                    with open(audio_path, "wb") as file:
                        file.write(load_url(audio_url, True).content)
                        return DownloadedAudio(filename=f'[sound:cambridge-{word_scrubbed}.ogg]')

                except Exception as e:
                    print(e)

        log(f"No Cambridge definition found for {word_scrubbed}", color="red")

    @lru_cache
    def get_ipa(self, word: str) -> str|None:
        html = self._cambridge_html(word)
        if not html or any(html.find(x) == -1 for x in ["us dpron-i", 'type="audio/ogg" src="', '<span class="ipa dipa lpr-2 lpl-1">']):
            return
        else:
            american_part = html[html.find("us dpron-i"):]
            return american_part[american_part.find('<span class="ipa dipa lpr-2 lpl-1">'):american_part.find("/</span></span>")]

    @lru_cache
    def get_prevalence_rate(self, word: str) -> int:
        """"""
        log(f"looking up '{word}' on phrasefinder...", end="\t")
        # Use the phrasefinder.io API to determine how common an english word is

        params = urllib.parse.urlencode({'corpus': 'eng-us', 'query': word.replace(" ", "%20"), 'topk': 20, 'format': 'tsv'}, safe="%20")
        print(params)
        try:
            response = requests.get('https://api.phrasefinder.io/search?' + params)
            i = int(math.ceil(int(response.text.split("\t")[1]) / 1000))
            log(f"{i}000 occurrences", color="green", start="")
            return i

        except IndexError as e:
            # the word can't be found
            return 0

    @lru_cache
    def scrub_word(self, word: str) -> str:
        """Remove annotations and parts of the term that aren't essential. Otherwise, Cambridge or phrasefinder might not recognize it"""
        scrubbed = word.split("\t")[0].strip()

        # Cut out these strings:
        cut = ["sth.", "sb.", " from ", " into ", " with "]
        for x in cut:
            scrubbed = scrubbed.replace(x, "")

        # Cut off anything after these strings:
        split = ["[", "{", "<", " for ", " to ", " of "]
        for x in split:
            scrubbed = scrubbed.split(x)[0]

        # cut off these strings if they occur at the very end
        end = [" to", " up", " into", " on", " upon", " off", " (off)", " about", " back"]
        for x in end:
            if scrubbed[-len(x):] == x:
                scrubbed = scrubbed[:-len(x)].strip()

        # cut off these strings if they occur at the very beginning of the term
        start = ["to ", "make ", "a ", "be "]
        for x in start:
            if scrubbed[:len(x)] == x:
                scrubbed = scrubbed[len(x):].strip()

        # Remove any special characters
        scrubbed = re.sub("[^abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZéâ '-]", '', scrubbed).strip()

        return scrubbed


class FrenchProfile(Profile):
    language = "French"
    anki_deck_names = ["All::1) Sprachen::French f. dict.cc"]
    dict_cc_list_id = "1031152-FR-DE-59911"
    already_imported_words_folder: str = None
    new_crawled_words_folder: str = None


EDIT_WORDS_SEPERATOR = "    ~    "
EDIT_WORDS_SEPERATOR_BASIC = "~"
