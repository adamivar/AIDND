import math
import random

import pygame

from config import (
    FONT_MONO, FONT_EMOJI, FONT_DISPLAY,
    FONT_SIZE_NORMAL, FONT_SIZE_BOLD, FONT_SIZE_SMALL,
    FONT_SIZE_HEADER, FONT_SIZE_PARTY, FONT_SIZE_HEARTS,
    FONT_SIZE_DICE_LARGE, FONT_SIZE_DICE_SMALL,
    CHAT_MAX_WIDTH, LINE_SPACING, WRAP_CACHE_MAX,
    DICE_RADIUS, DICE_SHAKE_AMPLITUDE, DICE_ROLL_FRAMES,
    DICE_HOLD_FRAMES, DICE_PULSE_PERIOD_MS,
    CURSOR_BLINK_MS, THINKING_DOT_MS,
    TOOLTIP_WIDTH,
    C_BG_TOP, C_BG_BOTTOM, C_PANEL, C_PANEL_HEADER,
    C_BORDER, C_BORDER_SOFT, C_TEXT, C_TEXT_DIM, C_TEXT_FAINT,
    C_HEALTH, C_HEALTH_TRACK, C_SKILL, C_SKILL_TRACK,
    C_SPELL, C_PARTY, C_INVENTORY, C_ACCENT, C_FATE, C_DEBUG,
    C_OK, C_WARN, C_DANGER,
    PARTY_COLORS as _PARTY_COLORS,
)


if not pygame.font.get_init():
    pygame.font.init()

font            = pygame.font.SysFont(FONT_MONO,  FONT_SIZE_NORMAL)
font_bold       = pygame.font.SysFont(FONT_MONO,  FONT_SIZE_BOLD,   bold=True)
font_chat_bold  = pygame.font.SysFont(FONT_MONO,  FONT_SIZE_NORMAL, bold=True)
font_small      = pygame.font.SysFont(FONT_MONO,  FONT_SIZE_SMALL)
font_header     = pygame.font.SysFont(FONT_MONO,  FONT_SIZE_HEADER, bold=True)
font_party      = pygame.font.SysFont(FONT_EMOJI, FONT_SIZE_PARTY)
font_hearts     = pygame.font.SysFont(FONT_EMOJI, FONT_SIZE_HEARTS)
font_dice_large = pygame.font.SysFont(FONT_DISPLAY, FONT_SIZE_DICE_LARGE)
font_dice_small = pygame.font.SysFont(FONT_DISPLAY, FONT_SIZE_DICE_SMALL)


# ---------------------------------------------------------------------------
# Colour palette  (values live in config.py; this class preserves the
# existing UI.X attribute API used throughout the codebase)
# ---------------------------------------------------------------------------
class UI:
    BG_TOP        = C_BG_TOP
    BG_BOTTOM     = C_BG_BOTTOM
    PANEL         = C_PANEL
    PANEL_HEADER  = C_PANEL_HEADER
    BORDER        = C_BORDER
    BORDER_SOFT   = C_BORDER_SOFT
    TEXT          = C_TEXT
    TEXT_DIM      = C_TEXT_DIM
    TEXT_FAINT    = C_TEXT_FAINT

    HEALTH        = C_HEALTH
    HEALTH_TRACK  = C_HEALTH_TRACK
    SKILL         = C_SKILL
    SKILL_TRACK   = C_SKILL_TRACK
    SPELL         = C_SPELL
    PARTY         = C_PARTY
    INVENTORY     = C_INVENTORY
    ACCENT        = C_ACCENT
    FATE          = C_FATE
    DEBUG         = C_DEBUG

    OK            = C_OK
    WARN          = C_WARN
    DANGER        = C_DANGER

    PARTY_COLORS  = _PARTY_COLORS


# ---------------------------------------------------------------------------
# Background + panel chrome
# ---------------------------------------------------------------------------
_bg_cache = {}


def draw_background(surface):
    size = surface.get_size()
    cached = _bg_cache.get(size)
    if cached is None:
        cached = pygame.Surface(size)
        h = size[1]
        for y in range(h):
            t = y / max(1, h - 1)
            r = int(UI.BG_TOP[0] + (UI.BG_BOTTOM[0] - UI.BG_TOP[0]) * t)
            g = int(UI.BG_TOP[1] + (UI.BG_BOTTOM[1] - UI.BG_TOP[1]) * t)
            b = int(UI.BG_TOP[2] + (UI.BG_BOTTOM[2] - UI.BG_TOP[2]) * t)
            pygame.draw.line(cached, (r, g, b), (0, y), (size[0], y))
        _bg_cache[size] = cached
    surface.blit(cached, (0, 0))


