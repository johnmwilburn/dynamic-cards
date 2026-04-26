# -*- coding: utf-8 -*-

from aqt.qt import *

PLATFORMS = ["Mistral AI (Mistral)", "Gemini (Google)"]

class Ui_Dialog(object):
    def setupUi(self, Dialog: QDialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(480, 750)
        
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
        self.platformSelect.addItems(PLATFORMS)
        self.llmForm.addRow(u"Platform", self.platformSelect)
        
        self.APIKeyLineEdit = QLineEdit()
        self.llmForm.addRow(u"API key", self.APIKeyLineEdit)
        
        self.modelLineEdit = QLineEdit()
        self.llmForm.addRow(u"Model", self.modelLineEdit)
        
        self.maxRendersLineEdit = QLineEdit()
        self.llmForm.addRow(u"Max renders", self.maxRendersLineEdit)
        
        self.textEdit = QTextEdit()
        self.textEdit.setMinimumHeight(150)
        self.llmForm.addRow(u"Context", self.textEdit)
        
        self.retryCountLineEdit = QLineEdit()
        self.llmForm.addRow(u"Retry count", self.retryCountLineEdit)
        
        self.retryDelayLineEdit = QLineEdit()
        self.llmForm.addRow(u"Retry delay (sec)", self.retryDelayLineEdit)
        
        self.scrollLayout.addLayout(self.llmForm)

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
