import urllib.parse

from ..constants import *


class Profile:
    language: str
    pollyLangCode: str  # for my own getPollyConfiguration function
    anki_deck_names: [str]
    dict_cc_list_id: str
    note_type_name: str = "Dict.cc imported"
    already_imported_words_folder: str = None
    new_crawled_words_folder: str = None
    new_crawled_words_to_delete: [NewCrawledWordFileToDelete] = None
    words_being_imported: [WordBeingImported]= None
    words_being_imported_raw: [WordBeingImported]= None

    def scrub_word(self, word: str) -> str:
        pass

    def __init__(self):
        self.already_imported_words_folder = join(BASE_FOLDER, "imported_done", self.dict_cc_list_id)
        self.new_crawled_words_folder = join(BASE_FOLDER, "dict cc crawled vocabulary", self.dict_cc_list_id)
        print("init on Profile")

    def start_import(self):
        self.words_being_imported_raw = []
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
        fileName = f"aws-polly-{self.pollyLangCode}-{word}.ogg"
        audio_path = os.path.join(MEDIA_FOLDER,fileName )
        tts = requests.get(f"http://localhost:5231/get_ogg_bytes_aws?" + urllib.parse.urlencode({"text": word, "lang": self.pollyLangCode})).content
        with open(audio_path, "wb") as file:
            file.write(tts)
            return DownloadedAudio(f'[sound:{fileName}]')

    def create_cards(self):
        log("Creating cards")

        for word in self.words_being_imported:
            log(word)
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

            fields = {"Learning": word.learning,
                      "Bild": "needsimage" if needs_image else "",
                      "Audio": "",
                      "IPA": "",
                      "Häufigkeit": str(self.get_prevalence_rate(word.learning_scrubbed)).zfill(6),
                      "Learning scrubbed": word.learning_scrubbed,
                      "reverse card disabled": "3" if not reverse_card else "",
                      "both-front": word.both_front}

            # Assign familiar words to their fields
            for i, x in enumerate(word.familiar[:10]):
                fields[f"Familiar {i + 1}"] = x

            # Download audio from Cambridge
            # check if there are any results for the word (if not, scrubbing[english] will be "False"
            # todo: detect if there is ipa but no audio (results in absurd url now)

            if self.get_ipa(word.learning_scrubbed):
                fields["IPA"] = self.get_ipa(word.learning_scrubbed)
            
            if word.learning_scrubbed.endswith("-"):
                word.learning_scrubbed=word.learning_scrubbed[:-1]
                print(f"not loading audio for {word.learning_scrubbed}")
            else:
                if audio := self.get_audio(word.learning_scrubbed):
                    fields["Audio"] = audio.filename

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
        return self.get_tts(word_scrubbed) 
