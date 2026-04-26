# Dynamic Cards

Hate when you memorize the wording of an Anki card rather than the card's
content? Introducing the **Dynamic Cards** plugin, a small plugin
that allows Anki to ping LLMs to slightly change the content of your cards
each time you review them.

This extension currently relies upon either **Mistral AI** or **Google Gemini** for generating and
serving new content. Please keep usage agreements and rate limits in mind.

> [!WARNING]
> This has only been tested on a Windows 11 machine and a macOS machine with PyQt6. It is possible
> that UI windows for this extension look subpar on other systems. If this
> plugin is indeed broken for other systems, please raise an issue on GitHub
> (see **Bugs and other issues** below).

## Download and installation

Head over to the [AnkiWeb page](https://ankiweb.net/shared/info/1902186394)
for installation instructions. You should be able to install the plugin
through the *Add-ons > Get Add-ons* menu in Anki itself.

## Usage

### First-time setup

There are some critical steps that need to be done before this extension may
be used.

1. **Create an API key:** Create a free account at
   [Mistral AI](https://console.mistral.ai/) or [Google AI Studio (Gemini)](https://aistudio.google.com/)
   to get started. Follow the appropriate instructions to create a **free** API key.
2. **Paste the API key into the extension.** Navigate to the *Tools > Dynamic
   Cards* window in Anki. Then, paste your API key into the *API key*
   field. Make sure the *AI Platform* dropdown is set to the appropriate service.
3. **Validate your Model:** Select the platform, enter an appropriate model (e.g., `gemini-3-pro-preview` or `mistral-large-latest`) and click **Validate Model** to ensure your API key and model name are correct.
4. That's it! **The plugin should begin working immediately without further
   action; changes will initially be subtle. Enjoy your dynamic cards!**

> [!IMPORTANT]
> If you see a tooltip (pop-up) saying 'Validation failed', there is a problem with
> your API key or the model you selected. Please try again or raise an issue on GitHub.

> [!WARNING]
> This extension might not work with certain types of cards, but should work
> with Basic, Cloze, and other note types that have the question text in their
> first field. This has been tested on AnKing and Miledown decks, for instance.

### Normal operation

The workflow of the extension is quite simple. Each time you review a card, a
new "rewording" is generated in the background for next time (until the maximum
number of rewordings are reached). The extension therefore operates as follows:

* The first time you see a card, you will see the original wording.
* A background task will request a reworded variant from the LLM.
* Upon subsequent reviews of a card, one of any of the previous rewordings
  (or a new rewording) may be selected for display.

### The Settings menu

The Settings menu is the main control center of this plugin. It is accessible
via *Tools > Dynamic Cards.*

#### Keyboard Shortcuts
* **Clear current card from cache:** Reset the wording of the specific card currently being viewed.
* **Clear all cards from cache:** Clear all dynamically generated text from the database.
* **Exclude/include current note type:** Stop dynamic generation for the note type of the current card.
* **Exclude/include current deck:** Stop dynamic generation for the entire deck of the current card (includes sub-decks).
* **Pause dynamic card generation:** Temporarily pause generation for all cards.

#### LLM Functionality
* **AI Platform:** The platform hosting the model you're using (Mistral or Gemini).
* **API key:** The API key to allow access to your platform's API.
* **Model:** The model name to use (e.g., `gemini-3-pro-preview`).
* **Validate Model:** A button to test your API key and model combination.
* **Max renders:** The maximum number of alternative "versions" of a card to hold. Default is `3`.

#### Prompt Configuration
* **Load Template:** Choose between pre-built prompts, like the strict "SuperMemo" template or the "Original" subtle rewording template.
* **Require LLM to shuffle the order of cloze deletions:** If enabled, the extension will randomly shuffle your `{{c1::...}}` tags and force the AI to rebuild the sentence around the new order, breaking visual patterns.
* **Context:** Instructions fed to the LLM to generate rewordings. You can fully customize this.
* **Retry count & delay:** Configures how many times the extension will retry generating a card if validation fails, and how long to wait between attempts to avoid rate limits.

#### Exclusions
* **Clear cache on review end:** Automatically clear all generated text when closing the reviewer.
* **Excluded Note Types / Decks:** Lists of all excluded types and decks. Double-click any item to remove it from the exclusion list.

## Technical Cards & Safety Valve

If you use the **SuperMemo** prompt template, the AI is instructed with a **Safety Valve**: if a card contains technical code, CLI commands, or formulas where rewording would break accuracy, the AI will silently decline to reword it, ensuring your technical cards remain 100% accurate.

## Bugs and other issues

Found a bug? Please raise an issue so I can see it! Contributions are also
welcome. Note that manual layout modifications were made to `ui/settings.py` to support the scroll area; compiling from the `.ui` file may overwrite these changes.