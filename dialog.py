# Storing Dialog files.

import json
import requests
from aqt.qt import QDialog
from aqt.utils import tooltip
from .ui.welcome import Ui_Dialog as WelcomeUI
from .ui.settings import Ui_Dialog as SettingsUI
from .config import Settings

ORIGINAL_PROMPT = "You are a program intended to rewrite Anki cards. Rewrite the following Anki card while not changing any of the cloze-deleted text, and do not say anything else besides the reworded card. Try and vary the sentence structure appreciably. Preserve HTML formatting; don't use Markdown."

SUPERMEMO_PROMPT = "You are an expert Anki flashcard creator adhering strictly to SuperMemo's 20 rules of formulating knowledge.\n\nCORE OBJECTIVE:\nAlter the \"visual shape\" of the card (sentence structure and cloze order) while PRESERVING ALL SEMANTIC NUANCE and qualifiers from the original text.\n\nABSOLUTE RULES:\n1. Semantic Integrity: NEVER remove qualifying words (e.g., \"typically\", \"often\", \"usually\") or specific details that define the scope of the fact. The variant must be factually identical to the original.\n2. Structural Reordering: Significantly change the grammatical structure (e.g. switch between active and passive voice, or between a statement and a question). \n3. REQUIRED CLOZE SEQUENCE: If a \"REQUIRED CLOZE SEQUENCE\" is provided, you MUST rebuild the sentence so that the clozes appear in that exact visual order on the screen.\n4. Minimum Information Principle: Keep the variant concise and efficient to read, but prioritize semantic integrity above all else.\n5. Cloze Protection: NEVER modify the internal contents of any {{c1::...}} tag. The tags must remain perfectly intact.\n6. Formatting: Preserve ALL existing HTML tags (e.g., <i>, <b>, <u>, <span>, etc.). NEVER remove or strip formatting from technical terms or vocabulary. Do not use Markdown.\n7. SAFETY VALVE: If the card is a technical command, code snippet, or formula where structural reordering would compromise accuracy or requires adding descriptive filler, output ONLY the string [SKIP_REWORD].\n\nOutput ONLY the raw HTML string of the new card (or the safety valve string). No preambles, no explanations."

class WelcomeDialog(QDialog):

    def __init__(self, show_modal: bool = True):
        super().__init__()
        self.form = WelcomeUI()
        self.form.setupUi(self)
        self.form.checkBox.setChecked(show_modal)
        
class SettingsDialog(QDialog):

    def __init__(self, settings: Settings):
        super().__init__()
        self.form = SettingsUI()
        self.form.setupUi(self)
        self.settings = settings
        
        # Connect template selector
        self.form.templateSelect.currentIndexChanged.connect(self.apply_template)
        
        # Connect validate button
        self.form.validateModelButton.clicked.connect(self.validate_model)

    def validate_model(self):
        platform = self.form.platformSelect.currentIndex()
        api_key = self.form.APIKeyLineEdit.text()
        model = self.form.modelLineEdit.text()
        
        if not api_key or not model:
            tooltip("Please enter an API key and a model to validate.")
            return

        self.form.validateModelButton.setText("Validating...")
        self.form.validateModelButton.setEnabled(False)
        self.repaint() # Force UI update

        try:
            if platform == 0: # Mistral
                chat_response = requests.post(url="https://api.mistral.ai/v1/chat/completions",
                                              headers={'Content-Type': 'application/json',
                                                      'Accept': 'application/json',
                                                      'Authorization': 'Bearer ' + api_key},
                                              data=json.dumps({'model': model,
                                                               'messages': [
                                                                   {'role': 'user', 'content': 'hello'}
                                                               ]}),
                                              timeout=10)
                if chat_response.status_code == 200:
                    tooltip(f"Success! Model '{model}' is valid on Mistral.")
                else:
                    msg = chat_response.json().get('message', f'Error {chat_response.status_code}')
                    tooltip(f"Validation failed: {msg}")
                    
            elif platform == 1: # Gemini
                chat_response = requests.post(
                    url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
                    headers={'Content-Type': 'application/json'},
                    data=json.dumps({
                        "contents": [{"role": "user", "parts": [{"text": "hello"}]}]
                    }),
                    timeout=10
                )
                if chat_response.status_code == 200:
                    tooltip(f"Success! Model '{model}' is valid on Gemini.")
                else:
                    try:
                        msg = chat_response.json().get('error', {}).get('message', f'Error {chat_response.status_code}')
                    except:
                        msg = f'Error {chat_response.status_code}'
                    tooltip(f"Validation failed: {msg}")
                    
        except Exception as e:
            tooltip(f"Validation error: {e}")
        finally:
            self.form.validateModelButton.setText("Validate Model")
            self.form.validateModelButton.setEnabled(True)

    def apply_template(self, index: int):
        from aqt.qt import QMessageBox
        
        current_text = self.form.textEdit.toPlainText().strip()
        new_text = SUPERMEMO_PROMPT if index == 0 else ORIGINAL_PROMPT
        
        # Don't prompt if the current text is already exactly one of the templates or empty
        if current_text and current_text != SUPERMEMO_PROMPT.strip() and current_text != ORIGINAL_PROMPT.strip():
            reply = QMessageBox.question(
                self, 
                "Overwrite Prompt?", 
                "Loading a template will overwrite your current context prompt. Are you sure you want to proceed?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        self.form.textEdit.setText(new_text)

    def show(self):
        super().show()
        self.load_from_config()

    def load_from_config(self):

        # Set all objects of simple datatypes.
        self.form.keySequenceEdit.setKeySequence(str(self.settings.shortcut_clear_current_card))
        self.form.keySequenceEdit_2.setKeySequence(str(self.settings.shortcut_clear_all_cards))
        self.form.keySequenceEdit_3.setKeySequence(str(self.settings.shortcut_include_exclude))
        self.form.keySequenceEdit_5.setKeySequence(str(self.settings.shortcut_exclude_deck))
        self.form.keySequenceEdit_4.setKeySequence(str(self.settings.shortcut_pause))
        self.form.APIKeyLineEdit.setText(str(self.settings.api_key))
        self.form.modelLineEdit.setText(str(self.settings.model))
        self.form.maxRendersLineEdit.setText(str(self.settings.max_renders))
        self.form.textEdit.setText(str(self.settings.context))
        self.form.retryCountLineEdit.setText(str(self.settings.num_retries))
        self.form.retryDelayLineEdit.setText(str(self.settings.retry_delay_seconds))
        self.form.checkBox.setChecked(bool(self.settings.clear_cache_on_reviewer_end))
        self.form.shuffleDeletionsCheckBox.setChecked(bool(self.settings.shuffle_clozes))
        self.form.platformSelect.setCurrentIndex(int(self.settings.platform_index))

        # Set the excluded types.
        self.form.listWidget.clear()
        self.form.listWidget.addItems([str(item) for item in self.settings.exclude_note_types])

        # Set the excluded decks.
        self.form.listWidgetDecks.clear()
        self.form.listWidgetDecks.addItems([str(item) for item in self.settings.exclude_decks])
