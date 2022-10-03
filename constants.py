import os
import urllib.parse
from os.path import join
from dataclasses import dataclass
import datetime
from aqt.qt import QAction
from aqt.utils import showInfo, tooltip
from .utils import *
from .edit_words_dialog import EditNewWordsDialog
from aqt import mw
from aqt import gui_hooks
from datetime import datetime
from .utils import all_imported_words
from anki.consts import *
import cachetools
from functools import lru_cache

BASE_FOLDER = r"/hdd/Software Engineering/.files/2021-09-23 Dict.cc und Cambridge Importer"
MEDIA_FOLDER = r"/home/robin/.local/share/Anki2/Benutzer 1/collection.media"


@dataclass
class DownloadedAudio:
    filename: str


@dataclass
class WordBeingImported:
    unprocessed_string: str
    learning: str = None
    familiar: str = None
    learning_scrubbed: str = None


@dataclass
class NewCrawledWordFileToDelete:
    filename: str


class Profile:
    language: str
    note_type_name: str = "Dict.cc imported"
    dict_cc_list_id: str
    done_folder: str
    new_crawled_words_folder: str
    new_crawled_words_to_delete: [str]
    words_being_imported: [WordBeingImported] = None

    def load_new_crawled_words(self):
        # create list of files to be deleted after import finishes
        self.new_crawled_words_to_delete = [NewCrawledWordFileToDelete(file.path) for file in os.scandir(self.new_crawled_words_folder)]

        # read new ew
        with os.scandir(self.new_crawled_words_folder) as files:
            files = [file for file in files]
            files = sorted(files, key=lambda x: x.name)

            words = [open(file.path, "r", encoding="utf-8").read() for file in files]
            [self.new.append(word) for word in words if word not in self.done]

            [log(f"already imported: {word}", color="red") for word in words if word in self.done]

        # show to user to clean them into matching patterns (using Qt Dialog with TextBox)

        self.edit_dialog = EditNewWordsDialog(self, "\n".join(self.new))
        self.edit_dialog.show()
        self.edit_dialog.exec()

    def load_imported_words(self):
        """Return all words that have already been imported into Anki"""
        with os.scandir(self.done_folder) as files:
            files = [open(file.path, "r", encoding="utf-8").read().split("\n") for file in files]
            words = [x.strip() for file in files for x in file if (x and not x[0] == "#")]
            return list(set(words))

    def update_tampermonkey_list(self):
        """Refresh the list of all imported words that the tampermonkey script reads"""
        with open(rf"/hdd/Software Engineering/.files/2021-09-23 Dict.cc und Cambridge Importer/imported dict.cc {self.dict_cc_list_id}.txt", "w+", encoding="utf-8") as file:
            file.write("\n".join(all_imported_words()))

        # update the json of all ew anki cards for forgetting them through dict.cc Tampermonkey
        with open(fr"/hdd/Software Engineering/.files/2021-09-23 Dict.cc und Cambridge Importer/imported dict.cc card {self.dict_cc_list_id}.json", "w+", encoding="utf-8") as file:
            new_json = {}
            cards = [mw.col.get_card(card_id) for card_id in mw.col.find_cards(f'"note:{self.note_type_name}" ')]
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

    def get_tss(self, word):
        log(f"Downloading Polly TTS of {word}...")

        audio_path = os.path.join(MEDIA_FOLDER, f"aws-polly-{word}.ogg")
        tts = requests.get(f"http://localhost:5231/get_ogg_bytes_aws?text={urllib.parse.quote(word)}&lang=en-US").content
        with open(audio_path, "wb") as file:
            file.write(tts)
            return DownloadedAudio(f'[sound:aws-tts-{word}.ogg]')

    def create_cards(self):
        log("Creating cards")
        # sort cards into groups
        grouped_words: {[str]} = {}

        for word in self.words_being_imported:

            english, german = (x.strip() for x in word.split("\t"))
            if english in grouped_words:
                grouped_words[english].append(german)
            else:
                grouped_words[english] = [german]

        for english, german in grouped_words.items():

            # detect if note is meant to be marked as needing an image
            needs_image = False

            for i, w in enumerate(german):
                if w[-1:] == "+":
                    needs_image = True
                    # Chop + needs image marker off word
                    german[i] = german[i][:-1].strip()

            # detect if note is meant to have reverse field set
            reverse = True
            for i, w in enumerate(german):
                if w[-1:] == "-":
                    reverse = False
                    # Chop - no reverse marker off word
                    german[i] = german[i][:-1].strip()
            log(f"Importing {english} - {german}")

            scrubbed = self.scrubbing[english]

            prevalence = int(get_phrasefinder(scrubbed) / 1000)
            fields = {"Englisch": english, "Bild": "needsimage" if needs_image else "", "Audio": "", "IPA": "", "Häufigkeit": str(prevalence).zfill(6), "Englisch scrubbed": scrubbed,
                      "reverse card disabled": "disabled during import" if not reverse else ""}

            # Assign german words to their fields
            for i, x in enumerate(german[:10]):
                fields[f"Deutsch {i + 1}"] = x

            # Wait till theres an internet connection to continue
            wait_for_internet_connection()

            # Download audio from Cambridge
            # check if there are any results for the word (if not, scrubbing[english] will be "False"
            # todo: detect if there is ipa but no audio (results in absurd url now)
            if html := self.cambridge_dict[scrubbed]:
                # Extract american pronunciation and IPA
                if any(html.find(x) == -1 for x in ["us dpron-i", 'type="audio/ogg" src="', '<span class="ipa dipa lpr-2 lpl-1">']):
                    log("Does not have audio or IPA information!")
                else:
                    american_part = html[html.find("us dpron-i"):]
                    audio_url = american_part[american_part.find('type="audio/ogg" src="') + len('type="audio/ogg" src="'):]
                    audio_url = "https://dictionary.cambridge.org" + audio_url[:audio_url.find('"/>')]
                    ipa = american_part[american_part.find('<span class="ipa dipa lpr-2 lpl-1">'):american_part.find("/</span></span>")]

                    try:
                        audio_path = os.path.join(MEDIA_FOLDER, f"cambridge-{scrubbed}.ogg")
                        with open(audio_path, "wb") as file:
                            file.write(load_url(audio_url, True).content)
                            fields["Audio"] = f'[sound:cambridge-{scrubbed}.ogg]'

                    except Exception as e:
                        print(e)

                    # Set field values
                    fields["IPA"] = ipa

            else:
                log(f"No Cambridge definition found for {scrubbed} ({english})", color="red")
                log("Downloading TTS instead...")

                try:
                    audio_path = os.path.join(MEDIA_FOLDER, f"google-tts-{scrubbed}.ogg")
                    google_tts = requests.get(f"http://localhost:5231/get_ogg_bytes_aws?text={urllib.parse.quote(scrubbed)}&lang=en-US").content
                    with open(audio_path, "wb") as file:
                        file.write(google_tts)
                        fields["Audio"] = f'[sound:aws-tts-{scrubbed}.ogg]'

                except Exception as e:
                    print(e)

            # Create the new notes
            # Set the right deck (according to how common the word is) and model
            selected_deck_id = mw.col.decks.id("All::1) Sprachen::🇺🇸 Englisch::_New" if prevalence >= 100 else "All::1) Sprachen::🇺🇸 Englisch::_New (rare)")
            mw.col.decks.select(selected_deck_id)
            model = mw.col.models.by_name(NOTE_TYPE_NAME)
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
        with open(os.path.join(DONE_FOLDER, f"{datetime.now().strftime('%Y-%m-%d %H-%M-%S imported.txt')}"), "w+", encoding="utf-8") as file:
            file.write("\n".join(self.new))

        # Refresh the list of all imported words that the tampermonkey script reads
        update_tampermonkey_list()

        # empty the folder that holds the crawled words before they get imported
        [os.remove(file.path) for file in self.delete_crawled_ew]


