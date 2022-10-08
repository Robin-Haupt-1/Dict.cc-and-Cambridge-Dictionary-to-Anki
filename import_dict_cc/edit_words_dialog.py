from aqt.qt import QDialog, QGridLayout, QTextEdit, QScrollBar, QPushButton
from PyQt6.QtGui import QCloseEvent, QFont, QTextBlockFormat, QTextCursor
from PyQt6.QtCore import Qt
from PyQt6 import QtGui
from aqt.utils import showInfo
from utils import load_url, wait_for_internet_connection, log, DebounceTimer
from aqt import mw
from math import ceil
from constants import *
from collections import defaultdict

numbers = "\n".join([str(x) for x in range(100)])


def set_line_height(textedit: QTextEdit, height: int = 40):
    """Set the line height of given QTextEdit by merging it with a QTextBlockFormat"""
    # Reference: https://stackoverflow.com/questions/10250533/set-line-spacing-in-qtextedit

    blockFmt = QTextBlockFormat()
    blockFmt.setLineHeight(height, 2)  # 2 = LineHeightTypes.FixedHeight

    theCursor = textedit.textCursor()
    theCursor.clearSelection()
    theCursor.select(QTextCursor.SelectionType.Document)
    theCursor.mergeBlockFormat(blockFmt)


class EditNewWordsDialog(QDialog):
    profile = None

    def __init__(self, profile):
        super(EditNewWordsDialog, self).__init__()
        self.profile = profile

        # set up font
        font = QFont()
        font.setPointSize(14)

        # Textedit indicating how the program groups words based on their english side. To help with refactoring them into appropriate groups
        self.word_groups = QTextEdit()
        self.word_groups.setLineWrapMode(QTextEdit.NoWrap)
        self.word_groups.setMaximumWidth(40)
        self.word_groups.setText(numbers)
        self.word_groups.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.word_groups_scrollbar: QScrollBar = self.word_groups.verticalScrollBar()
        self.word_groups.setFont(font)
        self.word_groups.setEnabled(False)

        # Textedit with new english and german words, seperated by ~
        self.new_words = QTextEdit()
        self.new_words.setLineWrapMode(QTextEdit.NoWrap)
        self.new_words.setText("\n".join([word.unprocessed_string.replace("\t", "       ~       ") for word in profile.words_being_imported_raw]))
        self.new_words.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.new_words_scrollbar: QScrollBar = self.new_words.verticalScrollBar()
        self.new_words_scrollbar.valueChanged.connect(self.on_scroll)
        self.new_words.setFont(font)
        self.new_words.textChanged.connect(self.words_changed)

        # self.words_changed()

        # Done editing button
        self.done_button = QPushButton()
        self.done_button.setText("Done editing")
        self.done_button.clicked.connect(self.done_)

        # Set up layout
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.addWidget(self.word_groups, 0, 0)
        grid.addWidget(self.new_words, 0, 1)
        grid.addWidget(self.done_button, 1, 1)
        self.setLayout(grid)
        self.setWindowTitle('Edit new words')
        self.setMinimumWidth(1200)
        self.setMinimumHeight(1000)
        sb = self.new_words.verticalScrollBar()
        sb.setValue(sb.maximum())

        [set_line_height(x) for x in [self.new_words, self.word_groups]]

    def on_scroll(self, position):
        """adjust the scroll position of cambridge_available and original_words and phrasefinder rank to keep synchronized with 'scrubbed' textedit"""

        [set_line_height(x) for x in [self.new_words, self.word_groups]]
        self.word_groups.verticalScrollBar().setValue(self.new_words.verticalScrollBar().value())
        #print(self.new_words.verticalScrollBar().value())
        #print(position)

    def get_words(self):
        return self.new_words.toPlainText().strip()

    def words_changed(self, *args):
        """rebuild the word_groups textedit"""

        # extract all unique english words and assign them a number
        word_groups = {}  # all unique words as keys, their number as values
        english_words = [word.split(EDIT_WORDS_SEPERATOR_BASIC)[0].strip() for word in self.get_words().split("\n")]

        # TODO defaultdict
        for english_word in english_words:
            if english_word not in word_groups:
                word_groups[english_word] = len(word_groups.keys()) + 1

        word_group_content = "\n".join(["----" if x % 2 == 0 else "////" for x in [word_groups[y] for y in english_words]])
        self.word_groups.setText(word_group_content)
        [set_line_height(x) for x in [self.word_groups]]
        self.word_groups.verticalScrollBar().setValue(self.new_words.verticalScrollBar().value())

    def done_(self):
        """pass unique words on to user to verify automated scrubbing output"""
        self.close()

        words_with_translations: dict[str, WordBeingImported] = {}
        for word in self.get_words().split("\n"):
            learning, familiar = word.split("~", 1)
            familiar = familiar.strip()
            learning = learning.strip()

            if learning not in words_with_translations:
                words_with_translations[learning] = WordBeingImported(learning=learning, familiar=[])
            words_with_translations[learning].familiar.append(familiar)

        self.profile.words_being_imported = list(words_with_translations.values())

        # show dialog to allow user to correct the scrubbing
        correct_scrubbed_output_dialog = CorrectScrubbingOutput(self.profile)
        correct_scrubbed_output_dialog.show()
        correct_scrubbed_output_dialog.exec()


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Correct Scrubbing Window


