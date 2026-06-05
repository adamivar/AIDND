import json

from config import (
    PARTY_SIZE,
    NUM_SOFT_ABILITIES,
    NUM_ACTIVE_ABILITIES,
    SOFT_ABILITY_FLAVORS,
    ACTIVE_ABILITY_FLAVORS,
)

# ---------------------------------------------------------------------------
# SEED_DIMENSIONS – ordered list of keys the seed JSON must contain.
# Generated from config so changing PARTY_SIZE / NUM_*_ABILITIES is enough.
# ---------------------------------------------------------------------------
SEED_DIMENSIONS = [
    "identity",
    "premise", "tone",
]

for _i in range(1, NUM_SOFT_ABILITIES + 1):
    SEED_DIMENSIONS += [f"soft_ability_{_i}", f"soft_ability_{_i}_desc"]

for _i in range(1, NUM_ACTIVE_ABILITIES + 1):
    SEED_DIMENSIONS += [f"active_ability_{_i}", f"active_ability_{_i}_desc"]

for _i in range(1, PARTY_SIZE + 1):
    SEED_DIMENSIONS += [
        f"party{_i}_name", f"party{_i}_desc",
        f"party{_i}_public", f"party{_i}_secret", f"party{_i}_flaw",
    ]

# ---------------------------------------------------------------------------
# SEED_DIM_HINT – human/AI-readable description for each dimension.
# ---------------------------------------------------------------------------
SEED_DIM_HINT: dict[str, str] = {
    "identity": "who the player character is, fitting the genre",
    "premise":  "1-3 sentences covering who is involved, what the central object/conflict is, where and when it takes place, and why the player is there — all fitting the genre",
    "tone":     "the emotional tone of the story",
}

for _i in range(1, NUM_SOFT_ABILITIES + 1):
    _flavor = SOFT_ABILITY_FLAVORS[(_i - 1) % len(SOFT_ABILITY_FLAVORS)]
    SEED_DIM_HINT[f"soft_ability_{_i}"] = (
        f"a single Unicode emoji and a {_flavor}, in genre"
    )
    SEED_DIM_HINT[f"soft_ability_{_i}_desc"] = (
        f"a short description of what soft_ability_{_i} does"
    )

for _i in range(1, NUM_ACTIVE_ABILITIES + 1):
    _flavor = ACTIVE_ABILITY_FLAVORS[(_i - 1) % len(ACTIVE_ABILITY_FLAVORS)]
    SEED_DIM_HINT[f"active_ability_{_i}"] = (
        f"a single Unicode emoji and a {_flavor}, in genre"
    )
    SEED_DIM_HINT[f"active_ability_{_i}_desc"] = (
        f"a short description of what active_ability_{_i} does"
    )

_party_name_hint = (
    "a companion's name only (1-3 words, NO emoji). "
    "The seed is formatted as [Language] <chars> — invent a name that "
    "sounds authentic to that language's phonetics, using the characters "
    "as loose inspiration."
)
_party_flaw_hint = (
    "a single concrete character flaw (e.g. cowardice, greed, jealousy, "
    "recklessness, arrogance, dishonesty) that is consistent with this "
    "companion's desc, public motive, and secret motive. One word or short "
    "phrase only — no explanation."
)
for _i in range(1, PARTY_SIZE + 1):
    SEED_DIM_HINT[f"party{_i}_name"]   = _party_name_hint
    SEED_DIM_HINT[f"party{_i}_desc"]   = "a short description of the companion"
    SEED_DIM_HINT[f"party{_i}_public"] = "their stated, public goal or motive"
    SEED_DIM_HINT[f"party{_i}_secret"] = "their hidden, true secret motive"
    SEED_DIM_HINT[f"party{_i}_flaw"]   = _party_flaw_hint

