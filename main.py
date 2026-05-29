import pygame
import random
import string
import threading
import json
import os
import sys
import anthropic
from dotenv import load_dotenv
from wonderwords import RandomWord

from config import (
    WINDOW_SIZE, WINDOW_TITLE, TARGET_FPS,
    MODEL_NAME, FALLBACK_MODELS,
    MAX_TOOL_ITERATIONS, API_MAX_RETRIES, RETRYABLE_STATUS,
    RETRY_BASE_WAIT, RETRY_MAX_WAIT, RETRY_JITTER,
    SAVE_PATH, HISTORY_WINDOW,
    SEED_MAX_ATTEMPTS, SEED_WAIT_BASE, SEED_WAIT_MAX,
    STARTING_HP, PARTY_HP_MAX,
    STARTING_INVENTORY, DEFAULT_ITEM_DESCRIPTION, RATIONS_DESCRIPTION,
    INPUT_MAX_LENGTH, SETUP_FIELD_MAX_LENGTH, MEANINGFUL_INPUT_MIN_ALNUM,
    MBTI_TYPES, ALIGNMENTS, LOVE_LANGUAGES, DND_NAME_LANGUAGES,
    PARTY_SIZE, NUM_SOFT_ABILITIES, NUM_ACTIVE_ABILITIES,
    STREAMING_CHUNK_SIZE,
    DICE_ROLL_FRAMES, DICE_HOLD_FRAMES,
    CURSOR_BLINK_MS,
)

from prompts import (
    SEED_DIMENSIONS,
    TOOLS,
    build_seed_prompt,
    build_dynamic_prompt,
    build_opening_prompt,
    build_auditor_prompt,
)

from ui import (
    UI,
    sanitize_text,
    clean_name,
    build_styled_lines,
    build_plain_lines,
    draw_setup_screen,
    draw_play_screen,
    set_party_color_provider,
)

pygame.init()
is_fullscreen = False
screen = pygame.display.set_mode(WINDOW_SIZE, pygame.SCALED)
pygame.display.set_caption(WINDOW_TITLE)

clock = pygame.time.Clock()

load_dotenv()
active_model = MODEL_NAME
API_KEY = os.environ.get("ANTHROPIC_API_KEY")
client = None
init_error = None

if API_KEY:
    try:
        client = anthropic.Anthropic()
    except Exception as exc:
        init_error = f"Anthropic client init failed: {exc}"
else:
    init_error = "ANTHROPIC_API_KEY is not set. Add it to a .env file."

game_state = "setup"

debug_mode = False
_debug_seq = 0

def _dbg_block_str(block):
    get = block.get if isinstance(block, dict) else lambda k, d=None: getattr(block, k, d)
    btype = get("type", "?")
    if btype == "text":
        return f"text: {get('text', '')}"
    if btype == "tool_use":
        return f"tool_use: {get('name', '?')} args={get('input', {})}"
    if btype == "tool_result":
        return f"tool_result -> {get('content')}"
    return f"{btype}: {block}"

def _dbg_header(title):
    global _debug_seq
    _debug_seq += 1
    print(f"\n{'='*78}\n[AI-DEBUG #{_debug_seq}] {title}\n{'='*78}")

def _dbg_sent(label, system, messages, tools=None):
    _dbg_header(f"REQUEST -> {label}  (model={active_model})")
    if system is not None:
        print("  SYSTEM PROMPT:\n  " + str(system).replace("\n", "\n  "))
    if tools:
        print(f"  TOOLS AVAILABLE: {[t.get('name', '?') for t in tools]}")
    print("  MESSAGES:")
    for i, msg in enumerate(messages):
        content = msg.get("content")
        if isinstance(content, list):
            print(f"  [{i}] {msg.get('role', '?')}: (structured)")
            for block in content:
                print(f"        {_dbg_block_str(block)}")
        else:
            print(f"  [{i}] {msg.get('role', '?')}: {content}")

def _dbg_received(label, response):
    _dbg_header(f"RESPONSE <- {label}")
    stop = getattr(response, "stop_reason", None)
    usage = getattr(response, "usage", None)
    if stop is not None:
        print(f"  stop_reason: {stop}")
    if usage is not None:
        print(f"  usage: input={getattr(usage, 'input_tokens', '?')} "
              f"output={getattr(usage, 'output_tokens', '?')}")
    print("  CONTENT BLOCKS:")
    for block in getattr(response, "content", []):
        print(f"    {_dbg_block_str(block)}")


def random_personality():
    return random.choice(MBTI_TYPES), random.choice(ALIGNMENTS)


# Name-seeding dimensions that receive language+char seeds instead of random words.
_NAME_DIMS = {"party1_name", "party2_name", "party3_name"}


def random_name_seed():
    """Return a seed string of the form '[Language] <random_chars>' (2-15 chars).

    The language is drawn from DND_NAME_LANGUAGES; the character string is a
    random mix of lowercase letters and spaces that the AI uses as loose
    phonetic inspiration when deriving a party-member name.
    """
    lang = random.choice(DND_NAME_LANGUAGES)
    length = random.randint(2, 15)
    alphabet = string.ascii_lowercase + "    "   # spaces weighted ~20 %
    chars = "".join(random.choices(alphabet, k=length)).strip()
    if not chars:                                # edge-case: all spaces
        chars = random.choice(string.ascii_lowercase)
    return f"[{lang}] {chars}"

