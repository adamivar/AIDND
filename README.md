# Agentic D&D Engine

A Pygame-based text RPG where Claude AI acts as your Dungeon Master. Describe actions, roll dice, manage your party, and explore a fully AI-generated world.

![Python](https://img.shields.io/badge/Python-3.12-blue) ![Pygame](https://img.shields.io/badge/Pygame-required-green) ![Claude](https://img.shields.io/badge/Powered%20by-Claude%20AI-orange)

---

## Requirements

- Python 3.12
- An [Anthropic API key](https://console.anthropic.com/)

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/adamivar/AIDND.git
cd AIDND
```

### 2. Install dependencies

If you have Python 3.12:

```bash
pip install pygame anthropic python-dotenv wonderwords
```

If you installed Python via the Microsoft Store or have Python 3.14, use the `py` launcher:

```bash
py install 3.12
py -3.12 -m pip install pygame anthropic python-dotenv wonderwords
```

### 3. Add your API key

Copy the template and fill in your Anthropic API key:

```bash
cp .env.template .env
```

Then open `.env` and replace `your_api_key_here` with your actual key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Get a key at [https://console.anthropic.com/](https://console.anthropic.com/) — sign up, go to **API Keys**, and create a new key. The `.env` file is gitignored and will never be committed.

> You can get a key from [https://console.anthropic.com/](https://console.anthropic.com/)

### 4. Run the game

Standard:

```bash
python main.py
```

If using `py` launcher with 3.12:

```bash
py -3.12 main.py
```

---

## How to Play

### Adventure Setup Screen

When the game launches you'll see a configuration screen with these fields:

| Field   | Description                                      |
|---------|--------------------------------------------------|
| Genre   | The genre of your adventure (e.g. Dark Fantasy)  |
| Tone    | The mood/atmosphere (e.g. Grim, Whimsical)       |
| Who     | A character or archetype central to the story    |
| What    | A key object in the scene                        |
| When    | A time period or moment                          |
| Where   | The location/setting                             |
| Why     | Your motivation or situation                     |

- **Roll Dice** — randomizes all fields for a surprise adventure
- **Start Game** — generates your world and begins the session (all fields are optional)

### Playing

Type your action in the input box at the bottom and press **Enter** to submit. Claude will narrate the result, use tools to update your stats, and sometimes call for a dice roll.

When prompted to roll, **click the hexagonal die** on the right side of the screen.

### Controls

| Key / Action         | Effect                              |
|----------------------|-------------------------------------|
| `Enter`              | Submit action / skip narration      |
| `Ctrl + S`           | Save game                           |
| `Ctrl + L`           | Load game                           |
| `F11`                | Toggle fullscreen                   |
| `F12`                | Toggle debug view                   |
| `↑ / ↓` or scroll   | Scroll the chronicle                |
| Click the die        | Roll dice when prompted             |

### Game Mechanics

- **HP** — you have 5 hearts. Reach 0 and it's game over (load a save to continue)
- **Party** — 3 AI companions travel with you, each with their own personality, motives, and flaws
- **Abilities** — 3 passive soft skills + 3 active abilities with cooldowns
- **Inventory** — items are tracked strictly; you can only use what you carry
- **Save/Load** — saves to `savegame.json` in the project folder

---

## Project Structure

```
AIDND/
├── main.py         # Game loop, AI calls, tool handling
├── config.py       # All constants and settings
├── prompts.py      # AI prompts, tool definitions, world-seed logic
├── ui.py           # Pygame rendering
├── savegame.json   # Auto-created on first save
└── .env            # Your API key (create this yourself)
```

---

## Notes

- The game uses `claude-haiku-4-5` by default and automatically falls back to Sonnet or Opus if the model is overloaded
- API usage will count against your Anthropic account — each turn makes at least one API call
- The `.env` file is gitignored and will never be committed
- `pygame 2.6.1` does not support Python 3.14 on Windows — use Python 3.12 instead
