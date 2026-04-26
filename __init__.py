from typing import Callable, Optional, Tuple, List
from aqt import QEvent, QObject, mw, gui_hooks, QMenu
from aqt.qt import QAction, qconnect, QKeySequence
from aqt.editor import Editor, EditorMode
from aqt.reviewer import Reviewer
from aqt.utils import tooltip as tooltip_aqt
from anki.cards import Card
from anki.notes import Note
from anki.template import TemplateRenderOutput
from random import choice, shuffle
import requests
import json
import re
import time
import random
from os.path import join, dirname, abspath

# Multitasking
import queue
import threading

# Caching
import sqlite3

# Local imports
from .dialog import WelcomeDialog, SettingsDialog
from .config import Config

# TO DO:
# * PRETTIFY FUNCTION NAMES
# * ORGANIZE CODE INTO SEPARATE FILES (SQL, ETC.) 
# * MAKE INTUITIVE ERROR MESSAGES FOR RATE LIMITS
# * STORE AND AUTOSWITCH API KEYS BASED ON RATE LIMITS
# * CLEAN UI ON MACOS

# Create global variables.
config_dict = mw.addonManager.getConfig(__name__)
config = Config(mw.addonManager, __name__, debug = False)

# CACHING

def connect_dynamic_db():
    conn = sqlite3.connect(config.settings.CACHE)
    return conn, conn.cursor()