def draw_panel(surface, rect, title=None, accent=UI.ACCENT):
    x, y, w, h = rect
    pygame.draw.rect(surface, UI.PANEL, rect, border_radius=6)
    pygame.draw.rect(surface, UI.BORDER, rect, width=1, border_radius=6)
    if title is None:
        return y + 10
    hdr_h = 26
    pygame.draw.rect(surface, UI.PANEL_HEADER, (x, y, w, hdr_h),
                     border_top_left_radius=6, border_top_right_radius=6)
    pygame.draw.rect(surface, accent, (x, y + 4, 3, hdr_h - 8))
    surface.blit(font_header.render(title.upper(), True, accent),
                 (x + 14, y + 6))
    pygame.draw.line(surface, UI.BORDER_SOFT,
                     (x, y + hdr_h), (x + w, y + hdr_h))
    return y + hdr_h + 10


# ---------------------------------------------------------------------------
# Text sanitising / cleaning
# ---------------------------------------------------------------------------
_REPLACEMENTS = {
    "\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
    "\u2014": "-", "\u2013": "-", "\u2026": "...", "\u2022": "*",
}


def sanitize_text(text):
    for target, sub in _REPLACEMENTS.items():
        text = text.replace(target, sub)
    return "".join(ch for ch in text if ord(ch) < 256)


def clean_name(name):
    kept = []
    for ch in str(name):
        cp = ord(ch)
        if (0x1F000 <= cp <= 0x1FAFF or
                0x2600 <= cp <= 0x27BF or
                0x2190 <= cp <= 0x21FF or
                cp in (0xFE0F, 0x200D) or
                0x1F1E6 <= cp <= 0x1F1FF):
            continue
        kept.append(ch)
    return " ".join("".join(kept).split())


# ---------------------------------------------------------------------------
# Plain text wrapping
# ---------------------------------------------------------------------------
_wrap_cache = {}


def wrap_text(text, max_width, target_font):
    key = (text, max_width, id(target_font))
    cached = _wrap_cache.get(key)
    if cached is not None:
        return list(cached)

    wrapped_lines = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        current_line = ""
        for word in words:
            if not word:
                continue
            test_line = current_line + (" " if current_line else "") + word
            if target_font.size(test_line)[0] < max_width:
                current_line = test_line
            else:
                if current_line:
                    wrapped_lines.append(current_line)
                current_line = word
        wrapped_lines.append(current_line)

    if len(_wrap_cache) > WRAP_CACHE_MAX:
        _wrap_cache.clear()
    _wrap_cache[key] = wrapped_lines
    return list(wrapped_lines)


# ---------------------------------------------------------------------------
# Rich ("styled") text: bold runs + party-name colouring
# ---------------------------------------------------------------------------
# The styled-text helpers need to know each party member's display
# colour. The game module owns the party list, so it registers a small
# lookup callback here rather than ui.py reaching into game state.
_party_color_provider = None


def set_party_color_provider(callback):
    """Register a function returning {lowercased_name_token: (r,g,b)}.

    Called by the game module once at startup. Keeps rendering decoupled
    from the live `party` list.
    """
    global _party_color_provider
    _party_color_provider = callback


def _party_color_lookup():
    if _party_color_provider is None:
        return {}
    try:
        return _party_color_provider() or {}
    except Exception:
        return {}


def _style_runs(paragraph, base_color):
    name_colors = _party_color_lookup()
    runs = []
    parts = paragraph.split("**")
    if len(parts) % 2 == 0 and len(parts) >= 2:
        parts = parts[:-2] + ["**".join(parts[-2:])]
    for i, chunk in enumerate(parts):
        if not chunk:
            continue
        is_bold = (i % 2 == 1)
        token = ""
        token_is_word = None
        buff = []

        def flush():
            if token == "":
                return
            stripped = token.strip(".,!?;:'\"()[]-").lower()
            col = name_colors.get(stripped, base_color)
            buff.append((token, col, is_bold))

        for ch in chunk:
            is_wordch = ch.isalnum() or ch in "'-"
            if token_is_word is None:
                token_is_word = is_wordch
            if is_wordch == token_is_word:
                token += ch
            else:
                flush()
                token = ch
                token_is_word = is_wordch
        flush()
        runs.extend(buff)

    if not runs:
        runs = [("", base_color, False)]
    return runs