class EnglishProfile(Profile):
    language = "English"

    dict_cc_list_id = "978781-EN-DE-09926"
    done_folder: str = None
    new_crawled_words_folder: str = None

    def __post_init__(self):
        self.done_folder = join(BASE_FOLDER, "imported_done", self.dict_cc_list_id)
        self.new_folder = join(BASE_FOLDER, "dict cc crawled vocabulary", self.dict_cc_list_id)

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
                        return DownloadedAudio(f'[sound:cambridge-{word_scrubbed}.ogg]')

                except Exception as e:
                    print(e)

        log(f"No Cambridge definition found for {word_scrubbed}", color="red")

    @lru_cache
    def get_ipa(self, word: str) -> str:
        html = self._cambridge_html(word)
        if any(html.find(x) == -1 for x in ["us dpron-i", 'type="audio/ogg" src="', '<span class="ipa dipa lpr-2 lpl-1">']):
            return "XXX"
        else:
            american_part = html[html.find("us dpron-i"):]
            return american_part[american_part.find('<span class="ipa dipa lpr-2 lpl-1">'):american_part.find("/</span></span>")]

    @lru_cache
    def get_prevalence_rate(self, word: str) -> int:
        """"""
        log(f"looking up '{word}' on phrasefinder...", end="\t")
        # Use the phrasefinder.io API to determine how common an english word is

        params = urllib.parse.urlencode({'corpus': 'eng-us', 'query': word, 'topk': 20, 'format': 'tsv'})
        try:
            response = requests.get('https://api.phrasefinder.io/search?' + params)
            i = int(response.text.split("\t")[1]) / 1000
            log(f"{i}000 occurrences", color="green", start="")
            return i

        except IndexError as e:
            # the word can't be found
            return 0

    @lru_cache
    def scrub_word(self, word):
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
    language = "English"
    note_type_name = "__English (from Dict.cc) (new)"
    dict_cc_list_id = "978781-EN-DE-09926"
    done_folder: str = None
    new_crawled_words_folder: str = None


profiles = [Profile(language="French", note_type_name="__French (from Dict.cc)", dict_cc_list_id="1031152-FR-DE-59911"),
            Profile(language="English", note_type_name="__English (from Dict.cc) (new)", dict_cc_list_id="978781-EN-DE-09926")]

EDIT_WORDS_SEPERATOR = "    ~    "
EDIT_WORDS_SEPERATOR_BASIC = "~"