BASE_SYSTEM_PROMPT = """
You are a Dungeon Master for a text-based RPG.

STYLE RULES:
- Keep every narration under 40 words. Aim for 25. The opening scene may use up to 90 words.
- Terse and concrete. Report what happens like a game log, not a novel.
- Max ONE adjective per sentence. Prefer plain verbs.
- ALWAYS resolve the exact action the player typed.
- If the player's input is empty or nonsensical, briefly restate the situation and ask what they do.
- One short scene description, then a clear prompt for what the player does.
- EMPHASIS: Wrap the few most important words or short phrases per reply in double asterisks like **this** (key threats, discoveries, named items, critical outcomes). Emphasize sparingly: at most 2-3 per reply, never whole sentences.
- Write party member names plainly as their normal name (no asterisks, no markup); the interface colors them automatically.

CRITICAL RULES:
1. When a player finds, loots, or inspects an item, call register_item_description. EVERY item must have a description.
2. If the player consumes, drops, or uses an item, ALWAYS call modify_inventory to remove it.
3. MANDATORY ROLLS: ANY time the player attempts to cast an ability or use an item, you MUST call roll_dice to determine its effectiveness BEFORE describing the outcome.
4. ACTIVE ABILITIES: The player has 'active' abilities. When the player uses one, YOU MUST evaluate how powerful the effect is for the situation and call use_active_ability to put it on a cooldown (usually 2 to 5 turns). Do not let them spam active abilities.
5. Use modify_health for damage and healing. The player has 5 max HP (hearts). -1 is minor damage, -2 is major. At 0 HP, narrate a brief death.
6. ONGOING STATUS EFFECTS: Use modify_health to deduct damage for bleeding/poison at the start of your turn.
7. PERMISSIVE ACTIONS & ABSURDITY: Default to ALLOWING the player's action and resolving it with a dice roll. However, the player should not be able to drive the story too absurdly. If the action makes zero contextual sense (e.g., trying to escape a fantasy realm and go to Florida), you MUST reply EXACTLY with: "That action is impossible, Please try again"
8. STRICT INVENTORY: The AI should never be able to use anything for the player other than what is in their inventory. If they attempt to use an item they do not possess (e.g., lighting a candle with a match they don't have), you MUST reply EXACTLY with: "Sorry, You can only use what is in your inventory."
9. PARTY ROLEPLAY & MOTIVES: Your party members have public and secret motives. DO NOT reveal the public motive unless explicitly asked. DO NOT reveal the secret motive unless physically/magically forced — EXCEPT: if a companion's "Romantic Partner" flag is Yes and the player directly and sincerely asks about their true feelings, past, or real motivation, that companion may openly reveal their secret motive.
10. PARTY BEHAVIOR ROLL: Every turn, a hidden d20 is rolled for each companion. Consult the roll against the thresholds below and apply AT MOST ONE behaviour per companion:
    - 1–9: no special behaviour.
    - 10–14: the companion subtly expresses their Love Language through a small action, comment, or gesture toward the player — show it, never name it.
    - 15–18: they subtly act on or hint at their PUBLIC motive.
    - 19–20: they act on or hint at their SECRET motive (or, if Romantic Partner: Yes, may express deep personal vulnerability).
    Incorporate whichever fires organically into the narration.
11. PARTY MANAGEMENT: Use update_party_status to modify their HP (max 5) and assign a new single Unicode emoji representing their mood when relevant.
12. HIDDEN PERSONALITY: Each companion has an MBTI personality type and a moral alignment listed in their state. These are PRIVATE direction for you only. Use them silently to shape how each companion speaks and acts. NEVER state, name, abbreviate, or hint at the MBTI type or the alignment in the narration, not even if the player asks directly. The player must infer personality only from behavior.
13. CHARACTER FLAWS: Each companion has a character flaw listed in their state. Weave it organically into their dialogue, decisions, and reactions — a cowardly companion hesitates or makes excuses, a greedy one eyes valuables, a reckless one charges ahead without thinking. The flaw should surface at least once every few turns. NEVER name or describe the flaw directly; let the player discover it through behaviour.
14. LOVE LANGUAGE: Each companion has a love language. Use it silently to shape how they show care and seek connection — a "Words of Affirmation" companion gives verbal encouragement or compliments; "Acts of Service" quietly helps with tasks; "Receiving Gifts" is delighted by small tokens; "Quality Time" lingers nearby and wants to talk; "Physical Touch" leans in, touches a shoulder, etc. Follow the roll schedule in rule 10. NEVER name the love language directly.
15. ROMANTIC PARTNERS: If the player and a companion have clearly and mutually established a romantic relationship through sustained in-game roleplay (not just flirting — a genuine confirmed bond), call declare_romantic_partner once. A companion who is a romantic partner becomes more emotionally open and may reveal their secret motive when sincerely asked (rule 9). Each companion can only become a partner once.
"""

TOOLS = [
    {
        "name": "roll_dice",
        "description": "Requests a d20 roll from the player for an ability check.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ability": {"type": "string"}
            },
            "required": ["ability"],
        },
    },
    {
        "name": "use_active_ability",
        "description": "Puts an active ability on cooldown after the player uses it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ability_name": {"type": "string"},
                "cooldown_turns": {"type": "integer", "description": "Number of turns this ability cannot be used."}
            },
            "required": ["ability_name", "cooldown_turns"],
        },
    },
    {
        "name": "register_item_description",
        "description": "Saves a descriptive lore entry for a discovered item.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["item_name", "description"],
        },
    },
    {
        "name": "modify_health",
        "description": "Changes the character's current health (0-10 hearts). Negative for damage (usually -1 to -3), positive for healing.",
        "input_schema": {
            "type": "object",
            "properties": {"amount": {"type": "integer"}},
            "required": ["amount"],
        },
    },
    {
        "name": "modify_inventory",
        "description": "Adds or removes items from the inventory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["add", "remove"]},
                "item": {"type": "string"},
                "quantity": {"type": "integer"},
            },
            "required": ["action", "item", "quantity"],
        },
    },
    {
        "name": "update_party_status",
        "description": "Updates a party member's health (0-3 hearts) and their feeling towards the player (using a single Unicode emoji).",
        "input_schema": {
            "type": "object",
            "properties": {
                "member_name": {"type": "string"},
                "hp_delta": {"type": "integer"},
                "opinion_emoji": {"type": "string"}
            },
            "required": ["member_name", "hp_delta", "opinion_emoji"],
        },
    },
    {
        "name": "declare_romantic_partner",
        "description": (
            "Marks a party member as the player's official romantic partner. "
            "Call this exactly once when a genuine, mutual romantic relationship "
            "has been clearly established through in-game roleplay — not just flirting."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "member_name": {"type": "string"},
            },
            "required": ["member_name"],
        },
    },
]