setup_fields = [
    {"key": "genre", "label": "Genre", "text": "", "rect": pygame.Rect(0, 0, 0, 0)},
    {"key": "tone", "label": "Tone", "text": "", "rect": pygame.Rect(0, 0, 0, 0)},
    {"key": "who", "label": "Who", "text": "", "rect": pygame.Rect(0, 0, 0, 0)},
    {"key": "what", "label": "What", "text": "", "rect": pygame.Rect(0, 0, 0, 0)},
    {"key": "when", "label": "When", "text": "", "rect": pygame.Rect(0, 0, 0, 0)},
    {"key": "where", "label": "Where", "text": "", "rect": pygame.Rect(0, 0, 0, 0)},
    {"key": "why", "label": "Why", "text": "", "rect": pygame.Rect(0, 0, 0, 0)},
]
setup_active_idx = None
btn_dice_rect = pygame.Rect(0, 0, 0, 0)
btn_start_rect = pygame.Rect(0, 0, 0, 0)

state_lock = threading.RLock()
turn_lock = threading.Lock()

hp, max_hp = STARTING_HP, STARTING_HP
player_alive = True
inventory = dict(STARTING_INVENTORY)
abilities = {}
item_descriptions = {k: RATIONS_DESCRIPTION for k in STARTING_INVENTORY}
party = []

chat_history = []
active_vibe = "neutral"
all_lines = []
scroll_y = 0

streaming_text_full = ""
streaming_text_current = ""
streaming_index = 0
is_streaming = False
is_ai_thinking = False

dice_event = threading.Event()
dice_state = "idle"
dice_rect = pygame.Rect(0, 0, 0, 0)
dice_current_val = 1
dice_final_val = 1
dice_skill = "None"
dice_modifier = 0
dice_timer = 0
dice_roll_accumulator = 0.0

shutdown_event = threading.Event()

_rand_word = RandomWord()

def _build_party_color_map():
    out = {}
    with state_lock:
        members = list(party)
    for m in members:
        col = m.get("color")
        if not col:
            continue
        col = tuple(col)
        name = (m.get("name") or "").strip()
        if not name:
            continue
        out[name.lower()] = col
        for tok in name.split():
            t = tok.strip(".,!?;:'\"()[]-").lower()
            if len(t) >= 3:
                out.setdefault(t, col)
    return out

set_party_color_provider(_build_party_color_map)

def random_words(n):
    out = []
    for _ in range(n):
        try:
            out.append(_rand_word.word())
        except Exception:
            out.append(random.choice(["mystic", "echo", "void", "ember", "thorn", "drift"]))
    return out

def _parse_seed_json(text):
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.strip().lower().startswith("json"):
            text = text.strip()[4:]
        text = text.strip()
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        text = text[first:last + 1]
    cleaned = "".join(
        ch if (ord(ch) >= 0x20 or ch in "\t") else " "
        for ch in text
    )
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    repaired = cleaned
    if repaired.count('"') % 2 == 1:
        repaired += '"'
    open_braces = repaired.count("{") - repaired.count("}")
    if open_braces > 0:
        repaired = repaired.rstrip().rstrip(",")
        repaired += "}" * open_braces
    return json.loads(repaired)

def _ask_ai_for_custom_seed(genre_text, dimension_dict):
    prompt = build_seed_prompt(dimension_dict, [genre_text])

    if debug_mode:
        _dbg_sent("SEED GENERATION", None,
                  [{"role": "user", "content": prompt}])

    resp = _call_with_retry(
        "SEED GENERATION",
        max_tokens=2000,
        temperature=1.0,
        messages=[{"role": "user", "content": prompt}],
    )

    if debug_mode:
        _dbg_received("SEED GENERATION", resp)

    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()

    data = _parse_seed_json(text)

    chosen_genre = str(data.get("genre", "")).strip() or genre_text
    seed = {"genre": chosen_genre}

    for dim in SEED_DIMENSIONS:
        val = str(data.get(dim, "")).strip()
        seed[dim] = val

    return seed

def generate_custom_seed_from_inputs(genre_text, dimension_dict):
    if client is None:
        log_output("[SEED] No API client available.", (255, 80, 80))
        return None
    last_exc = None
    for attempt in range(SEED_MAX_ATTEMPTS):
        try:
            return _ask_ai_for_custom_seed(genre_text, dimension_dict)
        except Exception as exc:
            last_exc = exc
            reason = f"{type(exc).__name__}: {exc}"
            print(f"\n[AI-DEBUG] SEED GENERATION attempt "
                  f"{attempt + 1}/{SEED_MAX_ATTEMPTS} failed -> {reason}")
            log_output(
                f"[SEED] Attempt {attempt + 1}/{SEED_MAX_ATTEMPTS} "
                f"failed: {reason}",
                (255, 165, 0),
            )
            if attempt < SEED_MAX_ATTEMPTS - 1:
                shutdown_event.wait(min(SEED_WAIT_BASE * (attempt + 1), SEED_WAIT_MAX))
                if shutdown_event.is_set():
                    return None
                continue
    if last_exc is not None:
        log_output(
            f"[SEED] All attempts exhausted. Last error: "
            f"{type(last_exc).__name__}: {last_exc}",
            (255, 80, 80),
        )
    return None

def log_styled(text, base_color=(220, 220, 220)):
    new_lines = build_styled_lines(text, base_color)
    with state_lock:
        for line_runs in new_lines:
            all_lines.append(line_runs)

def log_output(text, color=(200, 200, 200)):
    new_lines = build_plain_lines(text, color)
    with state_lock:
        for line in new_lines:
            all_lines.append(line)