def _wrap_runs(runs, max_width, target_font, bold_font):
    lines = []
    cur = []
    cur_w = 0

    def width_of(s, bold):
        f = bold_font if bold else target_font
        return f.size(s)[0]

    atoms = []
    for txt, col, bold in runs:
        piece = ""
        for ch in txt:
            if ch == " ":
                if piece:
                    atoms.append((piece, col, bold))
                    piece = ""
                atoms.append((" ", col, bold))
            else:
                piece += ch
        if piece:
            atoms.append((piece, col, bold))

    for atom, col, bold in atoms:
        w = width_of(atom, bold)
        if atom == " ":
            if cur:
                cur.append((atom, col, bold))
                cur_w += w
            continue
        if cur_w + w > max_width and cur:
            while cur and cur[-1][0] == " ":
                cur.pop()
            lines.append(cur)
            cur = []
            cur_w = 0
        cur.append((atom, col, bold))
        cur_w += w

    if cur:
        while cur and cur[-1][0] == " ":
            cur.pop()
        lines.append(cur)
    return lines if lines else [
        [("", runs[0][1] if runs else (200, 200, 200), False)]]


def build_styled_lines(text, base_color=(220, 220, 220), max_width=CHAT_MAX_WIDTH):
    """Turn a block of text into wrapped, styled line-run lists.

    Returns a list of lines, where each line is a list of
    (segment_text, color, is_bold) tuples - the same shape the renderer
    expects in its line buffer.
    """
    sanitized = sanitize_text(text)
    out = []
    for para in sanitized.split("\n"):
        runs = _style_runs(para, base_color)
        out.extend(_wrap_runs(runs, max_width, font, font_chat_bold))
    return out


def build_plain_lines(text, color=(200, 200, 200), max_width=CHAT_MAX_WIDTH):
    """Wrap text into single-colour, non-bold line-run lists."""
    sanitized = sanitize_text(text)
    lines = wrap_text(sanitized, max_width, font)
    return [[(line, color, False)] for line in lines]


