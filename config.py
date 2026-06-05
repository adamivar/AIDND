"""
config.py – Single source of truth for all constants and magic numbers.
"""

# ── Window ────────────────────────────────────────────────────────────────────
WINDOW_SIZE = (1200, 680)
WINDOW_TITLE = "Agentic D&D Engine v2.1"
TARGET_FPS = 60

# ── AI / API ──────────────────────────────────────────────────────────────────
MODEL_NAME = "claude-haiku-4-5-20251001"
FALLBACK_MODELS = [
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
    "claude-opus-4-6",
]
MAX_TOOL_ITERATIONS = 8
API_MAX_RETRIES = 3
RETRYABLE_STATUS = {429, 500, 502, 503, 529}
RETRY_BASE_WAIT = 1.5   # seconds (multiplied by 2^attempt)
RETRY_MAX_WAIT = 8.0    # seconds cap per retry
RETRY_JITTER = 0.75     # random jitter ceiling added to wait

# ── Persistence ───────────────────────────────────────────────────────────────
SAVE_PATH = "savegame.json"

# ── Game Logic ────────────────────────────────────────────────────────────────
HISTORY_WINDOW = 24          # number of recent messages kept verbatim per request
SUMMARY_KEEP_VERBATIM = HISTORY_WINDOW  # recent messages always sent raw (rest summarized)
SUMMARY_BATCH = 8            # summarize only once this many messages have aged out
SUMMARY_MAX_TOKENS = 600     # max tokens for the rolling "story so far" summary
SEED_MAX_ATTEMPTS = 6        # retries for world-seed generation
SEED_WAIT_BASE = 1.5         # seconds between seed-gen retries
SEED_WAIT_MAX = 5.0          # max wait between seed-gen retries

STARTING_HP = 5
PARTY_HP_MAX = 5
STARTING_INVENTORY = {"Rations": 2}
DEFAULT_ITEM_DESCRIPTION = "A common item."
RATIONS_DESCRIPTION = "Standard travel fare."

INPUT_MAX_LENGTH = 200       # max characters in the player's input box (supports 4 wrapped lines)
SETUP_FIELD_MAX_LENGTH = 50  # max characters per short setup field (Genre / Tone)
PREMISE_MAX_LENGTH = 300     # max characters in the Premise text area
MEANINGFUL_INPUT_MIN_ALNUM = 2  # minimum alphanumeric chars to count as real input

MBTI_TYPES = [
    "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
]

ALIGNMENTS = [
    "Lawful Good",    "Neutral Good",  "Chaotic Good",
    "Lawful Neutral", "True Neutral",  "Chaotic Neutral",
    "Lawful Evil",    "Neutral Evil",  "Chaotic Evil",
]

LOVE_LANGUAGES = [
    "Words of Affirmation",
    "Acts of Service",
    "Receiving Gifts",
    "Quality Time",
    "Physical Touch",
]

# Languages whose phonetics/orthography are commonly drawn on for D&D names.
# Used to seed AI party-member name generation with a consistent cultural flavour.
DND_NAME_LANGUAGES = [
    "Welsh",
    "Old Norse",
    "Finnish",
    "Latin",
    "Ancient Greek",
    "Arabic",
    "Old English",
    "Irish Gaelic",
    "Sanskrit",
    "Japanese",
    "Nahuatl",
    "Swahili",
    "Hebrew",
    "Persian",
    "Polish",
    "Icelandic",
    "Romanian",
    "Turkish",
    "Elvish (Tolkien-inspired)",
    "Draconic (high-fantasy)",
]

# ── Party & Ability Counts ────────────────────────────────────────────────────
PARTY_SIZE = 3           # number of companion party members
NUM_SOFT_ABILITIES = 3   # passive / soft-skill ability slots
NUM_ACTIVE_ABILITIES = 3 # cooldown-gated active ability slots

# Hint flavours cycled when generating ability seed prompts.
# Add more entries here if you raise NUM_SOFT_ABILITIES / NUM_ACTIVE_ABILITIES.
SOFT_ABILITY_FLAVORS = [
    "broad soft skill or physical ability",
    "broad soft skill or agility ability",
    "broad soft skill or social ability",
]
ACTIVE_ABILITY_FLAVORS = [
    "powerful active technique or spell",
    "powerful offensive technique or spell",
    "powerful utility technique or spell",
]

# ── Streaming / Dice Animation ────────────────────────────────────────────────
STREAMING_CHUNK_SIZE = 3    # characters revealed per frame during streaming
DICE_ROLL_FRAMES = 300      # total frames the dice "rolling" animation lasts
DICE_HOLD_FRAMES = 45       # frames each post-roll state holds (base → mod → done)
DICE_SHAKE_AMPLITUDE = 4    # max pixel shake during roll
CURSOR_BLINK_MS = 500       # ms per half-cycle for text-cursor blink
THINKING_DOT_MS = 400       # ms per dot step in "thinking…" animation
DICE_PULSE_PERIOD_MS = 300  # ms per pulse cycle for the "CLICK TO ROLL" prompt

# ── Fonts ─────────────────────────────────────────────────────────────────────
FONT_MONO = "consolas"
FONT_EMOJI = "segoe ui emoji, apple color emoji, symbol, arial"
FONT_DISPLAY = "impact"
FONT_SIZE_NORMAL = 14
FONT_SIZE_BOLD = 15
FONT_SIZE_SMALL = 12
FONT_SIZE_HEADER = 13
FONT_SIZE_PARTY = 14
FONT_SIZE_HEARTS = 20
FONT_SIZE_DICE_LARGE = 48
FONT_SIZE_DICE_SMALL = 20

# ── Layout ────────────────────────────────────────────────────────────────────
CHAT_MAX_WIDTH = 610    # pixel width for text wrapping in the chronicle panel
LINE_SPACING = 20       # pixels between rendered text lines
WRAP_CACHE_MAX = 2000   # max entries in the text-wrap LRU cache
DICE_RADIUS = 35        # pixel radius of the hexagonal dice graphic
TOOLTIP_WIDTH = 240     # default pixel width for hover tooltips

# ── Colour Palette ────────────────────────────────────────────────────────────
C_BG_TOP        = (16,  17,  22)
C_BG_BOTTOM     = (10,  10,  14)
C_PANEL         = (24,  26,  33)
C_PANEL_HEADER  = (33,  36,  46)
C_BORDER        = (52,  56,  70)
C_BORDER_SOFT   = (40,  43,  54)
C_TEXT          = (214, 218, 228)
C_TEXT_DIM      = (140, 146, 160)
C_TEXT_FAINT    = (96,  100, 116)

C_HEALTH        = (232, 72,  86)
C_HEALTH_TRACK  = (54,  30,  34)
C_SKILL         = (90,  210, 130)
C_SKILL_TRACK   = (28,  44,  34)
C_SPELL         = (150, 120, 240)
C_PARTY         = (96,  178, 240)
C_INVENTORY     = (235, 196, 92)
C_ACCENT        = (0,   200, 220)
C_FATE          = (240, 70,  150)
C_DEBUG         = (255, 140, 0)

C_OK            = (90,  210, 130)
C_WARN          = (240, 170, 70)
C_DANGER        = (232, 72,  86)

PARTY_COLORS = [
    (242, 166, 90),
    (120, 200, 245),
    (190, 150, 245),
    (130, 220, 160),
    (240, 130, 170),
    (220, 210, 120),
]