def save_game():
    with state_lock:
        data = {
            "hp": hp,
            "max_hp": max_hp,
            "player_alive": player_alive,
            "inventory": inventory,
            "abilities": abilities,
            "item_descriptions": item_descriptions,
            "party": party,
            "active_vibe": active_vibe,
            "chat_history": _serialize_history(chat_history),
        }
    try:
        with open(SAVE_PATH, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        log_output("[SYSTEM] Game saved.", (0, 255, 255))
    except OSError as exc:
        log_output(f"[SYSTEM] Save failed: {exc}", (255, 80, 80))

def _block_to_jsonable(block):
    if isinstance(block, dict):
        return block
    btype = getattr(block, "type", None)
    if btype == "text":
        return {"type": "text", "text": getattr(block, "text", "")}
    if btype == "tool_use":
        return {
            "type": "tool_use",
            "id": getattr(block, "id", ""),
            "name": getattr(block, "name", ""),
            "input": getattr(block, "input", {}) or {},
        }
    if hasattr(block, "model_dump"):
        try:
            return block.model_dump()
        except Exception:
            pass
    if hasattr(block, "to_dict"):
        try:
            return block.to_dict()
        except Exception:
            pass
    return {"type": str(btype or "text"), "text": str(block)}

def _serialize_history(history):
    out = []
    for msg in history:
        role = msg.get("role")
        content = msg.get("content")
        if isinstance(content, str):
            out.append({"role": role, "content": content})
        elif isinstance(content, list):
            out.append({
                "role": role,
                "content": [_block_to_jsonable(b) for b in content],
            })
        else:
            out.append({"role": role, "content": str(content)})

    while out:
        last = out[-1]
        if last.get("role") != "assistant":
            break
        c = last.get("content")
        has_tool_use = (
            isinstance(c, list)
            and any(isinstance(b, dict) and b.get("type") == "tool_use"
                    for b in c)
        )
        if has_tool_use:
            out.pop()
        else:
            break
    return out

def _trim_history_for_request(history):
    if len(history) <= HISTORY_WINDOW:
        return list(history)
    window = history[-HISTORY_WINDOW:]
    start = 0
    for i, msg in enumerate(window):
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        is_tool_result = (
                isinstance(content, list)
                and any(isinstance(b, dict) and b.get("type") == "tool_result"
                        for b in content)
        )
        if not is_tool_result:
            start = i
            break
    return window[start:]

def load_game():
    global hp, max_hp, player_alive, inventory, abilities
    global item_descriptions, party, chat_history, active_vibe
    if not os.path.exists(SAVE_PATH):
        log_output("[SYSTEM] No save file found.", (255, 165, 0))
        return False
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        log_output(f"[SYSTEM] Load failed: {exc}", (255, 80, 80))
        return False
        with state_lock:
            hp = min(data.get("hp", STARTING_HP), STARTING_HP)
            max_hp = STARTING_HP
        player_alive = data.get("player_alive", True)
        inventory = data.get("inventory", {})
        loaded_abilities = data.get("abilities", {})
        abilities.clear()
        for k, v in loaded_abilities.items():
            abilities[clean_name(k)] = v
        item_descriptions = data.get("item_descriptions", {})
        active_vibe = data.get("active_vibe", "neutral")
        loaded_history = data.get("chat_history", [])
        while loaded_history and loaded_history[0].get("role") != "user":
            loaded_history.pop(0)
        chat_history = loaded_history
        loaded_party = data.get("party", [])
        if loaded_party and isinstance(loaded_party[0], str):
            party = [{"name": clean_name(p), "hp": PARTY_HP_MAX, "emoji": "\U0001F610",
                      "desc": "", "public_motive": "", "secret_motive": "",
                      "flaw": "",
                      "love_language": random.choice(LOVE_LANGUAGES),
                      "is_partner": False,
                      "mbti": random_personality()[0],
                      "alignment": random_personality()[1]}
                     for p in loaded_party]
        else:
            party = loaded_party
            for _m in party:
                _m["name"] = clean_name(_m.get("name", ""))
                if not _m.get("mbti"):
                    _m["mbti"] = random.choice(MBTI_TYPES)
                if not _m.get("alignment"):
                    _m["alignment"] = random.choice(ALIGNMENTS)
                if "flaw" not in _m:
                    _m["flaw"] = ""
                if "love_language" not in _m:
                    _m["love_language"] = random.choice(LOVE_LANGUAGES)
                if "is_partner" not in _m:
                    _m["is_partner"] = False
        for _i, _m in enumerate(party):
            if not _m.get("color"):
                _m["color"] = list(UI.PARTY_COLORS[_i % len(UI.PARTY_COLORS)])

    log_output("[SYSTEM] Game loaded. Continue your adventure.", (0, 255, 0))
    return True

def _extract_text(content_blocks):
    parts = [b.text for b in content_blocks if getattr(b, "type", None) == "text"]
    return "\n".join(p for p in parts if p).strip()

_RETRYABLE_STATUS = RETRYABLE_STATUS

def _is_retryable(exc):
    status = getattr(exc, "status_code", None)
    if status in _RETRYABLE_STATUS:
        return True
    if isinstance(exc, getattr(anthropic, "APIConnectionError", ())):
        return True
    if isinstance(exc, getattr(anthropic, "APITimeoutError", ())):
        return True
    text = str(exc).lower()
    return "overloaded" in text or "529" in text

def _models_to_try():
    if active_model in FALLBACK_MODELS:
        return FALLBACK_MODELS[FALLBACK_MODELS.index(active_model):]
    return [active_model] + FALLBACK_MODELS

def _call_with_retry(label, **create_kwargs):
    global active_model
    create_kwargs.pop("model", None)
    last_exc = None
    models = _models_to_try()

    for model_idx, model_name in enumerate(models):
        for attempt in range(API_MAX_RETRIES):
            if shutdown_event.is_set():
                raise RuntimeError("Shutting down.")
            try:
                resp = client.messages.create(model=model_name,
                                               **create_kwargs)
                if model_name != active_model:
                    print(f"\n[AI-DEBUG] {label}: switched active model "
                          f"to '{model_name}' after fallback.")
                    log_output(
                        f"[SYSTEM] Primary model overloaded; now using "
                        f"'{model_name}'.",
                        (255, 165, 0),
                    )
                    active_model = model_name
                return resp
            except Exception as exc:
                last_exc = exc
                retryable = _is_retryable(exc)
                more_attempts = attempt < API_MAX_RETRIES - 1
                if not retryable:
                    raise
                if more_attempts:
                    wait = (min(RETRY_BASE_WAIT * (2 ** attempt), RETRY_MAX_WAIT)
                            + random.uniform(0, RETRY_JITTER))
                    if debug_mode:
                        print(f"\n[AI-DEBUG] {label}: transient error on "
                              f"'{model_name}' ({exc}); retry "
                              f"{attempt + 1}/{API_MAX_RETRIES - 1} "
                              f"in {wait:.1f}s")
                    shutdown_event.wait(wait)
                else:
                    if model_idx < len(models) - 1:
                        nxt = models[model_idx + 1]
                        print(f"\n[AI-DEBUG] {label}: '{model_name}' still "
                              f"overloaded after {API_MAX_RETRIES} tries; "
                              f"falling back to '{nxt}'.")
                        log_output(
                            f"[SYSTEM] '{model_name}' overloaded - trying "
                            f"'{nxt}'...",
                            (255, 165, 0),
                        )
    raise last_exc

def process_player_action_core(user_input):
    with state_lock:
        history_mark = len(chat_history)
        chat_history.append({"role": "user", "content": user_input})
        inv_str = ", ".join(f"{k} (x{v})" for k, v in inventory.items()) or "Empty"
        abilities_str = ", ".join(
            f"{k} ({v.get('type')}, cd: {v.get('cooldown', 0)})"
            for k, v in abilities.items()
        ) or "None"
        party_hidden_rolls = {p['name']: random.randint(1, 20) for p in party}
        party_str = ""
        for m in party:
            roll = party_hidden_rolls[m['name']]
            party_str += f"- {m['name']} (HP: {m['hp']}/5, Mood: {m.get('emoji', chr(0x1F610))})\n"
            party_str += f"  Desc: {m.get('desc', '')}\n"
            party_str += f"  Personality (MBTI): {m.get('mbti', '')}\n"
            party_str += f"  Alignment: {m.get('alignment', '')}\n"
            party_str += f"  Character Flaw: {m.get('flaw', '')}\n"
            party_str += f"  Love Language: {m.get('love_language', '')}\n"
            party_str += f"  Romantic Partner: {'Yes' if m.get('is_partner') else 'No'}\n"
            party_str += f"  Public Motive: {m.get('public_motive', '')}\n"
            party_str += f"  Secret Motive: {m.get('secret_motive', '')}\n"
            party_str += f"  Hidden Roll this turn: {roll}\n"
        cur_hp, cur_max = hp, max_hp

    dynamic_prompt = build_dynamic_prompt(
        active_vibe, cur_hp, cur_max, inv_str, abilities_str, party_str
    )

    accumulated_text = []
    any_tool_used = False

    def _rollback():
        with state_lock:
            del chat_history[history_mark:]

    for iter_idx in range(MAX_TOOL_ITERATIONS):
        if shutdown_event.is_set():
            return "", any_tool_used, False

        try:
            with state_lock:
                messages_snapshot = _trim_history_for_request(chat_history)

            if debug_mode:
                _dbg_sent(f"PLAYER ACTION (iter {iter_idx})", dynamic_prompt,
                          messages_snapshot, TOOLS)

            response = _call_with_retry(
                f"PLAYER ACTION (iter {iter_idx})",
                max_tokens=1024,
                system=dynamic_prompt,
                tools=TOOLS,
                messages=messages_snapshot,
            )

            if debug_mode:
                _dbg_received(f"PLAYER ACTION (iter {iter_idx})", response)
        except Exception as exc:
            _rollback()
            overloaded = _is_retryable(exc)
            if overloaded:
                msg = ("[The Dungeon Master is overwhelmed by too many "
                       "petitioners right now. Your action was NOT applied "
                       "- wait a moment and try again.]")
            else:
                msg = ("[The Dungeon Master's connection falters and the "
                       "moment is lost. Your action was NOT applied - "
                       "please try again.]")
            return msg, False, False

        step_text = _extract_text(response.content)
        if step_text:
            accumulated_text.append(step_text)

        has_tool_use = any(getattr(b, "type", None) == "tool_use" for b in response.content)

        if not has_tool_use:
            with state_lock:
                chat_history.append({"role": "assistant", "content": response.content})
            return "\n\n".join(accumulated_text).strip(), any_tool_used, True

        any_tool_used = True
        with state_lock:
            chat_history.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            if debug_mode:
                print(f"\n[AI-DEBUG] Executing tool '{block.name}' "
                      f"with args {block.input}")
            try:
                result_msg = _handle_tool(block.name, block.input)
            except Exception as exc:
                result_msg = f"Tool error: {exc}"
            if debug_mode:
                print(f"[AI-DEBUG] Tool '{block.name}' returned: {result_msg}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_msg,
            })

        with state_lock:
            chat_history.append({"role": "user", "content": tool_results})

    final_text = "\n\n".join(accumulated_text).strip()
    final_text = final_text or "[The Dungeon Master pauses, momentarily lost in thought. Try a simpler action.]"
    return final_text, any_tool_used, True