class CorrectScrubbingOutput(QDialog):
    def __init__(self, profile):
        super(CorrectScrubbingOutput, self).__init__()
        self.words_being_reviewed = profile.words_being_imported
        self.profile = profile

        self.look_up_scrubbed_timer2 = DebounceTimer(self.look_up_scrubbed,
                                                     700)  # timer to look up newly entered corrected versions of scrubbed terms on cambridge dictionary. timeout so as to not make the program freeze after every keystroke.

        # Set up font for textedits
        font = QFont()
        font.setPointSize(14)

        # Textedit containing original, full-length terms
        self.original_words = QTextEdit()
        self.original_words.setLineWrapMode(QTextEdit.NoWrap)
        self.original_words.setMaximumWidth(250)
        self.original_words.setText("\n".join([word.learning for word in self.profile.words_being_imported]))
        self.original_words.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.original_words.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.original_words.setFont(font)
        self.original_words.setEnabled(False)

        # Textedit containing the automatically scrubbed version of the original words and allowing user to edit them
        self.scrubbed = QTextEdit()
        self.scrubbed.setLineWrapMode(QTextEdit.NoWrap)
        self.scrubbed.setMinimumWidth(250)
        self.scrubbed.setText(("\n".join([self.profile.scrub_word(word.learning) for word in self.profile.words_being_imported])))
        self.scrubbed.verticalScrollBar().valueChanged.connect(self.on_scroll)
        self.scrubbed.setFont(font)
        self.scrubbed.textChanged.connect(lambda: self.look_up_scrubbed_timer2.trigger())

        # Textedit indicating whether the term can be found on cambridge dictionary (found IPA if yes, otherwise 'XX')
        self.cambridge_ipa = QTextEdit()
        self.cambridge_ipa.setLineWrapMode(QTextEdit.NoWrap)
        self.cambridge_ipa.setMinimumWidth(250)
        self.cambridge_ipa.setText("")
        self.cambridge_ipa.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.cambridge_ipa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.cambridge_ipa.setFont(font)
        self.cambridge_ipa.setEnabled(False)

        # Textedit showing how often the term occurs in the phrasefinder corpus
        self.phrasefinder_rank = QTextEdit()
        self.phrasefinder_rank.setLineWrapMode(QTextEdit.NoWrap)
        self.phrasefinder_rank.setMaximumWidth(100)
        self.phrasefinder_rank.setAlignment(Qt.AlignRight)
        self.phrasefinder_rank.setText("")
        self.phrasefinder_rank.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.phrasefinder_rank.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.phrasefinder_rank.setFont(font)
        self.phrasefinder_rank.setEnabled(False)

        # button to finish editing and create cards
        self.done_button = QPushButton()
        self.done_button.setText("Done editing")
        self.done_button.clicked.connect(self.done_)

        # set line height on all textedits

        [self.set_line_height(x) for x in [self.original_words, self.phrasefinder_rank, self.cambridge_ipa, self.scrubbed]]

        # Set up layout
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.addWidget(self.original_words, 0, 0)
        grid.addWidget(self.scrubbed, 0, 1)
        grid.addWidget(self.cambridge_ipa, 0, 2)
        grid.addWidget(self.phrasefinder_rank, 0, 3)
        grid.addWidget(self.done_button, 1, 1)
        self.setLayout(grid)
        self.setWindowTitle('Edit scrubbing output')
        self.setMinimumWidth(500)
        self.setMinimumHeight(1000)
        self.look_up_scrubbed()

    def on_scroll(self, position):
        """adjust the scroll position of cambridge_available and original_words and phrasefinder rank to keep synchronized with 'scrubbed' textedit"""
        self.original_words.verticalScrollBar().setValue(position)
        self.cambridge_ipa.verticalScrollBar().setValue(position)
        self.phrasefinder_rank.verticalScrollBar().setValue(position)

    def look_up_scrubbed(self, *args):
        """Look up all new scrubbed terms on cambridge dictionary and phrasefinder website. store results in cache variables"""

        scrubbed = [x.strip() for x in self.scrubbed.toPlainText().strip().split("\n")]

        self.cambridge_ipa.setText("<br>".join([self.profile.get_ipa(s) or "XXX" for s in scrubbed]))

        # rebuild the phrasefinder_rank textedit content
        self.phrasefinder_rank.setText("\n".join([str(self.profile.get_prevalence_rate(s)).zfill(6) for s in scrubbed]))

        # set both 'indicator' textedits to the correct line spacing
        self.set_line_height(self.phrasefinder_rank)
        self.set_line_height(self.scrubbed)

        self.set_line_height(self.cambridge_ipa)

        # scroll all textedits to the correct position again
        self.on_scroll(self.scrubbed.verticalScrollBar().value())

    def set_line_height(self, textedit: QTextEdit, height: int = 40):
        """Set the line height of given QTextEdit by merging it with a QTextBlockFormat"""
        # Reference: https://stackoverflow.com/questions/10250533/set-line-spacing-in-qtextedit

        blockFmt = QTextBlockFormat()
        blockFmt.setLineHeight(height, 2)  # 2 = LineHeightTypes.FixedHeight

        theCursor = textedit.textCursor()
        theCursor.clearSelection()
        theCursor.select(QTextCursor.SelectionType.Document)
        theCursor.mergeBlockFormat(blockFmt)

    def get_ipa(self, word: str):
        html = self.cambridge_available_cache[word]
        if any(html.find(x) == -1 for x in ["us dpron-i", 'type="audio/ogg" src="', '<span class="ipa dipa lpr-2 lpl-1">']):
            return "XXX"
        else:
            american_part = html[html.find("us dpron-i"):]
            return american_part[american_part.find('<span class="ipa dipa lpr-2 lpl-1">'):american_part.find("/</span></span>")]

    def done_(self):
        self.close()
        original = [x.strip() for x in self.original_words.toPlainText().split("\n")]
        scrubbed = [x.strip() for x in self.scrubbed.toPlainText().split("\n")]

        mapped = dict([(original[i], scrubbed[i]) for i in range(len(original))])

        for word in self.profile.words_being_imported:
            word.learning_scrubbed = mapped[word.learning]

        # .parent.scrubbing_edited(self.words_with_tabs, dict([(original[x], scrubbed[x]) for x in range(len(original))]), self.cambridge_available_cache)
        self.profile.create_cards()