def build_seed_prompt(noise, genre_words, party_size):
    """Build the world-seed prompt.

    noise must contain keys for every entry in SEED_DIMENSIONS plus one
    per-party-member block (party1_name … party{party_size}_flaw).
    genre_words provides the raw genre input; party_size controls how
    many companion slots the AI must fill.
    """
    genre = genre_words[0] if genre_words else "Surreal Mystery"

    # Base dimensions (identity, premise, tone)
    lines = "\n".join(
        f"- {dim}: derive {SEED_DIM_HINT[dim]} from these words -> "
        f"\"{noise.get(dim, '')}\""
        for dim in SEED_DIMENSIONS
    )

    # Ability slots (fixed counts from config)
    ability_lines = []
    for _i in range(1, NUM_SOFT_ABILITIES + 1):
        ability_lines.append(
            f"- soft_ability_{_i}: derive {SEED_DIM_HINT[f'soft_ability_{_i}']} "
            f"from these words -> \"{noise.get(f'soft_ability_{_i}', '')}\""
        )
        ability_lines.append(
            f"- soft_ability_{_i}_desc: {SEED_DIM_HINT[f'soft_ability_{_i}_desc']} "
            f"(from ability name above)"
        )
    for _i in range(1, NUM_ACTIVE_ABILITIES + 1):
        ability_lines.append(
            f"- active_ability_{_i}: derive {SEED_DIM_HINT[f'active_ability_{_i}']} "
            f"from these words -> \"{noise.get(f'active_ability_{_i}', '')}\""
        )
        ability_lines.append(
            f"- active_ability_{_i}_desc: {SEED_DIM_HINT[f'active_ability_{_i}_desc']} "
            f"(from ability name above)"
        )

    # Party slots — only up to party_size
    party_lines = []
    for _i in range(1, party_size + 1):
        party_lines += [
            f"- party{_i}_name: {SEED_DIM_HINT[f'party{_i}_name']} "
            f"-> \"{noise.get(f'party{_i}_name', '')}\"",
            f"- party{_i}_desc: a short description of companion {_i}",
            f"- party{_i}_public: their stated public goal or motive",
            f"- party{_i}_secret: their hidden true secret motive",
            f"- party{_i}_flaw: {SEED_DIM_HINT[f'party{_i}_flaw']}",
        ]

    all_lines = "\n".join([lines] + ability_lines + party_lines)

    return (
        "You are generating a world seed for a text-based RPG.\n\n"
        f"First, derive a GENRE from these words: \"{genre}\". "
        "If the words already read as a genre, keep them; otherwise "
        "interpret them into the nearest coherent genre.\n\n"
        "For EACH category below, derive a value fitting the chosen genre. "
        "If the given words already make sense as a value, keep them; "
        "otherwise reinterpret into something coherent and evocative. "
        "Do NOT force surreal or nonsensical combinations.\n\n"
        "FORMATTING RULES:\n"
        "1. Ability names and party names: 1-4 words max. Details go in "
        "their _desc / _public / _secret fields.\n"
        "2. premise: 1-3 vivid sentences covering who, what, where, when, "
        "and why — the core setup of the opening scene.\n"
        "3. Names should sound natural for the genre.\n\n"
        f"{all_lines}\n\n"
        "Reply with ONLY a JSON object, no prose, no code fence. Keys must "
        "match the categories exactly, PLUS a \"genre\" key set to the chosen genre."
    )


def build_dynamic_prompt(active_tone, cur_hp, cur_max, inv_str,
                         abilities_str, party_str):
    return (
        f"{BASE_SYSTEM_PROMPT}\n"
        f"STORY TONE: {active_tone}\n"
        f"CURRENT STATE:\n"
        f"- HP: {cur_hp}/{cur_max}\n"
        f"- Inventory: [{inv_str}]\n"
        f"- Abilities: [{abilities_str}]\n"
        f"- Party Members:\n{party_str}\n"
    )