def audit_and_correct_state(user_input, narrative, pre_state, post_state):
    global hp, max_hp, player_alive, inventory, party, abilities
    prompt = build_auditor_prompt(user_input, narrative, pre_state, post_state)
    try:
        if debug_mode:
            _dbg_sent("STATE AUDITOR", None,
                      [{"role": "user", "content": prompt}])

        resp = _call_with_retry(
            "STATE AUDITOR",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )

        if debug_mode:
            _dbg_received("STATE AUDITOR", resp)

        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
        try:
            fixed_state = _parse_seed_json(text)
        except json.JSONDecodeError:
            return narrative

        with state_lock:
            fixed_hp = max(0, min(max_hp, fixed_state.get("hp", hp)))
            if fixed_hp < post_state.get("hp"):
                hp_loss = post_state.get("hp") - fixed_hp
                log_output(f"[DAMAGE TAKEN] You lose {hp_loss} HP!", (255, 70, 70))

            inv_clean = {
                k: v for k, v in fixed_state.get("inventory", {}).items()
                if k not in abilities
            }

            fixed_party = fixed_state.get("party", [])
            if fixed_party != post_state.get("party"):
                for i, pm in enumerate(fixed_party):
                    if i < len(post_state.get("party", [])) and pm.get("hp", 5) < post_state["party"][i].get("hp", 5):
                        p_loss = post_state["party"][i]["hp"] - pm["hp"]
                        log_output(f"[PARTY DAMAGE] {pm['name']} loses {p_loss} HP!", (255, 70, 70))

            changed = (
                fixed_hp != post_state.get("hp")
                or inv_clean != post_state.get("inventory")
                or fixed_party != post_state.get("party")
            )

            hp = fixed_hp
            if hp == 0 and player_alive:
                player_alive = False
                log_output("[YOU HAVE FALLEN] Your journey ends here.", (255, 40, 40))

            inventory.clear()
            inventory.update(inv_clean)
            for item in inventory:
                if item not in item_descriptions:
                    item_descriptions[item] = DEFAULT_ITEM_DESCRIPTION

            prev_meta = {
                m["name"]: (
                    m.get("color"), m.get("mbti"), m.get("alignment"),
                    m.get("flaw", ""), m.get("love_language", ""),
                    m.get("is_partner", False),
                )
                for m in party
            }
            party.clear()
            for idx, _pm in enumerate(fixed_party):
                if isinstance(_pm, dict) and "name" in _pm:
                    _pm["name"] = clean_name(_pm["name"])
                    old_color, old_mbti, old_align, old_flaw, old_ll, old_partner = prev_meta.get(
                        _pm["name"], (None, None, None, "", "", False)
                    )
                    if not _pm.get("color"):
                        _pm["color"] = old_color or list(
                            UI.PARTY_COLORS[idx % len(UI.PARTY_COLORS)]
                        )
                    _pm["mbti"]         = old_mbti or _pm.get("mbti") or random.choice(MBTI_TYPES)
                    _pm["alignment"]    = old_align or _pm.get("alignment") or random.choice(ALIGNMENTS)
                    _pm["flaw"]         = _pm.get("flaw") or old_flaw
                    _pm["love_language"]= _pm.get("love_language") or old_ll or random.choice(LOVE_LANGUAGES)
                    _pm["is_partner"]   = old_partner or _pm.get("is_partner", False)
            party.extend(fixed_party)

        if changed:
            log_output("[SYSTEM] The Gamestate Auditor noticed an anomaly and synchronized reality.", (150, 150, 150))
    except Exception:
        pass
    return narrative

