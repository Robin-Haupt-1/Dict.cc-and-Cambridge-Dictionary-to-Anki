from .Profile import *


class EnglishProfile(Profile):
    language = "English"
    pollyLangCode = "us"
    dict_cc_list_id = "978781-EN-DE-09926"
    anki_deck_names = ["All::1) Sprachen::🇺🇸 Englisch::_New", "All::1) Sprachen::🇺🇸 Englisch::_New (rare)", "All::1) Sprachen::🇺🇸 Englisch::*"]


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

        html = self._cambridge_html(word_scrubbed)
        if not html:
            log(f"No Cambridge definition found for {word_scrubbed}", color="red")
            return

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


    @lru_cache
    def get_ipa(self, word: str) -> str | None:
        html = self._cambridge_html(word)
        if not html or any(html.find(x) == -1 for x in ["us dpron-i", 'type="audio/ogg" src="', '<span class="ipa dipa lpr-2 lpl-1">']):
            return
        else:
            american_part = html[html.find("us dpron-i"):]
            if not "</span>/</span></span>" in american_part:
                return
            return american_part[american_part.find('<span class="ipa dipa lpr-2 lpl-1">'):american_part.find("</span>/</span></span>")]

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