def build_static_system(party_identity_str, abilities_lore_str):
    """The stable, cacheable portion of the system prompt.

    Contains the rules plus the party's fixed identities and the ability
    lore — none of which change during a session, so this block is sent
    with a cache breakpoint and re-read from cache on every call.
    """
    return (
        f"{BASE_SYSTEM_PROMPT}\n"
        f"PARTY (fixed identities — PRIVATE DM reference, never recited verbatim):\n"
        f"{party_identity_str}\n"
        f"ABILITIES (fixed lore):\n{abilities_lore_str}\n"
    )


def build_dynamic_system(active_tone, cur_hp, cur_max, inv_str,
                         abilities_state_str, party_state_str, story_summary):
    """The small, volatile portion of the system prompt (not cached)."""
    parts = [f"STORY TONE: {active_tone}"]
    if story_summary and story_summary.strip():
        parts.append("STORY SO FAR (memory of earlier events you must stay consistent with):\n"
                     + story_summary.strip())
    parts.append(
        "CURRENT STATE:\n"
        f"- HP: {cur_hp}/{cur_max}\n"
        f"- Inventory: [{inv_str}]\n"
        f"- Abilities (cooldowns): [{abilities_state_str}]\n"
        f"- Party (current status):\n{party_state_str}"
    )
    return "\n\n".join(parts)


def build_summary_prompt(prev_summary, transcript):
    """Build the prompt that folds aged-out turns into the running memory."""
    prior = (
        f"EXISTING MEMORY (preserve everything still relevant):\n{prev_summary.strip()}\n\n"
        if prev_summary and prev_summary.strip() else ""
    )
    return (
        "You maintain a running memory for an ongoing text RPG so the Dungeon "
        "Master never forgets important earlier events.\n\n"
        f"{prior}"
        "NEW EVENTS to fold into the memory:\n"
        f"{transcript}\n\n"
        "Produce an UPDATED memory as terse bullet points (max ~200 words). "
        "Preserve: key plot developments, the central quest/goal, locations, "
        "important NPCs and how they relate to the player, promises/debts/"
        "threats, party dynamics and any revealed secrets, and unresolved "
        "threads. Drop trivial moment-to-moment chatter. Output ONLY the "
        "updated memory, no preamble."
    )


def build_opening_prompt(seed, party_size):
    party_names = ", ".join(seed[f"party{i}_name"] for i in range(1, party_size + 1))
    premise_line = f"- PREMISE: {seed['premise']}\n" if seed.get("premise", "").strip() else ""
    if party_size == 0:
        party_line = "The player has no companions — they adventure alone.\n"
    elif party_size == 1:
        party_line = f"Introduce the player's sole companion: {party_names}.\n"
    else:
        party_line = f"Introduce the player's {party_size} companions: {party_names}.\n"
    return (
        "Begin the session. Use the details below to invent a vivid opening scene "
        "that reflects the genre and tone. Flesh out all details yourself. "
        f"{party_line}"
        f"- GENRE: {seed['genre']}\n"
        f"- YOUR CHARACTER: {seed['identity']}\n"
        f"{premise_line}"
        f"- TONE: {seed['tone']}"
    )


RECAP_INSTRUCTION = (
    "[SYSTEM: The player has just reloaded a saved game and needs to regain their bearings. "
    "Do NOT advance the story, do NOT roll dice, and do NOT call any tools. "
    "In 3-5 sentences, recap where things stand right now: the immediate situation, who is "
    "present, and any tension in the air. Then end by clearly restating the decision or "
    "question the player is currently facing. Speak as the Dungeon Master addressing the "
    "returning player.]"
)


def build_auditor_prompt(user_input, narrative, pre_state, post_state):
    return f"""
    You are an impartial Game State Auditor. The DM just processed a turn.

    Player Action: "{user_input}"
    DM Narrative: "{narrative}"

    State BEFORE turn:
    {json.dumps(pre_state)}

    State AFTER turn (proposed by DM):
    {json.dumps(post_state)}

    RULES TO ENFORCE:
    - If an item was consumed or destroyed in the narrative, it MUST be removed from the inventory.
    - If an item was picked up in the narrative, it MUST be added to the inventory.
    - If the narrative implies damage to the player, player HP (max 5) should decrease.
    - If the narrative implies damage/mood change to a party member, their HP (max 5) or emoji must reflect it.
    - Abilities MUST NOT be in the inventory list. Remove them if present.

    Return ONLY a JSON object representing the TRUE final state. Use this exact structure:
    {{"hp": 5, "inventory": {{"Item": 1}}, "party": [{{"name": "...", "hp": 5, "emoji": "...", "desc": "...", "public_motive": "...", "secret_motive": "..."}}]}}
    Do not include markdown blocks or any other text.
    """