def _handle_tool(name, args):
    global hp, player_alive
    if not isinstance(args, dict):
        return "Tool call ignored (no arguments)."

    if name == "roll_dice":
        chosen_ability = args.get("ability", "None")
        base_roll = random.randint(1, 20)
        _start_dice(chosen_ability, base_roll, 0)
        dice_event.clear()
        while not dice_event.is_set():
            if shutdown_event.is_set():
                return "Action cancelled."
            dice_event.wait(0.5)
        result_str = f"Dice check resolved. Base: {base_roll}, Total: {base_roll}"
        if base_roll == 20:
            result_str += " (CRITICAL SUCCESS)"
        elif base_roll == 1:
            result_str += " (CRITICAL FAILURE)"
        log_output(f"[DICE ROLL] {chosen_ability} check: {base_roll}", (255, 0, 128))
        return result_str

    if name == "use_active_ability":
        ab_name = clean_name(str(args.get("ability_name", "")).strip())
        turns = int(args.get("cooldown_turns", 3))
        with state_lock:
            for k, v in abilities.items():
                if clean_name(k) == ab_name or k.lower() in ab_name.lower() or ab_name.lower() in k.lower():
                    v["cooldown"] = turns
                    return f"Ability {k} is now on cooldown for {turns} turns."
        return f"Ability {ab_name} not found."

    if name == "register_item_description":
        item_name = str(args.get("item_name", "")).strip()
        item_desc = str(args.get("description", "")).strip()
        if not item_name:
            return "register_item_description ignored: missing item name."
        with state_lock:
            item_descriptions[item_name] = item_desc or "(no description)"
        return f"Item lore recorded: {item_name}."

    if name == "modify_health":
        try:
            delta = int(args.get("amount", 0))
        except (TypeError, ValueError):
            delta = 0
        with state_lock:
            hp = max(0, min(max_hp, hp + delta))
            current = hp
            if hp == 0 and player_alive:
                player_alive = False
                died = True
            else:
                died = False
        if delta < 0:
            log_output(f"[DAMAGE TAKEN] You lose {abs(delta)} HP!", (255, 70, 70))
        elif delta > 0:
            log_output(f"[HEALED] You recover {delta} HP.", (70, 255, 70))
        if died:
            log_output("[YOU HAVE FALLEN] Your journey ends here.", (255, 40, 40))
        return f"HP is now {current}."

    if name == "modify_inventory":
        act = args.get("action")
        itm = str(args.get("item", "")).strip()
        try:
            qty = int(args.get("quantity", 0))
        except (TypeError, ValueError):
            qty = 0
        if act not in ("add", "remove") or not itm or qty <= 0:
            return "modify_inventory ignored: invalid arguments."
        with state_lock:
            if act == "add":
                if itm in abilities:
                    return f"Cannot add ability '{itm}' to physical inventory."
                inventory[itm] = inventory.get(itm, 0) + qty
                if itm not in item_descriptions:
                    item_descriptions[itm] = DEFAULT_ITEM_DESCRIPTION
            elif act == "remove" and itm in inventory:
                inventory[itm] = max(0, inventory[itm] - qty)
                if inventory[itm] == 0:
                    del inventory[itm]
        return f"Inventory updated ({act} {qty} {itm})."

    if name == "update_party_status":
        member_name = str(args.get("member_name", "")).strip()
        hp_delta = int(args.get("hp_delta", 0))
        new_emoji = str(args.get("opinion_emoji", "")).strip()
        with state_lock:
            for m in party:
                if member_name.lower() in m["name"].lower() or m["name"].lower() in member_name.lower():
                    m["hp"] = max(0, min(5, m["hp"] + hp_delta))
                    if new_emoji:
                        m["emoji"] = new_emoji
                    if hp_delta < 0:
                        log_output(f"[PARTY DAMAGE] {m['name']} loses {abs(hp_delta)} HP!", (255, 70, 70))
                    elif hp_delta > 0:
                        log_output(f"[PARTY HEAL] {m['name']} recovers {hp_delta} HP.", (70, 255, 70))
                    return f"{m['name']} status updated."
        return "Party member not found."

    if name == "declare_romantic_partner":
        member_name = str(args.get("member_name", "")).strip()
        with state_lock:
            for m in party:
                if member_name.lower() in m["name"].lower() or m["name"].lower() in member_name.lower():
                    if m.get("is_partner"):
                        return f"{m['name']} is already your romantic partner."
                    m["is_partner"] = True
                    log_output(
                        f"[ROMANCE] {m['name']} has become your romantic partner. "
                        f"Their true self may now come to light.",
                        (255, 150, 200),
                    )
                    return f"{m['name']} is now the player's romantic partner."
        return "Party member not found."

    return "Unknown command ignored."

