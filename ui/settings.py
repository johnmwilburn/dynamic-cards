# -*- coding: utf-8 -*-

from aqt.qt import *

PLATFORMS = ["Mistral AI (mistral-large-latest)", "Google Gemini (gemini-3-pro-preview)"]
PROMPTS = ["SuperMemo (High Structural Variety)", "Original (Subtle Rewording)"]

class Ui_Dialog(object):
    def setupUi(self, Dialog: QDialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(550, 850)
        
        self.mainLayout = QVBoxLayout(Dialog)
        
        # Create Scroll Area
        self.scrollArea = QScrollArea(Dialog)
        self.scrollArea.setWidgetResizable(True)
        self.scrollAreaWidgetContents = QWidget()
        self.scrollLayout = QVBoxLayout(self.scrollAreaWidgetContents)
        
        # Title
        self.label = QLabel(u"<h1>Dynamic Cards Settings</h1>")
        self.scrollLayout.addWidget(self.label)

        self.label_5 = QLabel(u"<a href='https://github.com/Petronian/dynamic-cards'>Need usage instructions? Click here!</a>")
        self.label_5.setOpenExternalLinks(True)
        self.scrollLayout.addWidget(self.label_5)

        # Shortcuts Section
        self.scrollLayout.addWidget(QLabel(u"<b>Keyboard Shortcuts</b>"))
        self.shortcutForm = QFormLayout()
        
        self.keySequenceEdit = QKeySequenceEdit()
        self.shortcutForm.addRow(u"Clear current card from cache", self.keySequenceEdit)
        
        self.keySequenceEdit_2 = QKeySequenceEdit()
        self.shortcutForm.addRow(u"Clear all cards from cache", self.keySequenceEdit_2)
        
        self.keySequenceEdit_3 = QKeySequenceEdit()
        self.shortcutForm.addRow(u"Exclude/include note type", self.keySequenceEdit_3)

        self.keySequenceEdit_5 = QKeySequenceEdit()
        self.shortcutForm.addRow(u"Exclude/include current deck", self.keySequenceEdit_5)
        
        self.keySequenceEdit_4 = QKeySequenceEdit()
        self.shortcutForm.addRow(u"Pause dynamic generation", self.keySequenceEdit_4)
        
        self.scrollLayout.addLayout(self.shortcutForm)

        # LLM Section
        self.scrollLayout.addWidget(QLabel(u"<b>LLM Functionality</b>"))
        self.llmForm = QFormLayout()
        
        self.platformSelect = QComboBox()
        self.platformSelect.addItems(["Mistral AI", "Google Gemini"])
        self.llmForm.addRow(u"AI Platform", self.platformSelect)
        
        self.APIKeyLineEdit = QLineEdit()
        self.llmForm.addRow(u"API key", self.APIKeyLineEdit)
        
        self.modelHBox = QHBoxLayout()
        self.modelLineEdit = QLineEdit()
        self.modelHBox.addWidget(self.modelLineEdit)
        self.validateModelButton = QPushButton(u"Validate Model")
        self.modelHBox.addWidget(self.validateModelButton)
        self.llmForm.addRow(u"Model", self.modelHBox)

        self.modelExplanation = QLabel(u"<small>Note: Weaker models may struggle to produce good variants while adhering to strict structural rules.</small>")
        self.modelExplanation.setWordWrap(True)
        self.modelExplanation.setStyleSheet("color: gray;")
        self.llmForm.addRow(u"", self.modelExplanation)
        
        self.maxRendersLineEdit = QLineEdit()
        self.llmForm.addRow(u"Max renders", self.maxRendersLineEdit)
        
        self.scrollLayout.addLayout(self.llmForm)

        # Prompt Section
        self.scrollLayout.addWidget(QLabel(u"<b>Prompt Configuration</b>"))
        self.promptForm = QFormLayout()

        self.templateSelect = QComboBox()
        self.templateSelect.addItems(PROMPTS)
        self.promptForm.addRow(u"Load Template", self.templateSelect)

        self.scrollLayout.addLayout(self.promptForm)

        # Shuffle Cloze Toggle
        self.shuffleDeletionsCheckBox = QCheckBox(u"Require LLM to shuffle the order of cloze deletions")
        self.scrollLayout.addWidget(self.shuffleDeletionsCheckBox)
        
        self.shuffleExplanation = QLabel(u"<small>If enabled, Python will pre-shuffle your clozes and force the AI to build the sentence around that new sequence. This helps break visual pattern-matching for cards with multiple deletions.</small>")
        self.shuffleExplanation.setWordWrap(True)
        self.shuffleExplanation.setStyleSheet("color: gray;")
        self.scrollLayout.addWidget(self.shuffleExplanation)
        
        self.textEdit = QTextEdit()
        self.textEdit.setMinimumHeight(300)
        self.scrollLayout.addWidget(QLabel(u"Current Context Prompt:"))
        self.scrollLayout.addWidget(self.textEdit)
        
        self.configForm = QFormLayout()
        self.retryCountLineEdit = QLineEdit()
        self.configForm.addRow(u"Retry count", self.retryCountLineEdit)
        
        self.retryDelayLineEdit = QLineEdit()
        self.configForm.addRow(u"Retry delay (sec)", self.retryDelayLineEdit)
        self.scrollLayout.addLayout(self.configForm)

        # Review Section
        self.scrollLayout.addWidget(QLabel(u"<b>Review Behavior</b>"))
        self.checkBox = QCheckBox(u"Clear cache on review end")
        self.scrollLayout.addWidget(self.checkBox)

        # Exclusions Section
        self.scrollLayout.addWidget(QLabel(u"<b>Excluded Note Types</b> (double-click to remove)"))
        self.listWidget = QListWidget()
        self.listWidget.setMinimumHeight(100)
        self.listWidget.itemDoubleClicked.connect(self.handleListWidgetDoubleClick)
        self.scrollLayout.addWidget(self.listWidget)

        self.scrollLayout.addWidget(QLabel(u"<b>Excluded Decks</b> (double-click to remove)"))
        self.listWidgetDecks = QListWidget()
        self.listWidgetDecks.setMinimumHeight(100)
        self.listWidgetDecks.itemDoubleClicked.connect(self.handleListWidgetDecksDoubleClick)
        self.scrollLayout.addWidget(self.listWidgetDecks)

        # Finalize Scroll Area
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)
        self.mainLayout.addWidget(self.scrollArea)

        # Buttons
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)
        self.buttonBox.accepted.connect(Dialog.accept)
        self.buttonBox.rejected.connect(Dialog.reject)
        self.mainLayout.addWidget(self.buttonBox)

    def handleListWidgetDoubleClick(self, item: QListWidgetItem):
        self.listWidget.takeItem(self.listWidget.row(item))

    def handleListWidgetDecksDoubleClick(self, item: QListWidgetItem):
        self.listWidgetDecks.takeItem(self.listWidgetDecks.row(item))