# ---------------------------------------------------------------------------
# Setup screen renderer
# ---------------------------------------------------------------------------
def draw_setup_screen(screen, window_size, setup_fields, setup_active_idx):
    """Render the adventure-configuration screen.

    Mutates each field's ``rect`` so the caller's click handling lines
    up with what's drawn. Returns (btn_dice_rect, btn_start_rect).
    """
    draw_background(screen)

    title = font_dice_large.render("Configure Your Adventure", True, UI.ACCENT)
    screen.blit(title, (window_size[0] // 2 - title.get_width() // 2, 70))

    box_w = 400
    box_h = 40
    start_y = 130
    gap = 55
    center_x = window_size[0] // 2 - box_w // 2

    for i, field in enumerate(setup_fields):
        field["rect"] = pygame.Rect(center_x, start_y + i * gap, box_w, box_h)

        lbl = font_bold.render(field["label"], True, UI.TEXT_DIM)
        screen.blit(lbl, (center_x, start_y + i * gap - 18))

        is_active = (i == setup_active_idx)
        color = UI.ACCENT if is_active else UI.BORDER
        pygame.draw.rect(screen, (20, 22, 28), field["rect"], border_radius=5)
        pygame.draw.rect(screen, color, field["rect"], width=1,
                         border_radius=5)

        cursor = "|" if is_active and (pygame.time.get_ticks() // CURSOR_BLINK_MS) % 2 \
            else ""
        txt = font.render(field["text"] + cursor, True, UI.TEXT)
        screen.blit(txt, (field["rect"].x + 10, field["rect"].y + 12))

    btn_y = start_y + len(setup_fields) * gap + 15
    btn_dice_rect = pygame.Rect(center_x, btn_y, box_w // 2 - 10, 45)
    btn_start_rect = pygame.Rect(center_x + box_w // 2 + 10, btn_y,
                                 box_w // 2 - 10, 45)

    pygame.draw.rect(screen, UI.PANEL, btn_dice_rect, border_radius=5)
    pygame.draw.rect(screen, UI.FATE, btn_dice_rect, width=1, border_radius=5)
    dlbl = font_bold.render("Roll Dice", True, UI.FATE)
    screen.blit(dlbl, (btn_dice_rect.centerx - dlbl.get_width() // 2,
                       btn_dice_rect.centery - dlbl.get_height() // 2))

    pygame.draw.rect(screen, UI.PANEL, btn_start_rect, border_radius=5)
    pygame.draw.rect(screen, UI.OK, btn_start_rect, width=1, border_radius=5)
    slbl = font_bold.render("Start Game", True, UI.OK)
    screen.blit(slbl, (btn_start_rect.centerx - slbl.get_width() // 2,
                       btn_start_rect.centery - slbl.get_height() // 2))

    return btn_dice_rect, btn_start_rect


# ---------------------------------------------------------------------------
# Play screen renderer
# ---------------------------------------------------------------------------
def draw_play_screen(screen, window_size, snap, dice_rect, sb_geom):
    """Render the main game screen from a state snapshot.

    ``snap`` is a plain dict the game module assembles under its state
    lock, so this function never touches live game state. Expected keys:

        lines, hp, max_hp, alive, abilities, inventory, item_desc,
        party, dice_skill, dice_state, dice_current, dice_final,
        dice_modifier, dice_timer, debug_mode, is_ai_thinking,
        is_streaming, scroll_y, input_text, busy,
        streaming_text_current, partial_styler

    ``partial_styler`` is a callable(text, width) -> styled line list,
    used for the live-streaming preview (the game module supplies it so
    the wrapping width stays in sync). ``dice_rect`` and ``sb_geom`` are
    mutated in place so the caller's hit-testing matches the drawing.

    Returns the list of hover-tooltip targets:
        [(pygame.Rect, title, description), ...]
    """
    draw_background(screen)

    lines_snapshot = snap["lines"]
    cur_hp = snap["hp"]
    cur_max = snap["max_hp"]
    alive = snap["alive"]
    abilities_snapshot = snap["abilities"]
    inv_snapshot = snap["inventory"]
    item_desc_snapshot = snap["item_desc"]
    party_snapshot = snap["party"]
    d_skill = snap["dice_skill"]
    d_state = snap["dice_state"]
    d_cur = snap["dice_current"]
    d_final = snap["dice_final"]
    d_timer = snap["dice_timer"]
    debug_mode = snap["debug_mode"]
    is_ai_thinking = snap["is_ai_thinking"]
    is_streaming = snap["is_streaming"]
    scroll_y = snap["scroll_y"]
    input_text = snap["input_text"]
    busy = snap["busy"]
    streaming_text_current = snap["streaming_text_current"]
    partial_styler = snap["partial_styler"]

    line_spacing = LINE_SPACING
    total_lines = len(lines_snapshot)
    hover_targets = []
    mouse_pos = pygame.mouse.get_pos()

    PAD = 14
    LEFT_X, LEFT_W = PAD, 232
    RIGHT_W = 252
    RIGHT_X = window_size[0] - PAD - RIGHT_W
    CENTER_X = LEFT_X + LEFT_W + PAD
    CENTER_W = RIGHT_X - PAD - CENTER_X
    TOP = PAD
    BOTTOM = window_size[1] - PAD
    ROW = 19

    # ---- Party panel (left) ----
    member_row_h = 90 if debug_mode else 44
    party_panel_h = max(70, 36 + len(party_snapshot) * member_row_h)
    party_rect = (LEFT_X, TOP, LEFT_W, party_panel_h)
    ptitle = "Party [DEBUG]" if debug_mode else "Party"
    body_y = draw_panel(screen, party_rect, ptitle,
                        UI.DEBUG if debug_mode else UI.PARTY)
    party_ceiling = TOP + party_panel_h - 8

    for member in party_snapshot:
        if body_y + 30 > party_ceiling:
            break
        emoji = member.get('emoji', '\U0001F610')
        screen.blit(font_party.render(f"{emoji}  {member['name']}",
                                      True, UI.TEXT), (LEFT_X + 14, body_y))
        php = max(0, min(5, member.get("hp", 5)))
        hearts = "\u2665" * php + "\u2661" * (5 - php)
        screen.blit(font_party.render(hearts, True, UI.HEALTH),
                    (LEFT_X + 14, body_y + 18))

        if debug_mode:
            trait_line = (f"{member.get('mbti', '?')} | "
                          f"{member.get('alignment', '?')}")
            screen.blit(font_small.render(trait_line, True, UI.DEBUG),
                        (LEFT_X + 14, body_y + 36))

            flaw_str = member.get('flaw', '') or '—'
            screen.blit(font_small.render(f"Flaw: {flaw_str}", True, UI.WARN),
                        (LEFT_X + 14, body_y + 50))

            ll_str   = member.get('love_language', '') or '—'
            partner  = "\u2665 Partner" if member.get('is_partner') else "Not partner"
            screen.blit(font_small.render(f"{ll_str}  |  {partner}", True, UI.FATE),
                        (LEFT_X + 14, body_y + 64))

        desc = member.get('desc', '') or "No description available."
        if debug_mode:
            partner_tag = "YES \u2665" if member.get('is_partner') else "No"
            desc = (f"MBTI: {member.get('mbti', '?')}\n"
                    f"Alignment: {member.get('alignment', '?')}\n"
                    f"Flaw: {member.get('flaw', '—')}\n"
                    f"Love Language: {member.get('love_language', '—')}\n"
                    f"Romantic Partner: {partner_tag}\n"
                    f"Public: {member.get('public_motive', '')}\n"
                    f"Secret: {member.get('secret_motive', '')}\n"
                    f"{desc}")
        hover_targets.append((
            pygame.Rect(LEFT_X, body_y, LEFT_W, member_row_h - 8),
            member['name'],
            desc,
        ))
        body_y += member_row_h

    # ---- Inventory panel (left) ----
    inv_top = TOP + party_panel_h + PAD
    inv_rect = (LEFT_X, inv_top, LEFT_W, BOTTOM - inv_top)
    body_y = draw_panel(screen, inv_rect, "Inventory", UI.INVENTORY)
    inv_ceiling = BOTTOM - 10
    hidden_inv = 0
    if not inv_snapshot:
        screen.blit(font_small.render("(empty)", True, UI.TEXT_FAINT),
                    (LEFT_X + 14, body_y))
    for i, (item, qty) in enumerate(inv_snapshot):
        if body_y + 18 > inv_ceiling:
            hidden_inv = len(inv_snapshot) - i
            break
        screen.blit(font.render(item, True, UI.TEXT), (LEFT_X + 14, body_y))
        qty_s = font_small.render(f"x{qty}", True, UI.INVENTORY)
        screen.blit(qty_s,
                    (LEFT_X + LEFT_W - 14 - qty_s.get_width(), body_y + 1))
        desc = item_desc_snapshot.get(item, "No description logged.")
        hover_targets.append((pygame.Rect(LEFT_X, body_y, LEFT_W, ROW),
                              item, desc))
        body_y += ROW + 3
    if hidden_inv > 0 and body_y < inv_ceiling:
        screen.blit(font_small.render(f"+{hidden_inv} more...", True,
                                      UI.TEXT_FAINT), (LEFT_X + 14, body_y))

    # ---- Chronicle / chat panel (center) ----
    STATUS_H = 30
    INPUT_H = 38
    FOOTER_H = 20
    chat_panel_h = (BOTTOM - TOP) - STATUS_H - INPUT_H - FOOTER_H - (PAD * 3)
    chat_rect = (CENTER_X, TOP, CENTER_W, chat_panel_h)
    chat_body_y = draw_panel(screen, chat_rect, "Chronicle", UI.ACCENT)

    text_x = CENTER_X + 16
    text_w = CENTER_W - 32 - 12
    chat_top = chat_body_y
    chat_bottom = TOP + chat_panel_h - 12
    chat_h = chat_bottom - chat_top
    max_visible = max(1, chat_h // line_spacing)
    sb_geom["visible"] = max_visible

    reserved = 0
    if is_streaming and scroll_y == 0:
        reserved = min(max_visible - 1,
                       len(partial_styler(streaming_text_current, text_w)))
    visible_committed = max_visible - reserved

    start_idx = max(0, total_lines - visible_committed - scroll_y)
    end_idx = min(total_lines, start_idx + visible_committed)

    draw_y = chat_top
    for idx in range(start_idx, end_idx):
        line_runs = lines_snapshot[idx]
        rx = text_x
        for seg_txt, seg_col, seg_bold in line_runs:
            if not seg_txt:
                continue
            seg_font = font_chat_bold if seg_bold else font
            surf = seg_font.render(seg_txt, True, seg_col)
            screen.blit(surf, (rx, draw_y))
            rx += surf.get_width()
        draw_y += line_spacing

    if total_lines > max_visible:
        sb_w = 6
        sb_x = CENTER_X + CENTER_W - 12
        sb_top, sb_h = chat_top, chat_h
        sb_geom["x"], sb_geom["w"] = sb_x, sb_w
        sb_geom["top"], sb_geom["h"] = sb_top, sb_h
        pygame.draw.rect(screen, UI.BORDER_SOFT,
                         (sb_x, sb_top, sb_w, sb_h), border_radius=3)
        thumb_h = max(24, int(sb_h * max_visible / total_lines))
        max_scroll = total_lines - max_visible
        frac_from_bottom = scroll_y / max_scroll if max_scroll else 0
        thumb_y = sb_top + int((sb_h - thumb_h) * (1 - frac_from_bottom))
        at_bottom = scroll_y == 0
        thumb_color = UI.BORDER if at_bottom else UI.ACCENT
        pygame.draw.rect(screen, thumb_color,
                         (sb_x, thumb_y, sb_w, thumb_h), border_radius=3)

    if is_streaming and scroll_y == 0:
        preview = partial_styler(streaming_text_current, text_w)
        s_y = draw_y
        max_fit = max(1, (chat_bottom - s_y) // line_spacing)
        if len(preview) > max_fit:
            preview = preview[-max_fit:]
        for line_runs in preview:
            if s_y + line_spacing > chat_bottom:
                break
            rx = text_x
            for seg_txt, seg_col, seg_bold in line_runs:
                if not seg_txt:
                    continue
                seg_font = font_chat_bold if seg_bold else font
                surf = seg_font.render(seg_txt, True, seg_col)
                screen.blit(surf, (rx, s_y))
                rx += surf.get_width()
            s_y += line_spacing

    if scroll_y > 0:
        hint = font_small.render("new text below - scroll down", True,
                                 UI.WARN)
        hx = CENTER_X + (CENTER_W - hint.get_width()) // 2
        screen.blit(hint, (hx, TOP + chat_panel_h - 18))

    # ---- Status bar (center) ----
    status_y = TOP + chat_panel_h + PAD
    status_rect = (CENTER_X, status_y, CENTER_W, STATUS_H)
    if not alive:
        st_text, st_col = "YOU HAVE FALLEN", UI.DANGER
    elif d_state == "wait":
        st_text, st_col = "FATE HANGS IN THE BALANCE - ROLL THE DIE", UI.FATE
    elif is_ai_thinking:
        dots = "." * (1 + (pygame.time.get_ticks() // THINKING_DOT_MS) % 3)
        st_text, st_col = f"The Dungeon Master is thinking{dots}", UI.WARN
    elif is_streaming:
        st_text, st_col = "Narrating... (Enter to skip)", UI.ACCENT
    else:
        st_text, st_col = "Ready - awaiting your action", UI.OK
    pygame.draw.rect(screen, UI.PANEL, status_rect, border_radius=5)
    pygame.draw.rect(screen, st_col, status_rect, width=1, border_radius=5)
    pygame.draw.circle(screen, st_col,
                       (CENTER_X + 16, status_y + STATUS_H // 2), 4)
    screen.blit(font_bold.render(st_text, True, st_col),
                (CENTER_X + 30, status_y + 7))

    # ---- Input box (center) ----
    input_y = status_y + STATUS_H + PAD
    input_rect = (CENTER_X, input_y, CENTER_W, INPUT_H)
    can_type = not busy and alive and d_state != "wait"
    in_border = UI.ACCENT if can_type else UI.BORDER
    pygame.draw.rect(screen, (20, 22, 28), input_rect, border_radius=5)
    pygame.draw.rect(screen, in_border, input_rect, width=1, border_radius=5)
    if not alive:
        in_text, in_col = "press Ctrl+L to load a save", UI.TEXT_FAINT
    elif not can_type:
        in_text, in_col = "...", UI.TEXT_FAINT
    else:
        cursor = "|" if (pygame.time.get_ticks() // CURSOR_BLINK_MS) % 2 else ""
        in_text, in_col = input_text + cursor, UI.TEXT
    screen.blit(font_bold.render(">", True, UI.ACCENT),
                (CENTER_X + 14, input_y + 11))
    screen.blit(font.render(in_text, True, in_col),
                (CENTER_X + 32, input_y + 11))

    # ---- Footer (center) ----
    footer_y = input_y + INPUT_H + 6
    screen.blit(font_small.render(
        "F11 Fullscreen   \u00b7   F12 Debug   \u00b7   Ctrl+S Save   \u00b7"
        "   Ctrl+L Load   \u00b7   Enter Skip   \u00b7   Scroll",
        True, UI.TEXT_FAINT), (CENTER_X, footer_y))

    # ---- Health panel (right) ----
    right_x = RIGHT_X
    right_w = RIGHT_W
    inner_x = right_x + 14

    hp_h = 64
    hp_rect = (right_x, TOP, right_w, hp_h)
    by = draw_panel(screen, hp_rect, "Health", UI.HEALTH)
    php = max(0, min(cur_max, cur_hp))
    hearts = "\u2665 " * php + "\u2661 " * (cur_max - php)
    screen.blit(font_hearts.render(hearts.strip(), True, UI.HEALTH),
                (inner_x, by + 2))
    hp_label = font_small.render(f"{cur_hp} / {cur_max}", True, UI.TEXT_DIM)
    screen.blit(hp_label,
                (right_x + right_w - 14 - hp_label.get_width(), by + 8))

    # ---- Abilities panel (right) ----
    ab_top = TOP + hp_h + PAD
    fate_h = 118
    ab_h = BOTTOM - fate_h - PAD - ab_top
    ab_rect = (right_x, ab_top, right_w, ab_h)
    by = draw_panel(screen, ab_rect, "Abilities", UI.SPELL)
    ab_ceiling = ab_top + ab_h - 24

    hidden_abs = 0
    if not abilities_snapshot:
        screen.blit(font_small.render("(none)", True, UI.TEXT_FAINT),
                    (inner_x, by))
    for i, (ab_name, ab_data) in enumerate(abilities_snapshot.items()):
        if by + 22 > ab_ceiling:
            hidden_abs = len(abilities_snapshot) - i
            break

        is_active = ab_data.get("type") == "active"
        cd = ab_data.get("cooldown", 0)

        pygame.draw.circle(screen, UI.SPELL if is_active else UI.SKILL,
                           (inner_x + 3, by + 8), 3)

        color = UI.TEXT_FAINT if cd > 0 else UI.TEXT
        screen.blit(font.render(ab_name, True, color), (inner_x + 14, by))

        if is_active and cd > 0:
            cd_s = font_small.render(f"(Cd: {cd})", True, UI.TEXT_FAINT)
            screen.blit(cd_s,
                        (right_x + right_w - 14 - cd_s.get_width(), by + 1))

        hover_targets.append((pygame.Rect(right_x, by, right_w, 20),
                              ab_name,
                              ab_data.get("desc", "")
                              or "No description available."))
        by += 24

    if hidden_abs > 0 and by < ab_ceiling:
        screen.blit(font_small.render(f"+{hidden_abs} more...", True,
                                      UI.TEXT_FAINT), (inner_x, by))
        by += 18
    screen.blit(font_small.render("hover for details", True, UI.TEXT_FAINT),
                (inner_x, ab_top + ab_h - 22))

    # ---- Fate roll panel (right) ----
    slot_y = BOTTOM - fate_h
    fate_rect = (right_x, slot_y, right_w, fate_h)
    fate_accent = UI.FATE if d_state != "idle" else UI.BORDER
    draw_panel(screen, fate_rect, "Fate Roll", fate_accent)
    screen.blit(font_small.render(f"Ability: {d_skill}", True, UI.TEXT_DIM),
                (inner_x, slot_y + 32))

    dice_rect.update(right_x + right_w - 96, slot_y + 22, 84, 84)

    if d_state != "idle":
        cx, cy = dice_rect.center
        d_radius = DICE_RADIUS

        if d_state == "roll":
            shake = int(DICE_SHAKE_AMPLITUDE * (1.0 - (d_timer / DICE_ROLL_FRAMES)))
            if shake > 0:
                cx += random.randint(-shake, shake)
                cy += random.randint(-shake, shake)

        points = []
        for j in range(6):
            angle = math.pi / 3 * j - math.pi / 2
            points.append((cx + d_radius * math.cos(angle),
                           cy + d_radius * math.sin(angle)))

        pygame.draw.polygon(screen, (0, 255, 255), points, 2)
        pygame.draw.line(screen, (0, 255, 255), points[1], points[3], 1)
        pygame.draw.line(screen, (0, 255, 255), points[3], points[5], 1)
        pygame.draw.line(screen, (0, 255, 255), points[5], points[1], 1)
        pygame.draw.line(screen, (0, 255, 255), (cx, cy), points[0], 1)
        pygame.draw.line(screen, (0, 255, 255), (cx, cy), points[2], 1)
        pygame.draw.line(screen, (0, 255, 255), (cx, cy), points[4], 1)

        if d_state == "wait":
            pulse = abs(math.sin(pygame.time.get_ticks() / DICE_PULSE_PERIOD_MS)) * 255
            click_txt = font_bold.render("CLICK", True,
                                         (0, int(pulse), int(pulse)))
            to_roll_txt = font_bold.render("TO ROLL", True,
                                           (0, int(pulse), int(pulse)))
            screen.blit(click_txt,
                        (cx - click_txt.get_width() // 2, cy - 15))
            screen.blit(to_roll_txt,
                        (cx - to_roll_txt.get_width() // 2, cy + 2))

        elif d_state == "roll":
            num_txt = font_dice_large.render(f"{d_cur}", True,
                                             (255, 255, 255))
            screen.blit(num_txt, (cx - num_txt.get_width() // 2,
                                  cy - num_txt.get_height() // 2))

        elif d_state in ["base", "mod", "done"]:
            if d_final == 20:
                base_color = (0, 255, 0)
            elif d_final == 1:
                base_color = (255, 50, 50)
            else:
                base_color = (255, 255, 255)

            num_txt = font_dice_large.render(f"{d_final}", True, base_color)
            screen.blit(num_txt, (cx - num_txt.get_width() // 2,
                                  cy - num_txt.get_height() // 2))

            if d_state in ["mod", "done"]:
                if d_final == 20:
                    crit_txt = font_bold.render("CRITICAL SUCCESS", True,
                                                UI.OK)
                    screen.blit(crit_txt, (inner_x, slot_y + 80))
                elif d_final == 1:
                    crit_txt = font_bold.render("CRITICAL FAILURE", True,
                                                UI.DANGER)
                    screen.blit(crit_txt, (inner_x, slot_y + 80))
                else:
                    tot_txt = font_bold.render(f"Total: {d_final}", True,
                                               UI.OK)
                    screen.blit(tot_txt, (inner_x, slot_y + 80))
    else:
        cx, cy = dice_rect.center
        d_radius = DICE_RADIUS
        points = []
        for j in range(6):
            angle = math.pi / 3 * j - math.pi / 2
            points.append((cx + d_radius * math.cos(angle),
                           cy + d_radius * math.sin(angle)))
        pygame.draw.polygon(screen, (40, 60, 60), points, 2)
        num_txt = font_dice_large.render("20", True, (40, 60, 60))
        screen.blit(num_txt, (cx - num_txt.get_width() // 2,
                              cy - num_txt.get_height() // 2))

    # ---- Debug banner ----
    if debug_mode:
        banner = font_bold.render(
            "DEBUG VIEW ACTIVE - hidden info shown - AI traffic in console",
            True, UI.DEBUG)
        bw = banner.get_width() + 20
        bx = CENTER_X + (CENTER_W - bw) // 2
        pygame.draw.rect(screen, (40, 28, 8),
                         (bx, TOP + 2, bw, 20), border_radius=4)
        screen.blit(banner, (bx + 10, TOP + 4))

    # ---- Hover tooltips ----
    for rect, tip_title, tip_desc in hover_targets:
        if not rect.collidepoint(mouse_pos):
            continue
        tip_w = TOOLTIP_WIDTH
        wrapped = wrap_text(sanitize_text(tip_desc), tip_w - 20, font)
        title_surf = font_bold.render(sanitize_text(tip_title), True,
                                      UI.ACCENT)
        box_h = 12 + 20 + len(wrapped) * 16 + 10
        box_w = max(tip_w, title_surf.get_width() + 20)

        bx = mouse_pos[0] - box_w - 14
        by = mouse_pos[1] + 12
        if bx < 10:
            bx = mouse_pos[0] + 14
        if by + box_h > window_size[1] - 10:
            by = window_size[1] - 10 - box_h
        if by < 10:
            by = 10

        shadow = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 90))
        screen.blit(shadow, (bx + 3, by + 3))
        pygame.draw.rect(screen, (18, 20, 26), (bx, by, box_w, box_h),
                         border_radius=6)
        pygame.draw.rect(screen, UI.ACCENT, (bx, by, box_w, box_h),
                         width=1, border_radius=6)
        screen.blit(title_surf, (bx + 10, by + 8))
        pygame.draw.line(screen, UI.BORDER_SOFT,
                         (bx + 10, by + 27), (bx + box_w - 10, by + 27))
        ty = by + 32
        for tline in wrapped:
            screen.blit(font.render(tline, True, UI.TEXT), (bx + 10, ty))
            ty += 16
        break

    return hover_targets