def _start_dice(skill, final_val, modifier):
    global dice_skill, dice_final_val, dice_modifier, dice_timer, dice_state, dice_roll_accumulator
    with state_lock:
        dice_skill = skill
        dice_final_val = final_val
        dice_modifier = modifier
        dice_timer = 0
        dice_roll_accumulator = 0.0
        dice_state = "wait"

def run_async_ai_turn(user_input, is_opening=False):
    global is_ai_thinking, streaming_text_full, is_streaming
    global streaming_index, streaming_text_current

    if not turn_lock.acquire(blocking=False):
        log_output("[The Dungeon Master is still resolving the last action - wait a moment.]", (255, 165, 0))
        return
    try:
        is_ai_thinking = True
        with state_lock:
            for ab in abilities.values():
                if ab.get("type") == "active" and ab.get("cooldown", 0) > 0:
                    ab["cooldown"] -= 1
            pre_state = {
                "hp": hp,
                "inventory": dict(inventory),
                "party": [dict(p) for p in party]
            }

        try:
            narrative, any_tool_used, turn_ok = process_player_action_core(user_input)
        except Exception as exc:
            narrative = f"[The Dungeon Master falters - an unexpected error occurred: {exc}. Try again.]"
            any_tool_used = False
            turn_ok = False

        if shutdown_event.is_set():
            is_ai_thinking = False
            return
        if not narrative or not narrative.strip():
            narrative = "[The Dungeon Master is silent. Try a different action.]"
        with state_lock:
            post_state = {
                "hp": hp,
                "inventory": dict(inventory),
                "party": [dict(p) for p in party]
            }

        if turn_ok and any_tool_used and post_state != pre_state and not is_opening:
            narrative = audit_and_correct_state(user_input, narrative, pre_state, post_state)

        streaming_text_full = sanitize_text(narrative)
        streaming_text_current = ""
        streaming_index = 0
        is_streaming = True
        is_ai_thinking = False
    finally:
        turn_lock.release()