def setup_dynamic_db():
    conn, cursor = connect_dynamic_db()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS id_to_strings (
        id INTEGER PRIMARY KEY,
        items TEXT,
        last_renders TEXT
    )
    """)
    conn.close()

# Debug function declarations
def clear_dynamic_db():
    conn, cursor = connect_dynamic_db()
    cursor.execute("DROP TABLE IF EXISTS id_to_strings")
    conn.close()
    setup_dynamic_db()

# Function to look up cached strings by ID
def get_strings_by_id(id_val: int) -> List[str]:
    conn, cursor = connect_dynamic_db()
    cursor.execute("SELECT items FROM id_to_strings WHERE id = ?", (id_val,))
    result = cursor.fetchone()
    if config.debug: print(f'SQL strings for {id_val}:', result)
    conn.commit()
    conn.close()
    try:
        if result and result[0]:
            return json.loads(result[0])  # Deserialize JSON string to list
    except Exception as e:
        if config.debug: print(f'Malformatted strings data for note id {id_val} with {type(e)}:', e)

# Function to look up cached strings by ID
def get_last_renders_by_id(id_val: int) -> Optional[dict[int, int]]:
    conn, cursor = connect_dynamic_db()
    cursor.execute("SELECT last_renders FROM id_to_strings WHERE id = ?", (id_val,))
    result = cursor.fetchone()
    if config.debug: print(f'SQL last render for {id_val}:', result)
    conn.commit()
    conn.close()
    try:
        return {int(x): int(y) for x, y in json.loads(result[0]).items()} if result else None
    except Exception as e:
        if config.debug: print(f'Malformatted last renders data for note id {id_val} with {type(e)}:', e)
        
# Function to look up all cached info by ID
def get_all_by_id(id_val: int) -> List[str]:
    conn, cursor = connect_dynamic_db()
    cursor.execute("SELECT items, last_renders FROM id_to_strings WHERE id = ?", (id_val,))
    result = cursor.fetchone()
    if config.debug: print(f'SQL all for {id_val}:', result)
    conn.commit()
    conn.close()

    try:
        if result and result[0]:
            texts, last_renders = result
            return json.loads(texts), {int(x): int(y) for x, y in json.loads(last_renders).items()}  # Deserialize JSON string to list
    except Exception as e:
        if config.debug: print(f'Malformatted data for note id {id_val} with {type(e)}:', e)

# Function to set cached strings by ID
def set_all_by_id(id_val: int, strings: List[str], last_renders: Optional[dict[int, int]]):
    conn, cursor = connect_dynamic_db()
    cursor.execute(f"INSERT OR REPLACE INTO id_to_strings (id, items, last_renders) VALUES (?, ?, ?)", (id_val, json.dumps(strings), json.dumps(last_renders)))
    conn.commit()
    conn.close()

# Function to set cached strings by ID
def set_strings_by_id(id_val: int, strings: List[str]):
    # See if id exists
    last_render = get_last_renders_by_id(id_val)
    set_all_by_id(id_val, strings, last_render if last_render is not None else {i: 0 for i, _ in enumerate(strings)})

# Function to set last render by ID
def set_last_renders_by_id(id_val: int, last_renders: dict[int, int]):
    # See if id exists
    strings = get_strings_by_id(id_val)
    set_all_by_id(id_val, strings if strings is not None else [""] * len(last_renders), last_renders)

# Additional helper function for clearing an entry
def clear_all_by_id(id_val: int):
    conn, cursor = connect_dynamic_db()
    cursor.execute("DELETE FROM id_to_strings WHERE id = ?", (id_val,))
    conn.commit()
    conn.close()

def _tooltip(*args, **kwargs):
    if config.debug: print(*args, **kwargs)
    tooltip_aqt(*args, **kwargs)

def tooltip(*args, **kwargs):
    mw.taskman.run_on_main(lambda: _tooltip(*args, **kwargs))

# Manage a queue for tasks.
class RewordingWorkerQueue:

    # This object must be started and should start when reviewer inits (see hook)
    def __init__(self):
        self.queue = queue.Queue()
        self.worker_thread = None
        self.running = False
        if config.debug: tooltip('Queue initialized.')

    # Start the worker queue if not already started.
    def start(self):
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self.worker, daemon=True)
            self.worker_thread.start()
            if config.debug: tooltip('Queue started.')

    # Continuously pop tasks off the queue
    # Do so one-by-one to avoid throttling!
    def worker(self):
        while self.running:
            try:
                func, args = self.queue.get(timeout=1)
                func(args)
                self.queue.task_done()
            except queue.Empty:
                continue

    # Task helper method
    def _task_helper(self, card: Card):
        try:
            cne = poll_cached_note_for_card(card)
            new_text = create_new_dynamic_wording(note=card.note(), existing_texts=cne.texts)
            if new_text is not None:
                update_cached_note_for_card(card=card, new_text=new_text)
                if config.debug: tooltip(f'Completed new wording task for card {card.id}.')
            elif config.debug:
                print(f'Could not complete new wording task for card {card.id}.')
        except Exception as e:
            tooltip(str(e))

    # Add new tasks to the queue
    def add_render_task(self, card: Card):
        self.start()
        self.queue.put((self._task_helper, card))
        if config.debug: tooltip(f'Queued card {card.id} for new wording task.')

    # Stop the queue.
    def stop(self, immediate=False):
        self.running = False
        # Don't join the thread here as it can cause Anki to hang if a network
        # request is in progress. The thread is a daemon and will exit on its own.
        if config.debug: tooltip(f'Queue stopped.')

    # Reset the queue and have it start running again.
    def reset(self, immediate=False):
        self.stop(immediate=immediate)
        self.start()
        if config.debug: tooltip(f'Queue reset.')

# Note entry format for use in the cache.
class CachedNoteEntry:

    def _find_card_at_ord(self, ord: int):
        cards = self.note.cards()
        for card in cards:
            if card.ord == ord: return card
        raise ValueError(f'Card with ord {ord} does not exist in cached entry for note {self.note.id}.')

    def get_render(self, idx: int, ord: int = 0) -> TemplateRenderOutput:
        note = Note(col=self.note.col, id=self.note.id)
        note.fields[0] = self.texts[idx]
        return note.ephemeral_card(
            ord=ord,
            custom_note_type=note.note_type(),
            custom_template=self._find_card_at_ord(ord).template()
        ).render_output()

    def __init__(self, note: Note, texts: List[str]) -> None:
        self.note = note
        self.texts = texts
        self.last_renders = {}
        self.reps = {}
        self.last_overall_render = None

    def __str__(self):
        return (f'[Cached note {self.note.id}, texts ({len(self.texts)} total): {self.texts}, reps: {self.reps}, last renders: {self.last_renders}, last overall render: {self.last_overall_render}]')

# Keypress event that will be used for removing faulty revisions of a card.
class KeyPressCacheClearFilter(QObject):
    def eventFilter(self, obj: object, event: QEvent):
        if event.type() == QEvent.Type.KeyPress:
            key_combination = event.keyCombination()
            pressed_key = QKeySequence(key_combination).toString()
            if pressed_key == config.settings.shortcut_clear_current_card:
                curr_card = mw.reviewer.card
                if curr_card is not None and curr_card.note().id in config.data.keys():
                    clear_parent_note_of_card_from_cache(curr_card)
                else:
                    tooltip('No note to clear from dynamic cache.')
                # Fix bug: hitting any cache clear keys should trigger a redraw in case card isn't drawing right
                if mw.reviewer.card is not None:
                    mw.reviewer._redraw_current_card()
                return True
            elif pressed_key == config.settings.shortcut_clear_all_cards:
                clear_cache()
                # Fix bug: hitting any cache clear keys should trigger a redraw in case card isn't drawing right
                if mw.reviewer.card is not None:
                    mw.reviewer._redraw_current_card()
                return True
            elif pressed_key == config.settings.shortcut_pause:
                config.pause = not config.pause
                if config.pause:
                    tooltip('Dynamic card generation paused; will resume on Anki restart or unpause. '
                            'Existing dynamic cards will still show.')
                else:
                    tooltip('Dynamic card generation unpaused.')
            elif pressed_key == config.settings.shortcut_include_exclude and mw.reviewer:
                _, add_remove_fn = inject_include_exclude_option(mw.reviewer, None)
                add_remove_fn()
            elif pressed_key == config.settings.shortcut_exclude_deck and mw.reviewer:
                inject_deck_include_exclude_option(mw.reviewer, None)

        return super().eventFilter(obj, event)

def poll_cached_note_for_card(card: Card) -> CachedNoteEntry:
    note = card.note()
    if note.id in config.data.keys():
        if config.debug: print(f'Cached note entry exists for note {note.id}.')
        cne = config.data[note.id]
        if card.ord not in config.data[note.id].reps.keys():
            if config.debug: print(f'Added rep information for ord {card.ord} to cached note {note.id}.')
            cne.reps[card.ord] = card.reps
        if card.ord not in config.data[note.id].last_renders.keys():
            if config.debug: print(f'Added last render information for ord {card.ord} to cached note {note.id}.')
            cne.last_renders[card.ord] = 0
    else:
        cached_note = get_all_by_id(note.id)
        if cached_note:
            if config.debug:
                print(f'Cached note entry for note {note.id} exists in the dynamic database, retrieving it.')
            texts, last_renders = cached_note
            cne = CachedNoteEntry(note=note, texts=texts)
            cne.last_renders = last_renders
            if card.ord not in cne.last_renders.keys():
                if config.debug: print(f'Added rep information for ord {card.ord} to cached note {note.id}.')
                cne.last_renders[card.ord] = 0
            cne.reps[card.ord] = card.reps
            config.data[note.id] = cne
        else:
            if config.debug:
                print(f'Cached note entry for note id {note.id} does not exist; creating a new one.')
            cne = CachedNoteEntry(note=note, texts=[note.fields[0]])
            cne.last_renders[card.ord] = 0
            cne.reps[card.ord] = card.reps
            config.data[note.id] = cne
            set_all_by_id(id_val=note.id, strings=[note.fields[0]], last_renders=cne.last_renders) # Create a new entry in the database with the current text.
    if config.debug: print(f'Retrieved cached note entry {cne}.')
    return cne

def update_cached_note_for_card(card: Card,
                                reps: Optional[int] = None,
                                last_used_render: Optional[int] = None,
                                new_text: Optional[str] = None) -> CachedNoteEntry:
    
    # Set card intrinsic props.
    cne = poll_cached_note_for_card(card)

    if reps is not None:
        # cce id should match card id already.
        cne.reps[card.ord] = reps
        if config.debug: print(f'Updated reps for note {cne.note.id}, ord {card.ord}:', str(cne))
    if new_text is not None:
        cne.texts += [new_text]
        set_all_by_id(id_val=cne.note.id,
                      strings=cne.texts,
                      last_renders=cne.last_renders)
        if config.debug: print(f'Added render for note {cne.note.id}, ord {card.ord}:', str(cne))
    if last_used_render is not None:
        assert last_used_render >= 0 and last_used_render < len(cne.texts)
        cne.last_renders[card.ord] = last_used_render
        set_last_renders_by_id(id_val=cne.note.id, last_renders=cne.last_renders)
        if config.debug: print(f'Updated last used render for note {cne.note.id}, ord {card.ord}:', str(cne))

    config.data[cne.note.id] = cne
    return cne

def create_new_dynamic_wording(note: Note, ord: Optional[int] = None, existing_texts: Optional[List[str]] = None):
    # print('Making a new cached render for card ' + str(card.id))
    # print('API KEY: ' + api_key)
    if config.debug: print(f'Creating new dynamic wording for note {note.id} using model \'{config.settings.model}\'')
    
    new_text = reword_note(note, ord=ord, existing_texts=existing_texts)
    if config.debug:
        if new_text is not None: print(f'Successfully created new dynamic wording for note {note.id} using model \'{config.settings.model}\'')
        else: print(f'Unsuccessfully attempted new dynamic wording for note {note.id} using model \'{config.settings.model}\'')
    return new_text

# Clear cache, either entirely or for a specific note (possibly associated with a card).
def clear_parent_note_of_card_from_cache(card: Card, indicate_error: bool = False):
    if card is not None:
        clear_note_from_cache(note=card.note(), indicate_error=indicate_error)
        
def clear_note_from_cache(note: Note, indicate_error: bool = False):
    if note is not None and note.id in config.data.keys():
        del config.data[note.id]
        clear_all_by_id(note.id)
        if indicate_error:
            tooltip(f'Due to an error (likely problem with dynamic cache), cleared dynamic cache for cards associated with note {note.id}.')
        else:
            tooltip(f'Cleared dynamic cache for cards associated with note {note.id}.')

def clear_cache():
    config.data = {}
    clear_dynamic_db()
    tooltip('Cleared dynamic cache.')

# No need to redraw the card since that will be done anyway when the editor closes
# Only clear cache when editing new cards (only ADD_CARDS, EDIT_CURRENT, and BROWSER modes exist,
# see Editor class)
def clear_cache_on_editor_load_note(e: Editor):
    if e.editorMode == EditorMode.EDIT_CURRENT:
        clear_note_from_cache(e.note)
    # if mw.reviewer.card is not None:
    #     mw.reviewer._redraw_current_card()

# Find all cloze matches in a cloze card.
def get_all_cloze_tags(text: str) -> list[str]:
    return re.findall(r'{{c\d+::.*?}}', text)

# Ensure all cloze deletions are intact and valid.
def validate_cloze(reworded: str, original: str) -> bool:
    # 1. Ensure all unique cloze tags from original are present in reworded
    original_tags = set(get_all_cloze_tags(original))
    reworded_tags = set(get_all_cloze_tags(reworded))
    
    if not original_tags.issubset(reworded_tags):
        return False
        
    # 2. Check for balanced braces
    if reworded.count("{{") != reworded.count("}}"):
        return False
        
    # 3. Check for unclosed tags at the end
    if reworded.strip().endswith("{{") or "{{" in reworded.strip()[-3:]:
         return False
         
    # 4. Length check: if it's significantly shorter than the original while having multiple clozes,
    # it's likely truncated.
    if len(reworded) < (len(original) * 0.4) and len(original_tags) > 1:
        return False
         
    return True

def reword_note(note: Note, ord: Optional[int] = None, num_retries: int = config.settings.num_retries, reason: Optional[str] = None, existing_texts: Optional[List[str]] = None) -> str:

    # Extract relevant properties from the card.
    curr_qtext = reworded_qtext = note.fields[0]
    curr_note_type = note.note_type()['name']
    
    # Extract all unique cloze tags to create a required sequence (if enabled)
    tag_order_instruction = ""
    if config.settings.shuffle_clozes:
        cloze_tags = re.findall(r'{{c\d+::.*?}}', curr_qtext)
        if len(set(cloze_tags)) > 1:
            # Shuffle the unique clozes to create a target sequence
            shuffled_tags = list(cloze_tags)
            shuffle(shuffled_tags)
            variants_str = " -> ".join(shuffled_tags)
            tag_order_instruction = f"\n\nREQUIRED CLOZE SEQUENCE:\n{variants_str}"

    # Construct the prompt with existing variants to avoid duplicates
    prompt_text = curr_qtext
    avoid_instruction = ""
    if existing_texts and len(existing_texts) > 0:
        variants_to_avoid = "\n".join([f"- {text}" for text in set(existing_texts)])
        avoid_instruction = f"\n\nDO NOT generate anything similar to these existing variants:\n{variants_to_avoid}"
    
    prompt_text = f"Original Card Text:\n{curr_qtext}{tag_order_instruction}{avoid_instruction}\n\nTask: Generate exactly ONE new, structurally distinct variation of the Original Card Text following all instructions."

    # If we've run out of tries, then give up.
    if num_retries < 0:
        tooltip(f'Could not properly reword note {note.id} using platform {config.settings.platform_index} (reason: {reason}). Please try again.') 
        return None

    try:
        if config.settings.platform_index == 0:
            reworded_qtext = reword_text_mistral(prompt_text)
        elif config.settings.platform_index == 1:
            reworded_qtext = reword_text_gemini(prompt_text)
        else:
            raise RuntimeError(f'Unknown platform index {config.settings.platform_index} for rewording note {note.id}.')
        
        # Safety Valve: allow model to opt-out if the card is too technical/specific
        if "[SKIP_REWORD]" in reworded_qtext:
            return None

        # Deduplication check: if the new text is a duplicate, retry.
        if existing_texts and reworded_qtext.strip() in [t.strip() for t in existing_texts]:
            time.sleep(config.settings.retry_delay_seconds)
            return reword_note(note, num_retries - 1, reason='Duplicate variant generated', existing_texts=existing_texts)

    except RuntimeError as e:
        time.sleep(config.settings.retry_delay_seconds) # avoid rate limit ceiling
        return reword_note(note, num_retries - 1, reason=str(e), existing_texts=existing_texts)
    
    # If the note is cloze-adjacent, then validate it. If valid, return the note.
    # If not cloze-adjacent, skip this validation process and just return the note.
    # BUG: This ONLY goes by name. There must be a better way to validate it.
    if 'cloze' in curr_note_type.lower() and not validate_cloze(reworded_qtext, curr_qtext):
        time.sleep(config.settings.retry_delay_seconds) # avoid rate limit ceiling
        return reword_note(note, num_retries - 1, reason='Cloze validation failed', existing_texts=existing_texts)
    return reworded_qtext
        
def reword_text_mistral(curr_qtext: str) -> str: 
       
    # Try to reword the card using Mistral.
    try:
        chat_response = requests.post(url="https://api.mistral.ai/v1/chat/completions",
                                      headers={'Content-Type': 'application/json',
                                              'Accept': 'application/json',
                                              'Authorization': 'Bearer ' + config.settings.api_key},
                                      data=json.dumps({'model': config.settings.model,
                                                       'messages': [
                                                           {'role': 'system', 'content': config.settings.context},
                                                           {'role': 'user', 'content': curr_qtext}
                                                       ]}),
                                      timeout=15)
        if not (chat_response.status_code >= 200 and chat_response.status_code < 300):
            raise requests.exceptions.RequestException(chat_response.json().get('message', f'Unspecified error ({chat_response.status_code})'))
        return chat_response.json()['choices'][0]['message']['content']
    except Exception as e:
        raise RuntimeError(f'Error loading \'{config.settings.model}\' for dynamic Anki cards: ' + str(e))

def reword_text_gemini(curr_qtext: str) -> str: 
       
    # Try to reword the card using Gemini.
    try:
        chat_response = requests.post(
            url=f"https://generativelanguage.googleapis.com/v1beta/models/{config.settings.model}:generateContent?key={config.settings.api_key}",
            headers={
                'Content-Type': 'application/json'
            },
            data=json.dumps({
                "system_instruction": {
                    "parts": [
                        {
                            "text": config.settings.context
                        }
                    ]
                },
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": curr_qtext
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "topP": 0.95,
                    "topK": 40,
                    "maxOutputTokens": 1024,
                }
            }),
            timeout=30
        )
        
        if not (chat_response.status_code >= 200 and chat_response.status_code < 300):
            raise requests.exceptions.RequestException(chat_response.json().get('message', f'Unspecified error ({chat_response.status_code})'))
            
        return chat_response.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        raise RuntimeError(f'Error loading \'{config.settings.model}\' for dynamic Anki cards: ' + str(e))
                          # 'You might need to check your settings to ensure correct model name, API keys, and usage limits. '
                          # 'If this continues, disable this add-on to stop these messages.')

# Based on the template used in the note, generate a rewording and rerender the front cloze.
def inject_rewording_on_question(text: str, card: Card, kind: str) -> str:

    global q # Make it explicit.

    # Although this entire hook is called each time, we only want to modify the ephemeral card when we view
    # the question side. Then, we can simply view the answer side of the modified card while it's stored
    # in the mw.reviewer.card slot, even though we call the hook again.
    if kind == 'reviewQuestion':
        
        # Using the NOTE template, create an ephermeral card referring to the given note.
        # The consequence is that we can inject whatever wording we want, the wording will stay consistent,
        # and then the scheduling will be assigned to the stored card in memory.

        # Poll the cached card.
        # This will set the number of reps of any new card to 0.
        cne = poll_cached_note_for_card(card)
        # print('Last used render: %d of %d (at that time)' % (cce.last_used_render + 1, len(cce.renders)))

        try:
            # Check for exclusions (Note Type or Deck)
            curr_note_type = card.note().note_type()['name']
            curr_deck_name = mw.col.decks.get(card.did)['name']
            
            # Check if current deck OR any parent deck is excluded
            is_deck_excluded = any(curr_deck_name == excluded or curr_deck_name.startswith(excluded + "::") 
                                   for excluded in config.settings.exclude_decks)

            # Proactively queue a task if we don't have enough renders yet
            if (not config.pause and len(cne.texts) < config.settings.max_renders and 
                curr_note_type not in config.settings.exclude_note_types and
                not is_deck_excluded):
                if config.debug: print(f'Creating new render for note {cne.note.id}, current cache: ', str(cne))
                q.add_render_task(card=card)

            # If the rep state hasn't changed since last time, then use the last render. Don't change.
            if cne.reps[card.ord] <= card.reps:
                # Try to select a render that is different from the previous one (or just select the only one available)
                if config.debug:
                    print('Card to inject:', card, f'(id {card.id}, ord {card.ord})')
                    print('CNE to use:', cne)
                last_render_to_avoid = cne.last_overall_render if cne.last_overall_render is not None else cne.last_renders[card.ord]
                choices = set(range(len(cne.texts)))
                choices = list(choices.difference(set([last_render_to_avoid]))) if len(choices) > 1 else list(choices)           
                cne.last_renders[card.ord] = choice(choices)

                # Update the cache reps.
                # BUG: Will freeze card updates if it is undone multiple times in one "undo chain."
                # Eventually this will be fixed, or the user can clear the cache on a card manually.
                # This issue should not occur in everyday usage though.
                update_cached_note_for_card(card, reps=cne.reps[card.ord]+1, last_used_render=cne.last_renders[card.ord])

            # Set the current render. If there is an error, clear the card from cache and try again.
            curr_render = cne.get_render(idx=cne.last_renders[card.ord], ord=card.ord)
            cne.last_overall_render = cne.last_renders[card.ord]
            card.set_render_output(curr_render)
            if config.debug:
                print(f'Using render {cne.last_renders[card.ord]} (zero-indexed) for note {cne.note.id}, ord {card.ord}')
                print(f'Cached reps: {cne.reps[card.ord]}')
                print(f'True (card) reps: {card.reps}')
        except (KeyError, TypeError, IndexError) as e:
            if config.debug: print(f'Error on injecting wording for card {card.id}:', e)
            clear_parent_note_of_card_from_cache(card, indicate_error=True)

        # print(cce)
        return card.question()

    # Again, we don't need to do any kind of modification to the ephemeral card that's in mw.reviewer.card 
    # as long as the card is visible.
    elif kind == 'reviewAnswer':
        return card.answer()
    
    # If there is any unexpected value of kind, just display what's there.
    return text

# Inject context menu option to add or remove current card type.

def inject_include_exclude_option(r: Reviewer, m: QMenu) -> Tuple[QAction, Callable]:
    # See L1026 in reviewer.py
    curr_note_type = r.card.note().note_type()['name']
    if curr_note_type not in config.settings.exclude_note_types:
        def exclude_curr_note_type():
            # Assigning explicitly so the setting change gets written to disk since we are calling __setattr__
            config.settings.exclude_note_types = config.settings.exclude_note_types + [curr_note_type]
            tooltip(f'Excluding note type \'{curr_note_type}\' from dynamic card generation.')
        phrase = 'Exclude current note type'
        fn = exclude_curr_note_type
    else:
        def include_curr_note_type():
            config.settings.exclude_note_types = [x for x in config.settings.exclude_note_types if x != curr_note_type]
            tooltip(f'Including note type \'{curr_note_type}\' in dynamic card generation.')
        phrase = 'Include current note type'
        fn = include_curr_note_type
    a = None
    if m:
        #m.addSeparator()
        a = m.addAction(phrase)
        a.setShortcut(config.settings.shortcut_include_exclude)
        qconnect(a.triggered, fn)
    return a, fn

def inject_deck_include_exclude_option(r: Reviewer, m: QMenu) -> None:
    curr_deck_name = None
    
    # Strategy 1: If in reviewer, get deck from current card
    if r and r.card:
        curr_deck_name = mw.col.decks.get(r.card.did)['name']
    
    # Strategy 2: If not in reviewer, check if we are in the Deck Overview screen
    if not curr_deck_name:
        try:
            # mw.col.decks.current() returns the deck currently selected in the UI
            curr_deck_name = mw.col.decks.current()['name']
        except:
            pass

    if not curr_deck_name:
        if not m: tooltip("No deck selected to exclude.")
        return
    
    def toggle_deck_exclusion():
        if curr_deck_name not in config.settings.exclude_decks:
            config.settings.exclude_decks = config.settings.exclude_decks + [curr_deck_name]
            tooltip(f'Excluding deck \'{curr_deck_name}\' from dynamic card generation.')
        else:
            config.settings.exclude_decks = [x for x in config.settings.exclude_decks if x != curr_deck_name]
            tooltip(f'Including deck \'{curr_deck_name}\' in dynamic card generation.')
    
    if m:
        phrase = 'Exclude current deck' if curr_deck_name not in config.settings.exclude_decks else 'Include current deck'
        a = m.addAction(phrase)
        qconnect(a.triggered, toggle_deck_exclusion)
    else:
        toggle_deck_exclusion()

def inject_clear_current_card_option(r: Reviewer, m: QMenu) -> None:
    a = m.addAction('Clear current card from cache')
    a.setShortcut(config.settings.shortcut_clear_current_card)
    if mw.reviewer:
        def fn(): clear_parent_note_of_card_from_cache(mw.reviewer.card)
        qconnect(a.triggered, fn)

def inject_clear_all_cards_option(r: Reviewer, m: QMenu) -> None:
    a = m.addAction('Clear all cards from cache')
    a.setShortcut(config.settings.shortcut_clear_all_cards)
    def fn(): clear_cache()
    qconnect(a.triggered, fn)
    
def inject_pause_generation_option(r: Reviewer, m: QMenu) -> None:
    a = m.addAction('Pause dynamic card generation' if not config.pause else 'Resume dynamic card generation')
    a.setShortcut(config.settings.shortcut_pause)
    def fn(): config.pause = not config.pause
    qconnect(a.triggered, fn)

def insert_separator(r: Reviewer, m: QMenu) -> None:
    m.addSeparator()

# Start the dynamic database.
setup_dynamic_db()

# Start the asynchronous queue and have it start/stop appropriately.
# Using the card showing as a proxy for the start of a review session.
q = RewordingWorkerQueue()
gui_hooks.card_will_show.append(lambda *args: q.start())
gui_hooks.reviewer_will_end.append(lambda *args: q.stop())

# Add hook using the new method
# Also clear the reviewer once the review session is over
# Also clear cards from the cache when they are to be edited
gui_hooks.card_will_show.append(inject_rewording_on_question)
gui_hooks.editor_did_load_note.append(clear_cache_on_editor_load_note)
gui_hooks.reviewer_will_show_context_menu.append(insert_separator)
gui_hooks.reviewer_will_show_context_menu.append(inject_pause_generation_option)
gui_hooks.reviewer_will_show_context_menu.append(inject_include_exclude_option)
gui_hooks.reviewer_will_show_context_menu.append(inject_deck_include_exclude_option)
gui_hooks.reviewer_will_show_context_menu.append(inject_clear_current_card_option)
gui_hooks.reviewer_will_show_context_menu.append(inject_clear_all_cards_option)
if config.settings.clear_cache_on_reviewer_end:
    gui_hooks.reviewer_will_end.append(clear_cache)

# Attach the remove revision tool.
mw.installEventFilter(KeyPressCacheClearFilter(mw))

# Make the welcome announcement if warranted.
if config.settings.show_modal:
    dlg = WelcomeDialog(config.settings.show_modal)
    def set_show_modal():
        config.settings.show_modal = dlg.form.checkBox.isChecked()
    qconnect(dlg.rejected, set_show_modal)
    dlg.setModal(True)
    dlg.show()

# Have the dialog and the settings menu in separate classes.
sdlg = SettingsDialog(config.settings)
def update_config_settings():
    config.settings.shortcut_clear_current_card = sdlg.form.keySequenceEdit.keySequence().toString()
    config.settings.shortcut_clear_all_cards = sdlg.form.keySequenceEdit_2.keySequence().toString()
    config.settings.shortcut_include_exclude = sdlg.form.keySequenceEdit_3.keySequence().toString()
    config.settings.shortcut_exclude_deck = sdlg.form.keySequenceEdit_5.keySequence().toString()
    config.settings.shortcut_pause = sdlg.form.keySequenceEdit_4.keySequence().toString()
    config.settings.api_key = sdlg.form.APIKeyLineEdit.text()
    config.settings.model = sdlg.form.modelLineEdit.text()
    config.settings.context = sdlg.form.textEdit.toPlainText()
    config.settings.clear_cache_on_reviewer_end = sdlg.form.checkBox.isChecked()
    config.settings.shuffle_clozes = sdlg.form.shuffleDeletionsCheckBox.isChecked()
    config.settings.exclude_note_types = [sdlg.form.listWidget.item(i).text() for i in range(sdlg.form.listWidget.count())]
    config.settings.exclude_decks = [sdlg.form.listWidgetDecks.item(i).text() for i in range(sdlg.form.listWidgetDecks.count())]
    config.settings.platform_index = sdlg.form.platformSelect.currentIndex()

    # Handle max render input
    try:
        val = int(sdlg.form.maxRendersLineEdit.text())
        assert val > 0
        config.settings.max_renders = val
    except ValueError or AssertionError:
        tooltip(f'Invalid new value \'{sdlg.form.maxRendersLineEdit.text()}\' for max renders; reverting to old value.')

    # Handle num retries input
    try:
        val = int(sdlg.form.retryCountLineEdit.text())
        assert val > 0
        config.settings.num_retries = val
    except ValueError or AssertionError:
        tooltip(f'Invalid new value \'{sdlg.form.retryCountLineEdit.text()}\' for retry count; reverting to old value.')

    # Handle retry delay input
    try:
        val = float(sdlg.form.retryDelayLineEdit.text())
        assert val >= 0
        config.settings.retry_delay_seconds = val
    except ValueError or AssertionError:
        tooltip(f'Invalid new value \'{sdlg.form.retryDelayLineEdit.text()}\' for retry delay; reverting to old value.')
    
    # Handle reviewer ending callback
    # As per internal gui_hooks code, no exception thrown if object to remove not found
    gui_hooks.reviewer_will_end.remove(clear_cache)
    if config.settings.clear_cache_on_reviewer_end:
        gui_hooks.reviewer_will_end.append(clear_cache)

sdlg.setModal(True)
sdlg.accepted.connect(update_config_settings)
config_option = QAction("Dynamic Cards", mw)
config_option.triggered.connect(sdlg.show)
mw.form.menuTools.addAction(config_option)