def boot_session(genre_text, dimension_dict):
    global active_vibe, is_ai_thinking
    is_ai_thinking = True

    log_output("System: Initialization online.", (0, 255, 255))
    if init_error:
        log_output(f"[FATAL] {init_error}", (255, 80, 80))
        log_output("The game cannot contact the Dungeon Master without a valid key.", (255, 165, 0))
        is_ai_thinking = False
        return

    log_output("Controls: F11 fullscreen | F12 debug view | Ctrl+S save | Ctrl+L load | Arrows/Wheel scroll", (100, 100, 105))
    log_output("Rolling the dice of fate...", (110, 110, 140))

    seed = generate_custom_seed_from_inputs(genre_text, dimension_dict)
    if seed is None:
        is_ai_thinking = False
        log_output(
            "[The Dungeon Master is weary and cannot conjure a world "
            "right now. The realm is overburdened with travelers - "
            "please try again in a little while.]",
            (255, 165, 0),
        )
        return

    active_vibe = seed.get("tone", dimension_dict.get("tone", "neutral"))
    with state_lock:
        abilities.clear()
        for kind, count in (("soft", NUM_SOFT_ABILITIES), ("active", NUM_ACTIVE_ABILITIES)):
            for n in range(1, count + 1):
                name = clean_name(seed[f"{kind}_ability_{n}"])
                abilities[name] = {
                    "type": kind,
                    "desc": seed[f"{kind}_ability_{n}_desc"],
                    "cooldown": 0,
                }
        party.clear()
        for i in range(PARTY_SIZE):
            mbti, align = random_personality()
            party.append({
                "name": clean_name(seed[f"party{i + 1}_name"]),
                "desc": seed[f"party{i + 1}_desc"],
                "public_motive": seed[f"party{i + 1}_public"],
                "secret_motive": seed[f"party{i + 1}_secret"],
                "flaw": seed.get(f"party{i + 1}_flaw", ""),
                "love_language": random.choice(LOVE_LANGUAGES),
                "is_partner": False,
                "mbti": mbti, "alignment": align,
                "hp": PARTY_HP_MAX, "emoji": "\U0001F610",
                "color": list(UI.PARTY_COLORS[i % len(UI.PARTY_COLORS)]),
            })

    if debug_mode:
        print("\n[AI-DEBUG] Party personalities assigned by code:")
        for _m in party:
            print(f"  {_m['name']}: {_m['mbti']} / {_m['alignment']}")

    log_output(
        f"[SEED] {dimension_dict.get('who', 'Unknown')} / "
        f"{dimension_dict.get('what', 'Unknown')} / "
        f"{dimension_dict.get('when', 'Unknown')} / "
        f"{dimension_dict.get('where', 'Unknown')} / "
        f"{dimension_dict.get('why', 'Unknown')}  [TONE: {active_vibe}]",
        (110, 110, 140),
    )
    opening = build_opening_prompt(seed)
    run_async_ai_turn(opening, is_opening=True)

input_text = ""
active = True
dragging_scrollbar = False
sb_geom = {"x": 895, "w": 6, "top": 28, "h": 540, "visible": 27}

def _partial_styler(text, width):
    return build_styled_lines(text, UI.TEXT, max_width=width)

def _build_render_snapshot():
    with state_lock:
        snap = {
            "lines": list(all_lines),
            "hp": hp,
            "max_hp": max_hp,
            "alive": player_alive,
            "abilities": {k: dict(v) for k, v in abilities.items()},
            "inventory": list(inventory.items()),
            "item_desc": dict(item_descriptions),
            "party": list(party),
            "dice_skill": dice_skill,
            "dice_state": dice_state,
            "dice_current": dice_current_val,
            "dice_final": dice_final_val,
            "dice_modifier": dice_modifier,
            "dice_timer": dice_timer,
        }
    snap.update({
        "debug_mode": debug_mode,
        "is_ai_thinking": is_ai_thinking,
        "is_streaming": is_streaming,
        "scroll_y": scroll_y,
        "input_text": input_text,
        "busy": busy,
        "streaming_text_current": streaming_text_current,
        "partial_styler": _partial_styler,
    })
    return snap

while active:

    if is_streaming:
        if streaming_index < len(streaming_text_full):
            streaming_text_current += streaming_text_full[streaming_index:streaming_index + STREAMING_CHUNK_SIZE]
            streaming_index += STREAMING_CHUNK_SIZE
        else:
            log_styled(streaming_text_full, (220, 220, 220))
            is_streaming = False
            streaming_text_full = ""
            streaming_text_current = ""

    if dice_state == "roll":
        dice_timer += 1
        p = dice_timer / DICE_ROLL_FRAMES
        speed = max(0.03, (1.0 - p) ** 2.5)
        dice_roll_accumulator += speed
        if dice_roll_accumulator >= 1.0:
            dice_current_val = random.randint(1, 20)
            dice_roll_accumulator -= 1.0
        if dice_timer >= DICE_ROLL_FRAMES:
            dice_state = "base"
            dice_current_val = dice_final_val
            dice_timer = 0
    elif dice_state == "base":
        dice_timer += 1
        if dice_timer > DICE_HOLD_FRAMES:
            dice_state = "mod"
            dice_timer = 0
    elif dice_state == "mod":
        dice_timer += 1
        if dice_timer > DICE_HOLD_FRAMES:
            dice_state = "done"
            dice_timer = 0
            dice_event.set()

    busy = is_ai_thinking or is_streaming or turn_lock.locked()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            active = False

        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            ctrl = mods & pygame.KMOD_CTRL

            if event.key == pygame.K_F11:
                is_fullscreen = not is_fullscreen
                flags = pygame.SCALED | (pygame.FULLSCREEN if is_fullscreen else 0)
                screen = pygame.display.set_mode(WINDOW_SIZE, flags)

            elif event.key == pygame.K_F12:
                debug_mode = not debug_mode
                state_word = "ENABLED" if debug_mode else "DISABLED"
                log_output(f"[SYSTEM] Debug view {state_word}. "
                           f"AI traffic is now {'logged to console' if debug_mode else 'not logged'}.",
                           UI.DEBUG)
                print(f"\n[AI-DEBUG] Debug mode {state_word}.")

            elif ctrl and event.key == pygame.K_l:
                if load_game():
                    game_state = "playing"

        if game_state == "setup":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                setup_active_idx = None
                for i, field in enumerate(setup_fields):
                    if field["rect"].collidepoint(event.pos):
                        setup_active_idx = i

                if btn_dice_rect.collidepoint(event.pos):
                    for f in setup_fields:
                        n = random.randint(1, 3)
                        f["text"] = " ".join(random_words(n)).title()

                elif btn_start_rect.collidepoint(event.pos):
                    genre_val = setup_fields[0]["text"].strip()
                    if not genre_val:
                        genre_val = "Fantasy Mystery"

                    noise_dict = {}
                    for dim in SEED_DIMENSIONS:
                        if dim in _NAME_DIMS:
                            noise_dict[dim] = random_name_seed()
                        else:
                            noise_dict[dim] = " ".join(random_words(random.randint(1, 2)))

                    for field in setup_fields[1:]:
                        val = field["text"].strip()
                        if val:
                            noise_dict[field["key"]] = val

                    game_state = "playing"
                    threading.Thread(target=boot_session, args=(genre_val, noise_dict), daemon=True).start()

            elif event.type == pygame.KEYDOWN:
                if setup_active_idx is not None:
                    if event.key == pygame.K_BACKSPACE:
                        setup_fields[setup_active_idx]["text"] = setup_fields[setup_active_idx]["text"][:-1]
                    elif event.unicode.isprintable() and len(setup_fields[setup_active_idx]["text"]) < SETUP_FIELD_MAX_LENGTH:
                        setup_fields[setup_active_idx]["text"] += event.unicode

        elif game_state == "playing":
            if event.type == pygame.MOUSEBUTTONDOWN:
                with state_lock:
                    total = len(all_lines)
                visible = sb_geom["visible"]
                max_scroll = max(0, total - visible)

                if event.button == 1:
                    with state_lock:
                        if dice_state == "wait" and dice_rect.collidepoint(event.pos):
                            dice_state = "roll"
                            dice_timer = 0
                            dice_roll_accumulator = 0.0

                if event.button == 4:
                    scroll_y = min(max_scroll, scroll_y + 2)
                elif event.button == 5:
                    scroll_y = max(0, scroll_y - 2)
                elif event.button == 1 and max_scroll > 0:
                    mx, my = event.pos
                    if (sb_geom["x"] - 4 <= mx <= sb_geom["x"] + sb_geom["w"] + 4
                            and sb_geom["top"] <= my <= sb_geom["top"] + sb_geom["h"]):
                        dragging_scrollbar = True
                        rel = (my - sb_geom["top"]) / sb_geom["h"]
                        scroll_y = int(round((1 - rel) * max_scroll))
                        scroll_y = max(0, min(max_scroll, scroll_y))

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    dragging_scrollbar = False

            elif event.type == pygame.MOUSEMOTION and dragging_scrollbar:
                with state_lock:
                    total = len(all_lines)
                visible = sb_geom["visible"]
                max_scroll = max(0, total - visible)
                if max_scroll > 0:
                    rel = (event.pos[1] - sb_geom["top"]) / sb_geom["h"]
                    scroll_y = int(round((1 - rel) * max_scroll))
                    scroll_y = max(0, min(max_scroll, scroll_y))

            elif event.type == pygame.KEYDOWN:
                mods = pygame.key.get_mods()
                ctrl = mods & pygame.KMOD_CTRL

                if ctrl and event.key == pygame.K_s:
                    save_game()
                elif event.key == pygame.K_UP:
                    with state_lock:
                        total = len(all_lines)
                    scroll_y = min(max(0, total - 1), scroll_y + 2)
                elif event.key == pygame.K_DOWN:
                    scroll_y = max(0, scroll_y - 2)
                elif event.key == pygame.K_RETURN and is_streaming:
                    streaming_index = len(streaming_text_full)
                    streaming_text_current = streaming_text_full
                elif event.key == pygame.K_RETURN and not busy:
                    with state_lock:
                        alive = player_alive
                    cleaned = input_text.strip()
                    meaningful = sum(c.isalnum() for c in cleaned) >= MEANINGFUL_INPUT_MIN_ALNUM
                    if dice_state == "wait":
                        log_output("[The Dungeon Master waits... Click the die to roll your fate!]", (255, 0, 128))
                    elif cleaned and meaningful and client and alive:
                        log_output(f"You: {input_text}", (0, 255, 255))
                        scroll_y = 0
                        threading.Thread(target=run_async_ai_turn, args=(input_text,), daemon=True).start()
                        input_text = ""
                    elif cleaned and not meaningful and alive:
                        log_output("[Type an actual action - what do you do?]", (255, 165, 0))
                    elif not alive:
                        log_output("[The dead take no actions. Ctrl+L to load a save.]", (255, 165, 0))
                elif event.key == pygame.K_BACKSPACE:
                    input_text = input_text[:-1]
                else:
                    if (not ctrl and len(input_text) < INPUT_MAX_LENGTH and event.unicode.isprintable()):
                        input_text += event.unicode

    if game_state == "setup":
        btn_dice_rect, btn_start_rect = draw_setup_screen(
            screen, WINDOW_SIZE, setup_fields, setup_active_idx)

    elif game_state == "playing":
        draw_play_screen(screen, WINDOW_SIZE, _build_render_snapshot(),
                         dice_rect, sb_geom)

    pygame.display.flip()
    clock.tick(TARGET_FPS)

print("[DEBUG] Exiting Pygame loop and cleaning up.")
shutdown_event.set()
dice_event.set()
pygame.quit()
sys.exit()