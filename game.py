# =============================================================================
# Chuck-A-Luck Wheel Simulator 
# A sophisticated Pygame application simulating a casino-style prize wheel.
#
# This version features a fully procedural wheel graphic, meaning the entire
# wheel, including dice, metalwork, and realistic felt textures, is drawn
# with code. This eliminates the need for external image files and ensures
# a crisp, high-quality look at any screen resolution.
#
# Key Features:
# - High-detail, anti-aliased procedural wheel with felt/baize textures.
# - Advanced 2.5D star with gradients, shadows, and brushed metal effects.
# - Physics-based spinning with smooth easing functions for acceleration/deceleration.
# - Dynamic pointer animation that reacts to the wheel's pegs.
# - Pulsing highlight on the winning segment after a spin.
# - MQTT client for integration with a wireless hardware button.
# - On-screen UI for game stats, payout odds, and spin history.
# - Test mode for manually selecting wheel outcomes.
#
# Controls:
# - SPACE:      Spin the wheel.
# - S:          Toggle between the game screen and the full stats screen.
# - P:          (P)opulate stats by running a silent simulation of 45 spins.
# - T:          Toggle test mode (use Left/Right arrows to select).
# - Q / ESC:    Quit the application.
# =============================================================================

# ========= IMPORTS =========
import sys
import os
import random
import math
import pygame
import paho.mqtt.client as mqtt # For wireless button communication

# =============================================================================
# --- CONFIGURATION ---
# This section contains all primary tunable parameters for the game.
# =============================================================================

# --- ASSETS ---
LOGO_IMAGE_PATH = "logo.png"     # File path for the logo on the game screen.
CLICK_SOUND     = "tick.wav"     # Sound file for the peg tick sound during spin.

# --- DISPLAY & RESOLUTION ---
FULLSCREEN = True      # Set to True to run in fullscreen, False for a window.
FPS        = 120       # Target frames per second for smooth animation.
MARGIN_PX  = 20        # Minimum space between the wheel and the edge of the window.

# --- WHEEL RENDERING QUALITY ---
# This factor increases the internal render resolution of the wheel for anti-aliasing.
# Higher values result in a sharper wheel but require more memory and processing power.
# A value of 4 or 5 is recommended for 1080p and 4K displays.
WHEEL_SCALE_FACTOR = 2

# This is a safety limit to prevent crashes on very high-resolution displays (e.g., 4K/8K).
# It caps the maximum size of the internal surface used to draw the wheel.
# 8192 is a safe limit for most modern graphics cards.
MAX_RENDER_DIAMETER = 8192

# --- WHEEL & SPIN PHYSICS ---
NUM_PEGS            = 54      # Must match the length of WHEEL_RESULTS.
MIN_SPINS           = 4       # Minimum number of full rotations for a spin. 4 default
MAX_SPINS           = 8       # Maximum number of full rotations for a spin. 8 default
MIN_SPIN_TIME_SEC   = 30    # Minimum duration for the main spin animation. 28 default
MAX_SPIN_TIME_SEC   = 38    # Maximum duration for the main spin animation. 38 default 

# --- ANIMATION FEEL ---
WIND_UP_ANGLE_DEG   = 100.0   # How far (in degrees) the wheel winds back before spinning.
WIND_UP_TIME_SEC    = 3.0     # The duration of the wind-up animation.
SETTLE_WOBBLE_DEG   = 1.8     # The max angle of the wobble effect as the wheel settles.
SETTLE_WOBBLE_START = 0.75    # When to start the wobble (0.75 = during the last 25% of the spin).
POINTER_JIGGLE_DURATION_SEC = 0.25 # How long the pointer jiggle animation lasts.
POINTER_JIGGLE_STRENGTH_PX  = 8    # How much the pointer moves vertically.

# --- FONTS ---
# You can change these to any font installed on your system.
FONT_TITLE    = "Arial Black"
FONT_RESULT   = "Arial Black"
FONT_HISTORY  = "Arial"
FONT_STATS    = "Consolas"
FONT_DEBUG    = "Arial Bold"

# Central dictionary for all font sizes used in the game UI.
FONT_SIZES = {
    "title": 80,
    "result": 120,
    "result_title": 97,
    "history": 40,
    "history_title": 70,
    "stats_title": 40,
    "stats_total_spins": 48,
    "payout_title": 40,
    "payout_header": 24,
    "payout_body": 24,
    "main_stats_title": 30,
    "main_stats_header": 26,
    "main_stats_body": 26,
    "full_stats_title": 36,
    "full_stats_header": 30,
    "full_stats_body": 25,
    "debug": 70
}


# --- COLORS ---
# Colors used throughout the UI and the procedural wheel generation.
COLOR_BLACK         = (0, 0, 0)
COLOR_WHITE         = (255, 255, 255)
COLOR_RED           = (200, 0, 0)
COLOR_GREEN         = (0, 200, 0)
COLOR_CASINO_GREEN  = (0, 100, 0)
COLOR_DARK_GREY     = (50, 50, 50)
COLOR_MID_GREY      = (120, 120, 120)
COLOR_LIGHT_GREY    = (170, 170, 170)
COLOR_SILVER        = (192, 192, 192)
COLOR_GOLD          = (255, 215, 0)
COLOR_TITLE         = (138, 43, 226) # Purple for "Chuck-A-Luck" title

# New colors for the visually distinct pegs next to special segments.
COLOR_PEG_BLACK_DARK  = (10, 10, 10)
COLOR_PEG_BLACK_LIGHT = (40, 40, 40)
COLOR_PEG_GREEN_DARK  = (0, 80, 0)
COLOR_PEG_GREEN_LIGHT = (0, 150, 0)


# =============================================================================
# --- WHEEL DATA ---
# This list defines the outcome for each of the 54 segments on the wheel.
# The order corresponds to the segments, starting at 0 degrees (right) and
# moving counter-clockwise. Special segments have been rearranged for balance.
# (0,0,0) = House Wins, (9,9,9) = Spin Again
# =============================================================================
WHEEL_RESULTS = [
    (4, 5, 6),
    (1, 2, 4), 
    (5, 5, 5), 
    (3, 6, 6), 
    (5, 5, 6), 
    (4, 4, 4),
    (1, 2, 3), 
    (3, 3, 4), 
    (1, 4, 5), 
    (6, 6, 6), 
    (1, 1, 4), 
    (1, 2, 6),
    (9, 9, 9),   # Spin Again
    (1, 2, 4), 
    (5, 5, 5), 
    (3, 6, 6), 
    (1, 3, 4), 
    (2, 5, 6), 
    (1, 4, 6),
    (0, 0, 0),   # House Win
    (1, 2, 3), 
    (3, 3, 4), 
    (2, 3, 4), 
    (1, 4, 5), 
    (1, 1, 2), 
    (3, 3, 3),
    (9, 9, 9),   # Spin Again
    (4, 5, 6), 
    (1, 2, 2), 
    (2, 4, 5), 
    (2, 3, 6), 
    (5, 5, 6), 
    (1, 4, 6),
    (3, 3, 4), 
    (2, 2, 2), 
    (2, 3, 6), 
    (1, 1, 2), 
    (3, 4, 6), 
    (4, 5, 6),
    (9, 9, 9),   # Spin Again
    (1, 2, 2), 
    (5, 5, 5), 
    (3, 6, 6), 
    (1, 1, 1), 
    (5, 5, 6),   
    (1, 4, 6),
    (0, 0, 0),   # House Win    
    (1, 2, 3), 
    (3, 3, 4), 
    (2, 2, 2), 
    (4, 4, 5), 
    (2, 3, 6), 
    (1, 3, 5),
    (9, 9, 9)    # Spin Again
]


# ========= EASING =========
# Functions that control the "feel" of animations by describing speed changes over time.
# They take a progress value 'x' from 0.0 to 1.0 and return a modified value.

def ease_out_cubic(x: float) -> float:
    """Cubic easing: starts fast, slows down to a stop. Used for the main spin."""
    return 1 - pow(1 - x, 3)

def ease_in_out_quad(x: float) -> float:
    """Quadratic easing: starts slow, speeds up, then slows down. Used for wind-up."""
    return 2 * x * x if x < 0.5 else 1 - pow(-2 * x + 2, 2) / 2

def ease_out_back(x: float) -> float:
    """
    "Back" easing creates an overshoot effect, like a bounce.
    Used for the pointer jiggle animation.
    """
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * pow(x - 1, 3) + c1 * pow(x - 1, 2)

def end_wobble(u: float) -> float:
    """Calculates a dampened sine wave to create a "wobble" effect as the wheel settles."""
    if SETTLE_WOBBLE_DEG <= 0 or u < SETTLE_WOBBLE_START:
        return 0.0
    t = (u - SETTLE_WOBBLE_START) / (1 - SETTLE_WOBBLE_START)
    return SETTLE_WOBBLE_DEG * math.sin(math.pi * t) * math.exp(-3.0 * t)

# ========= UI HELPERS =========
# Utility functions to simplify common Pygame drawing and UI creation.

def blit_center(surface, img, center):
    """Draws an image onto a surface, with the image's center at the specified coordinate."""
    surface.blit(img, img.get_rect(center=center))

def draw_animated_pointer(surface, cx, cy, radius, anim_progress):
    """Draws the triangular pointer, applying an animated 'jiggle' based on anim_progress."""
    # INVERTED ANIMATION LOGIC:
    # The animation now represents the pointer FALLING back to its resting state.
    # We use (1.0 - anim_progress) to invert the easing curve.
    # When a peg hits, anim_progress resets to 0.0.
    # (1.0 - 0.0) = 1.0. ease_out_back(1) = 1. Offset is at max (pointer is kicked UP).
    # As anim_progress goes to 1.0, (1.0 - anim_progress) goes to 0.
    # ease_out_back(0) = 0. Offset is 0 (pointer is at REST).
    y_offset = POINTER_JIGGLE_STRENGTH_PX * ease_out_back(1.0 - anim_progress)

    # Base position for the pointer is now the lower, "resting" position.
    # The animation subtracts from this, raising the pointer UPWARDS.
    y_top = cy - radius - 20 + POINTER_JIGGLE_STRENGTH_PX - y_offset
    half_w = max(15, radius // 25)
    base_y = y_top - 15
    tip_y  = y_top + 20

    # Define the polygon points for the pointer
    tip, left, right = (cx, tip_y), (cx - half_w, base_y), (cx + half_w, base_y)

    # Draw the pointer's fill and outline
    pygame.draw.polygon(surface, (255, 0, 0), (tip, left, right))
    pygame.draw.polygon(surface, COLOR_WHITE, (tip, left, right), width=3)

def create_payout_table():
    """Creates a pre-rendered Pygame surface for the payout and odds table."""
    font_title  = pygame.font.SysFont("Arial Bold", FONT_SIZES["payout_title"])
    font_header = pygame.font.SysFont(FONT_STATS, FONT_SIZES["payout_header"], bold=True)
    font_body   = pygame.font.SysFont(FONT_STATS, FONT_SIZES["payout_body"])
    table_data = [
        ("TRIPLE", "3 to 1", 1), ("DOUBLE", "2 to 1", 5), ("SINGLE", "1 to 1", 13),
        ("GREEN", "Push", 4), ("BLACK", "Lose Bet", 31)
    ]
    title_surf  = font_title.render("PAYOUTS & ODDS", True, COLOR_GOLD)
    header_text = f"{'Outcome':<10} {'Payout':<14} {'Odds':<10}"
    header_surf = font_header.render(header_text, True, (200, 200, 200))
    body_surfs  = [font_body.render(f"{o:<10} {p:<14} {f'{pr} in 54':<10}", True, (255, 255, 255)) for o, p, pr in table_data]
    # Calculate surface size based on rendered text
    width  = header_surf.get_width() + 40
    height = title_surf.get_height() + header_surf.get_height() + sum(s.get_height() for s in body_surfs) + 30
    table_surf = pygame.Surface((width, height), pygame.SRCALPHA)
    # Draw background and border
    bg_rect = table_surf.get_rect()
    pygame.draw.rect(table_surf, (30, 30, 30, 200), bg_rect, border_radius=10)
    pygame.draw.rect(table_surf, (255, 215, 0, 220), bg_rect, width=2, border_radius=10)
    # Blit text elements onto the surface
    y = 10
    blit_center(table_surf, title_surf, (width/2, y + title_surf.get_height()/2)); y += title_surf.get_height() + 5
    blit_center(table_surf, header_surf,(width/2, y + header_surf.get_height()/2)); y += header_surf.get_height()
    for s in body_surfs:
        blit_center(table_surf, s, (width/2, y + s.get_height()/2)); y += s.get_height()
    return table_surf

def create_main_screen_stats_table(title, spin_counts, total_dice, total_spins):
    """Creates a compact stats table for the main game screen (e.g., 'Last 5 spins')."""
    font_title  = pygame.font.SysFont("Arial Bold", FONT_SIZES["main_stats_title"])
    font_header = pygame.font.SysFont(FONT_STATS, FONT_SIZES["main_stats_header"], bold=True)
    font_body   = pygame.font.SysFont(FONT_STATS, FONT_SIZES["main_stats_body"])
    title_surf  = font_title.render(title, True, (0, 200, 0))
    header_surf = font_header.render("Result: Hits | Percent", True, (200, 200, 200))
    lines = []
    for i in range(1,7):
        hits = spin_counts.get(i,0); pct = (hits/total_dice*100) if total_dice>0 else 0
        lines.append(font_body.render(f"{i:<6}: {hits:>3} | {pct:5.1f}%", True, (255,255,255)))
    lines.append(font_body.render("-"*23, True, (100,100,100)))
    for label, color in [("House Wins",(255,100,100)), ("Spin Again",(200,200,200))]:
        hits = spin_counts.get(label,0); pct = (hits/total_spins*100) if total_spins>0 else 0
        lines.append(font_body.render(f"{label:<11}: {hits:>2} | {pct:5.1f}%", True, color))
    width  = header_surf.get_width() + 40
    height = title_surf.get_height() + header_surf.get_height() + sum(l.get_height() for l in lines) + 30
    table_surf = pygame.Surface((width, height), pygame.SRCALPHA)
    bg_rect = table_surf.get_rect()
    pygame.draw.rect(table_surf, (30,30,30,200), bg_rect, border_radius=10)
    pygame.draw.rect(table_surf, (0,200,0,220), bg_rect, width=2, border_radius=10)
    y = 10
    blit_center(table_surf, title_surf, (width/2, y + title_surf.get_height()/2)); y += title_surf.get_height() + 5
    blit_center(table_surf, header_surf,(width/2, y + header_surf.get_height()/2)); y += header_surf.get_height() + 5
    for l in lines:
        blit_center(table_surf, l, (width/2, y + l.get_height()/2)); y += l.get_height()
    return table_surf

def create_full_stats_table_surface(title, spin_counts, total_dice, total_spins, combo_counts):
    """Creates the larger, more detailed stats table for the dedicated statistics screen."""
    font_title  = pygame.font.SysFont("Arial Bold", FONT_SIZES["full_stats_title"])
    font_header = pygame.font.SysFont(FONT_STATS, FONT_SIZES["full_stats_header"], bold=True)
    font_body   = pygame.font.SysFont(FONT_STATS, FONT_SIZES["full_stats_body"])
    title_surf  = font_title.render(title, True, (0,200,0))
    header_surf = font_header.render("Result: Hits | Percent", True, (200,200,200))
    lines=[]
    for i in range(1,7):
        hits = spin_counts.get(i,0); pct = (hits/total_dice*100) if total_dice>0 else 0
        lines.append(font_body.render(f"{i:<6}: {hits:>4} | {pct:5.1f}%", True, (255,255,255)))
    lines.append(font_body.render("-"*22, True, (100,100,100)))
    for label,color in [("House Wins",(255,100,100)),("Spin Again",(200,200,200))]:
        hits = spin_counts.get(label,0); pct = (hits/total_spins*100) if total_spins>0 else 0
        lines.append(font_body.render(f"{label:<11}: {hits:>4} | {pct:5.1f}%", True, color))
    if combo_counts:
        lines.append(font_body.render("-"*22, True, (100,100,100)))
        total_combos = sum(combo_counts.values())
        for label,color in [("Singles",(255,255,255)),("Doubles",(255,255,100)),("Triples",(100,255,100))]:
            hits = combo_counts.get(label,0); pct = (hits/total_combos*100) if total_combos>0 else 0
            lines.append(font_body.render(f"{label:<8}: {hits:>4} | {pct:5.1f}%", True, color))
    width  = header_surf.get_width() + 60
    height = title_surf.get_height() + header_surf.get_height() + sum(l.get_height() for l in lines) + 40
    table_surf = pygame.Surface((width, height), pygame.SRCALPHA)
    bg_rect = table_surf.get_rect()
    pygame.draw.rect(table_surf, (30,30,30,200), bg_rect, border_radius=10)
    pygame.draw.rect(table_surf, (0,200,0,220), bg_rect, width=2, border_radius=10)
    y = 15
    blit_center(table_surf, title_surf, (width/2, y + title_surf.get_height()/2)); y += title_surf.get_height() + 5
    blit_center(table_surf, header_surf,(width/2, y + header_surf.get_height()/2)); y += header_surf.get_height() + 5
    for l in lines:
        blit_center(table_surf, l, (width/2, y + l.get_height()/2)); y += l.get_height()
    return table_surf

# ========= FELT / BAIZE TEXTURE HELPERS =========
# This suite of functions procedurally generates a realistic felt-like texture.
# It builds the texture in layers: grain, fibers, weave, and vignette.

def _circle_mask(size, center, radius):
    """Creates a circular mask surface used to clip other surfaces."""
    surf = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.circle(surf, (255,255,255,255), center, radius)
    return surf

def _apply_alpha_mask(src, mask):
    """Applies a mask to a source surface, making areas outside the mask transparent."""
    out = pygame.Surface(src.get_size(), pygame.SRCALPHA)
    out.blit(src, (0,0))
    out.blit(mask, (0,0), special_flags=pygame.BLEND_RGBA_MULT)
    return out

def _felt_grain(size, base_color, density=0.98, alpha=14, seed=0):
    """Generates fine, random pixel noise to simulate felt grain."""
    random.seed(seed)
    w, h = size
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    n = int(w*h*0.0075*density)
    br, bg, bb = base_color
    for _ in range(n):
        x = random.randrange(w); y = random.randrange(h)
        dv = random.randint(-10, 10) # brightness variation
        col = (max(0,min(255, br+dv)), max(0,min(255,bg+dv)), max(0,min(255,bb+dv)), alpha)
        surf.fill(col, (x, y, 1, 1))
    return surf

def _felt_fibers(size, base_color, angle_deg=25, length=10, thickness=1, count_scale=1.0, alpha=18, seed=1):
    """Draws thin, semi-transparent lines to simulate felt fibers."""
    random.seed(seed)
    w, h = size
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    count = int((w*h)/260 * count_scale)
    ax = math.cos(math.radians(angle_deg))
    ay = math.sin(math.radians(angle_deg))
    br, bg, bb = base_color
    stroke = (max(0, br-18), max(0, bg-18), max(0, bb-18), alpha) # slightly darker fibers
    for _ in range(count):
        cx = random.randrange(w); cy = random.randrange(h)
        dx = int(length*ax); dy = int(length*ay)
        pygame.draw.line(surf, stroke, (cx-dx, cy-dy), (cx+dx, cy+dy), thickness)
    return surf

def _soft_vignette(size, center, radius, strength=0.12):
    """Creates a soft, dark radial gradient to simulate depth and shadow."""
    w, h = size
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    steps = max(8, int(radius*0.2))
    for i in range(steps):
        t = i/(steps-1)
        r = int(radius*(t))
        a = int(255 * (t**2) * strength) # Alpha increases quadratically for a soft edge
        pygame.draw.circle(surf, (0,0,0,a), center, r)
    return surf

def make_felt_patch(size, center, radius, base_color, seed=0):
    """Builds a complete felt/baize texture patch by layering multiple effects."""
    patch = pygame.Surface(size, pygame.SRCALPHA)
    # 1. Base color fill
    pygame.draw.circle(patch, (*base_color, 255), center, radius)

    # 2. Fine grain noise
    grain = _felt_grain(size, base_color, density=0.58, alpha=14, seed=seed)
    grain = _apply_alpha_mask(grain, _circle_mask(size, center, radius))
    patch.blit(grain, (0,0))

    # 3. Fibers (two passes at different angles for realism)
    fib_len = max(8, radius//18)
    fib1 = _felt_fibers(size, base_color, angle_deg=22,  length=fib_len, thickness=1, count_scale=1.0, alpha=16, seed=seed+11)
    fib1 = _apply_alpha_mask(fib1, _circle_mask(size, center, radius))
    patch.blit(fib1, (0,0))

    fib2 = _felt_fibers(size, base_color, angle_deg=112, length=fib_len, thickness=1, count_scale=0.8, alpha=12, seed=seed+23)
    fib2 = _apply_alpha_mask(fib2, _circle_mask(size, center, radius))
    patch.blit(fib2, (0,0))

    # 4. Subtle cross-hatch weave pattern
    weave = pygame.Surface(size, pygame.SRCALPHA)
    br, bg, bb = base_color
    weave_col = (max(0, br-10), max(0, bg-10), max(0, bb-10), 10) # Very subtle, dark weave
    step = max(6, radius//22)
    cx, cy = center
    for x in range(cx-radius, cx+radius, step): pygame.draw.line(weave, weave_col, (x, cy-radius), (x, cy+radius), 1)
    for y in range(cy-radius, cy+radius, step): pygame.draw.line(weave, weave_col, (cx-radius, y), (cx+radius, y), 1)
    weave = _apply_alpha_mask(weave, _circle_mask(size, center, radius))
    patch.blit(weave, (0,0))

    # 5. Vignette for depth and 'pile' shadow
    vig = _soft_vignette(size, center, radius, strength=0.12)
    vig = _apply_alpha_mask(vig, _circle_mask(size, center, radius))
    patch.blit(vig, (0,0))

    return patch

# ========= STAR RENDERING (two-layer with depth) =========
# This suite of functions procedurally generates a high-detail, 2.5D metallic star.
# It uses layers, gradients, masks, and generated textures to create a sense of depth and realism.

def _regular_star_points(center, r_outer, r_inner, num_points=10, rotation_deg=-90):
    """Calculates the vertex points for a standard n-pointed star."""
    cx, cy = center
    pts = []
    steps = num_points * 2
    for i in range(steps):
        r = r_outer if i % 2 == 0 else r_inner # Alternate between outer and inner radius
        ang = math.radians(i * (360.0 / steps) + rotation_deg)
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return pts

def _polygon(surface, color, points, width=0):
    """A simple wrapper for pygame.draw.polygon for convenience."""
    pygame.draw.polygon(surface, color, points, width)

def _mask_from_polygon(size, points):
    """Creates a mask surface from a list of polygon points."""
    m = pygame.Surface(size, pygame.SRCALPHA)
    _polygon(m, (255,255,255,255), points)
    return m

def _apply_mask_rgba(src_surf, mask_surf):
    """Applies a mask to a source, similar to _apply_alpha_mask but with a different name."""
    out = pygame.Surface(src_surf.get_size(), pygame.SRCALPHA)
    out.blit(src_surf, (0,0))
    out.blit(mask_surf, (0,0), special_flags=pygame.BLEND_RGBA_MULT)
    return out

def _radial_gradient(size, center, r_outer, inner_color, outer_color):
    """Draws a radial gradient by drawing concentric circles of changing color."""
    w,h = size
    grad = pygame.Surface((w,h), pygame.SRCALPHA)
    max_r = max(1, int(r_outer))
    for i in range(max_r, -1, -1):
        t = i/max_r # progress from outer (0.0) to inner (1.0)
        # Linear interpolation for each color channel
        r = int(outer_color[0] + (inner_color[0]-outer_color[0])*(1-t))
        g = int(outer_color[1] + (inner_color[1]-outer_color[1])*(1-t))
        b = int(outer_color[2] + (inner_color[2]-outer_color[2])*(1-t))
        a = int(outer_color[3] + (inner_color[3]-outer_color[3])*(1-t))
        pygame.draw.circle(grad, (r,g,b,a), center, i)
    return grad

def _brushed_metal(size, strength=26, alpha=55, seed=777):
    """Generates a texture of horizontal lines to simulate brushed metal."""
    random.seed(seed)
    w,h = size
    tex = pygame.Surface((w,h), pygame.SRCALPHA)
    for y in range(0, h, max(1, h//160)):
        brightness = 185 + random.randint(-strength, strength)
        brightness = max(95, min(235, brightness)) # Clamp brightness
        pygame.draw.line(tex, (brightness,brightness,brightness,alpha), (0,y), (w,y))
    return tex

def _soft_glow_star(size, center, r_outer, color=(255, 235, 120, 90)):
    """Creates a soft, diffuse glow effect using layered circles of decreasing alpha."""
    glow = pygame.Surface(size, pygame.SRCALPHA)
    steps = 20
    for i in range(steps):
        t = i/(steps-1)
        r = int(r_outer * (1.20 + 0.45*t)) # Glow extends beyond the star
        a = max(0, int(color[3] * (1.0 - t))) # Alpha fades to zero
        pygame.draw.circle(glow, (color[0],color[1],color[2],a), center, r)
    return glow

def _offset(points, dx, dy):
    """Returns a new list of points, each offset by dx, dy."""
    return [(x+dx, y+dy) for x,y in points]

def draw_two_layer_star(target, center, r_outer_base, r_inner_base, scale_factor=1):
    """
    Draws a complete, high-detail, two-layer star onto the target surface.
    It simulates 2.5D by layering a larger, darker "back" star and a smaller,
    brighter "front" star, with shadows and bevels.
    """
    cx, cy = center
    R = int(r_outer_base * 1.6) # Create a local surface large enough to contain effects
    size = (R*2, R*2)
    local_center = (R, R)

    # --- 1. BACK STAR (DARKER, LARGER) ---
    back_points = _regular_star_points(local_center, r_outer_base, r_inner_base)
    back_mask   = _mask_from_polygon(size, back_points)

    # Gradient base for the back star
    back_grad = _radial_gradient(size, local_center, r_outer_base,
                                 inner_color=(160,160,160,255), outer_color=(40,40,40,255))
    back_grad  = _apply_mask_rgba(back_grad, back_mask)

    # Brushed metal texture on top of the gradient
    back_metal = _brushed_metal(size, strength=22, alpha=45, seed=515)
    back_metal = _apply_mask_rgba(back_metal, back_mask)
    back_grad.blit(back_metal, (0,0))

    # Bevel effect using offset light/dark outlines
    back_bevel = pygame.Surface(size, pygame.SRCALPHA)
    thick = max(2, int(4*scale_factor))
    _polygon(back_bevel, (255,255,255,110), _offset(back_points, -2*scale_factor, -2*scale_factor), width=thick) # Highlight
    _polygon(back_bevel, (0,0,0,140),       _offset(back_points,  2*scale_factor,  2*scale_factor), width=thick) # Shadow
    back_bevel = _apply_mask_rgba(back_bevel, back_mask)
    back_grad.blit(back_bevel, (0,0))

    # Inset polygon to create a sharp inner edge
    back_inset = _regular_star_points(local_center, r_outer_base - 6*scale_factor, r_inner_base - 6*scale_factor)
    pygame.draw.polygon(back_grad, (60,60,60,220), back_inset)
    pygame.draw.polygon(back_grad, (255,255,255,60), back_inset, width=max(1, int(2*scale_factor)))

    # Blit the finished back star onto the main wheel surface
    target.blit(back_grad, (cx - R, cy - R))

    # --- 2. DROP SHADOW ---
    shadow = pygame.Surface(size, pygame.SRCALPHA)
    _polygon(shadow, (0,0,0,130), _offset(back_points, 5*scale_factor, 5*scale_factor))
    target.blit(shadow, (cx - R, cy - R))

    # --- 3. SOFT GLOW ---
    target.blit(_soft_glow_star(size, local_center, r_outer_base*0.92, color=(255, 235, 150, 90)), (cx - R, cy - R))

    # --- 4. FRONT STAR (LIGHTER, SMALLER) ---
    front_scale = 0.90 # Front star is 90% the size of the back one
    r_outer_front = r_outer_base * front_scale
    r_inner_front = r_inner_base * front_scale

    front_points = _regular_star_points(local_center, r_outer_front, r_inner_front)
    front_mask   = _mask_from_polygon(size, front_points)

    # Gradient, metal, and bevels for the front star (similar to back star but with lighter colors)
    front_grad = _radial_gradient(size, local_center, r_outer_front,
                                  inner_color=(255,245,205,255), outer_color=(120,90,25,255))
    front_grad = _apply_mask_rgba(front_grad, front_mask)

    front_metal = _brushed_metal(size, strength=28, alpha=55, seed=913)
    front_metal = _apply_mask_rgba(front_metal, front_mask)
    front_grad.blit(front_metal, (0,0))

    thick_f = max(2, int(4*scale_factor))
    front_bevel = pygame.Surface(size, pygame.SRCALPHA)
    _polygon(front_bevel, (255,255,255,150), _offset(front_points, -2*scale_factor, -2*scale_factor), width=thick_f)
    _polygon(front_bevel, (0,0,0,130),       _offset(front_points,  2*scale_factor,  2*scale_factor), width=thick_f)
    front_bevel = _apply_mask_rgba(front_bevel, front_mask)
    front_grad.blit(front_bevel, (0,0))

    # Blit the finished front star
    target.blit(front_grad, (cx - R, cy - R))

    # --- 5. CENTER HUB ---
    hub_r = int(r_outer_front * 0.22)
    pygame.draw.circle(target, (235,235,235), (cx,cy), hub_r)
    pygame.draw.circle(target, (50,50,50), (cx,cy), hub_r, width=max(2, int(3*scale_factor)))
    bolt_r = max(3, int(5*scale_factor))
    bolt_ring = hub_r * 0.62
    for i in range(6):
        ang = math.radians(i*60)
        bx = int(cx + bolt_ring*math.cos(ang))
        by = int(cy + bolt_ring*math.sin(ang))
        pygame.draw.circle(target, (40,40,40), (bx,by), bolt_r)
        pygame.draw.circle(target, (200,200,200), (bx,by), max(1, bolt_r-1))

# ========= GAME =========
class Game:
    """Encapsulates all game state and logic."""
    def __init__(self):
        """Initializes Pygame, the display, loads/creates assets, and sets up game state."""
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        self.click_channel = pygame.mixer.Channel(0)
        self.clock = pygame.time.Clock()

        # --- Display Setup ---
        flags = 0
        if FULLSCREEN:
            flags |= pygame.FULLSCREEN
            info = pygame.display.Info()
            self.WINDOW_SIZE = (info.current_w, info.current_h)
        else:
            self.WINDOW_SIZE = (1200, 800)
        self.screen = pygame.display.set_mode(self.WINDOW_SIZE, flags)
        pygame.display.set_caption("Chuck-A-Luck — v6.0 High-Res & Configurable — P:Sim 45 | S:Stats | T:Test | Space:Spin | Q/Esc:Quit")

        # --- Geometry, Assets, and State Initialization ---
        self.cx, self.cy = self.WINDOW_SIZE[0]//2, self.WINDOW_SIZE[1]//2
        self.seg_angle = 360.0/NUM_PEGS
        self._load_assets()
        self._init_fonts()
        self._prerender_text()

        self.payout_table_surf = create_payout_table()

        # --- Animation State ---
        self.animation_state = "idle"  # "idle", "winding_up", "spinning"
        self.animation_progress = 0.0  # Progress (0.0 to 1.0) within the current state
        self.current_angle = 0.0
        self.rest_angle = 0.0
        self.final_angle_base = 0.0
        self.current_spin_duration = 0.0

        # --- Game Logic State ---
        self.current_screen = "game"  # "game" or "stats"
        self.last_tick_idx = None
        self.result_display_text = ""
        self.test_mode = False
        self.test_index = 0
        self.winning_segment_index = None # New state to track the winner for highlighting

        # --- Visual Effect State ---
        self.rainbow_hue = 0
        self.flash_timer = 0
        self.pointer_anim_progress = 1.0 # New state for pointer animation (1.0 = finished)

        # --- Statistics Tracking ---
        self.results_history_full = []
        self.spin_counts_full = {i:0 for i in range(1,7)}
        self.spin_counts_full.update({"House Wins":0,"Spin Again":0})
        self.combo_counts_full = {"Singles":0,"Doubles":0,"Triples":0}
        self.total_dice_rolled_full = 0
        self.total_spins_full = 0
        self.last_5_stats_surf = None
        self._update_on_screen_stats()

        self._setup_mqtt()

    def draw_die(self, surface, value, center_pos, size, angle_deg, bg_color):
        """Draws a single die face, rotated to point radially outward."""
        die_surface = pygame.Surface((size, size), pygame.SRCALPHA)
        size = int(size)
        pygame.draw.rect(die_surface, bg_color, (0,0,size,size), border_radius=int(size*0.15))
        if bg_color != COLOR_BLACK:
            pygame.draw.rect(die_surface, COLOR_BLACK, (0,0,size,size), width=max(1,int(size*0.05)), border_radius=int(size*0.15))
        margin = size * 0.2
        c, r = size/2, size*0.12
        dots = {1:[(c,c)], 2:[(margin,margin),(size-margin,size-margin)], 3:[(margin,margin),(c,c),(size-margin,size-margin)], 4:[(margin,margin),(size-margin,margin),(margin,size-margin),(size-margin,size-margin)], 5:[(margin,margin),(size-margin,margin),(c,c),(margin,size-margin),(size-margin,size-margin)], 6:[(margin,margin),(size-margin,margin),(margin,c),(size-margin,c),(margin,size-margin),(size-margin,size-margin)]}
        if value in dots:
            for pos in dots[value]: pygame.draw.circle(die_surface, COLOR_BLACK, pos, r)
        rotated = pygame.transform.rotate(die_surface, -angle_deg)
        surface.blit(rotated, rotated.get_rect(center=center_pos))

    def create_wheel_surface(self):
        """
        Constructs the entire wheel graphic procedurally.
        This function is called once at startup to create the wheel surface.
        It uses a high-resolution canvas (scale_factor) and then downsamples
        for anti-aliasing.
        """
        # --- High-Resolution Surface Calculation with Safety Cap ---
        # 1. Calculate the ideal diameter for the high-res internal surface.
        ideal_scaled_diameter = self.wheel_radius * 2 * WHEEL_SCALE_FACTOR

        # 2. Check if the ideal size exceeds our safety limit.
        if ideal_scaled_diameter > MAX_RENDER_DIAMETER:
            # If it's too big, cap the diameter and recalculate the scale factor.
            print(f"Warning: Ideal render size ({ideal_scaled_diameter}px) exceeds max limit.")
            print(f"Capping render diameter to {MAX_RENDER_DIAMETER}px to prevent errors.")
            scaled_diameter = MAX_RENDER_DIAMETER
            scale_factor = scaled_diameter / (self.wheel_radius * 2)
        else:
            # If it's safe, use the ideal size.
            scaled_diameter = ideal_scaled_diameter
            scale_factor = WHEEL_SCALE_FACTOR

        scaled_radius = scaled_diameter // 2
        wheel_surf    = pygame.Surface((scaled_diameter, scaled_diameter), pygame.SRCALPHA)
        wheel_center  = (scaled_radius, scaled_radius)
        angle_step    = 360/NUM_PEGS

        # ===== FELT AREAS =====
        # 1. Red outer rim felt
        rim_radius = scaled_radius
        red_base   = (170, 10, 10) # A richer red for better texture readability
        red_felt   = make_felt_patch((scaled_diameter, scaled_diameter), wheel_center, rim_radius, red_base, seed=101)
        wheel_surf.blit(red_felt, (0,0))
        # 2. Black outer border ring (drawn on top of the felt)
        pygame.draw.circle(wheel_surf, COLOR_BLACK, wheel_center, scaled_radius, int(15*scale_factor))

        # 3. Center casino-green felt
        center_radius = int(scaled_radius * 0.55)
        green_base    = (0, 105, 35) # A slightly brighter green for texture
        green_felt    = make_felt_patch((scaled_diameter, scaled_diameter), wheel_center, center_radius, green_base, seed=202)
        wheel_surf.blit(green_felt, (0,0))

        # ===== WHEEL STRUCTURE =====
        # 4. Inner black ring between dice and center hub
        inner_ring_radius = scaled_radius*0.65
        pygame.draw.circle(wheel_surf, COLOR_BLACK, wheel_center, int(inner_ring_radius), width=int(8*scale_factor))

        # 5. Segment dividing lines
        peg_outer_radius = scaled_radius - (8*scale_factor)
        for i in range(NUM_PEGS):
            th = math.radians(i*angle_step)
            x_outer = wheel_center[0] + peg_outer_radius*math.cos(th)
            y_outer = wheel_center[1] + peg_outer_radius*math.sin(th)
            x_inner = wheel_center[0] + inner_ring_radius*math.cos(th)
            y_inner = wheel_center[1] + inner_ring_radius*math.sin(th)
            pygame.draw.line(wheel_surf, COLOR_BLACK, (x_outer,y_outer), (x_inner,y_inner), int(2*scale_factor))

        # ===== DICE & PEGS =====
        # 6. Dice, positioned in three concentric rings
        die_size = int(self.wheel_radius * 0.062 * scale_factor)
        radii = [scaled_radius*0.90, scaled_radius*0.80, scaled_radius*0.70]
        for i in range(NUM_PEGS):
            center_angle_deg = (i*angle_step) + (angle_step/2)
            ang = math.radians(center_angle_deg)
            dice_values = WHEEL_RESULTS[i]
            seg_color = COLOR_WHITE
            if dice_values == (0,0,0): seg_color = COLOR_BLACK
            elif dice_values == (9,9,9): seg_color = COLOR_GREEN
            for j in range(3):
                d = radii[j]
                x = wheel_center[0] + d*math.cos(ang)
                y = wheel_center[1] + d*math.sin(ang)
                ang_to_center = math.degrees(math.atan2(y-wheel_center[1], x-wheel_center[0]))
                self.draw_die(wheel_surf, dice_values[j], (x,y), die_size, ang_to_center+90, seg_color)

        # 7. Peg studs on the dividing lines
        peg_radius = int(self.wheel_radius*0.017) * scale_factor
        peg_ring   = scaled_radius - (8*scale_factor)
        for i in range(NUM_PEGS):
            # --- New Peg Coloring Logic ---
            # Check the segments on either side of the current peg
            left_segment = WHEEL_RESULTS[(i - 1 + NUM_PEGS) % NUM_PEGS]
            right_segment = WHEEL_RESULTS[i]
            
            # Default peg color is metallic grey
            peg_color_dark = COLOR_DARK_GREY
            peg_color_light = COLOR_LIGHT_GREY

            # If adjacent to a "House Win" segment, color the peg black.
            if left_segment == (0,0,0) or right_segment == (0,0,0):
                peg_color_dark = COLOR_PEG_BLACK_DARK
                peg_color_light = COLOR_PEG_BLACK_LIGHT
            # If adjacent to a "Spin Again" segment, color the peg green.
            elif left_segment == (9,9,9) or right_segment == (9,9,9):
                peg_color_dark = COLOR_PEG_GREEN_DARK
                peg_color_light = COLOR_PEG_GREEN_LIGHT
            
            th = math.radians(i*angle_step)
            px = wheel_center[0] + peg_ring*math.cos(th)
            py = wheel_center[1] + peg_ring*math.sin(th)
            pygame.draw.circle(wheel_surf, peg_color_dark, (px,py), peg_radius)
            pygame.draw.circle(wheel_surf, peg_color_light, (px,py), peg_radius - int(2*scale_factor))
            pygame.draw.circle(wheel_surf, COLOR_WHITE,      (px-int(2*scale_factor), py-int(2*scale_factor)), max(1, peg_radius - int(5*scale_factor)))

        # ===== CENTERPIECE =====
        # 8. The high-detail two-layer star
        star_r_outer_back = scaled_radius * 0.52
        star_r_inner_back = scaled_radius * 0.22
        draw_two_layer_star(wheel_surf, wheel_center, star_r_outer_back, star_r_inner_back, scale_factor=scale_factor)

        # 9. Final down-sampling to display size for a smooth, anti-aliased look
        return pygame.transform.smoothscale(wheel_surf, (self.wheel_radius*2, self.wheel_radius*2))

    def _load_assets(self):
        """Determines wheel size and calls the procedural generation function."""
        max_dim = min(self.WINDOW_SIZE) - (MARGIN_PX*2)
        self.wheel_radius = max_dim // 2

        print("Generating dynamic wheel surface...")
        self.wheel_img = self.create_wheel_surface() # This is the key change from loading a PNG
        print("Wheel surface created.")

        self.logo_img = None
        if os.path.exists(LOGO_IMAGE_PATH):
            logo_raw = pygame.image.load(LOGO_IMAGE_PATH).convert_alpha()
            logo_h = 450
            logo_w = int(logo_raw.get_width() * (logo_h / logo_raw.get_height()))
            self.logo_img = pygame.transform.smoothscale(logo_raw, (logo_w, logo_h))

        self.click_sound = None
        if CLICK_SOUND and os.path.exists(CLICK_SOUND):
            try: self.click_sound = pygame.mixer.Sound(CLICK_SOUND)
            except pygame.error as e: print(f"Warning: Could not load sound '{CLICK_SOUND}'. Error: {e}")

    def _init_fonts(self):
        """Initializes all Pygame font objects using names and sizes from the configuration."""
        self.title_font              = pygame.font.SysFont(FONT_TITLE, FONT_SIZES["title"])
        self.result_font             = pygame.font.SysFont(FONT_RESULT, FONT_SIZES["result"])
        self.history_font            = pygame.font.SysFont(FONT_HISTORY, FONT_SIZES["history"])
        self.debug_font              = pygame.font.SysFont(FONT_DEBUG, FONT_SIZES["debug"])
        self.history_title_font      = pygame.font.SysFont(FONT_HISTORY, FONT_SIZES["history_title"], bold=True)
        self.result_title_font       = pygame.font.SysFont(FONT_RESULT, FONT_SIZES["result_title"], bold=True)
        self.stats_screen_title_font = pygame.font.SysFont(FONT_HISTORY, FONT_SIZES["stats_title"])
        self.total_spins_font        = pygame.font.SysFont(FONT_HISTORY, FONT_SIZES["stats_total_spins"], bold=True)

    def _prerender_text(self):
        self.title_text_surf     = self.title_font.render("Chuck-A-Luck", True, COLOR_TITLE)
        self.history_title_surf_5= self.history_title_font.render("Last 5 Results", True, (0, 200, 0))
        self.history_title_surf_45= self.history_title_font.render("Last 45 Results", True, (0, 200, 0))
        self.result_title_surf   = self.result_title_font.render("Winning Number", True, (255, 255, 255))
        self.stats_title_surf    = self.title_font.render("Full Statistics", True, (0, 200, 0))
        self.return_surf         = self.stats_screen_title_font.render("Press 'S' to return to the game", True, (255, 255, 0))

    def run(self):
        print("Ready. Press SPACE to spin or use the wireless button.")
        dt = 0.0 # Delta time (time since last frame)
        running = True
        while running:
            running = self._handle_events()      # Process user input
            self._update_state(dt)               # Update game logic and animation
            self._draw()                         # Render the current frame
            dt = self.clock.tick(FPS) / 1000.0   # Control frame rate
        # --- Shutdown ---
        if self.mqtt_client and self.mqtt_client.is_connected():
            self.mqtt_client.loop_stop()
        pygame.quit()
        sys.exit(0)

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT: return False
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q): return False
                if event.key == pygame.K_s: self.current_screen = "stats" if self.current_screen == "game" else "game"
                if self.current_screen == "game":
                    is_animating = self.animation_state != "idle"
                    if event.key == pygame.K_p and not is_animating: self._run_silent_simulation(45)
                    if event.key == pygame.K_t: self.test_mode = not self.test_mode; self.result_display_text = ""; self.winning_segment_index = None
                    if event.key == pygame.K_SPACE and not is_animating and not self.test_mode: self._start_spin()
                    if self.test_mode:
                        if event.key == pygame.K_RIGHT: self.test_index = (self.test_index + 1) % NUM_PEGS
                        if event.key == pygame.K_LEFT:  self.test_index = (self.test_index - 1 + NUM_PEGS) % NUM_PEGS
        return True

    def _update_state(self, dt):
        if self.current_screen != "game": return
        self.flash_timer += 1

        # --- Update Pointer Animation ---
        # If the pointer animation is in progress, advance it.
        if self.pointer_anim_progress < 1.0:
            self.pointer_anim_progress += dt / POINTER_JIGGLE_DURATION_SEC
            self.pointer_anim_progress = min(1.0, self.pointer_anim_progress) # Clamp to 1.0

        # --- Update Wheel Animation ---
        if self.test_mode:
            self._update_test_mode()
        elif self.animation_state == "winding_up":
            self._update_wind_up(dt)
        elif self.animation_state == "spinning":
            self._update_spin(dt)
        else: # idle
            self.current_angle = self.rest_angle

        # --- Trigger Pointer Animation & Sound ---
        # Play tick sound and trigger pointer jiggle as it passes pegs
        if self.click_sound and self.animation_state != "idle":
            # COORDINATE SYSTEM FIX:
            # The pointer is at the TOP (90 degrees in Pygame's angle system).
            pointer_angle = 90
            normalized_angle = self.current_angle % 360
            angle_under_pointer = (pointer_angle - normalized_angle + 360) % 360
            idx_now = int(angle_under_pointer / self.seg_angle)
            if idx_now != self.last_tick_idx:
                self.click_channel.play(self.click_sound)
                self.last_tick_idx = idx_now
                self.pointer_anim_progress = 0.0 # Reset animation on each tick

    def _update_test_mode(self):
        """Locks the wheel to the selected test position and updates the result text."""
        self.animation_state = "idle"
        target_segment_angle = (self.test_index + 0.5) * self.seg_angle
        
        # CORRECTED ANGLE CALCULATION:
        # To bring a segment at angle `theta` to the pointer at angle `90`,
        # the required clockwise rotation is `theta - 90`.
        final_angle = target_segment_angle - 90
        
        self.current_angle = self.rest_angle = final_angle
        result = WHEEL_RESULTS[self.test_index]
        self.winning_segment_index = self.test_index # Set winner for highlighting
        if result == (0,0,0): self.result_display_text = "House Wins"
        elif result == (9,9,9): self.result_display_text = "Spin Again"
        else: self.result_display_text = f"{result[0]} - {result[1]} - {result[2]}"

    def _update_wind_up(self, dt):
        """Handles the backward wind-up animation."""
        self.animation_progress += dt / WIND_UP_TIME_SEC
        eased_u = ease_in_out_quad(min(1.0, self.animation_progress))
        self.current_angle = self.rest_angle - (WIND_UP_ANGLE_DEG * eased_u)
        if self.animation_progress >= 1.0:
            self.animation_state = "spinning"
            self.animation_progress = 0.0

    def _draw(self):
        """Main drawing function; calls the renderer for the current screen."""
        self.screen.fill((20,20,20))
        if self.current_screen == "game": self._draw_game_screen()
        elif self.current_screen == "stats": self._draw_stats_screen()
        pygame.display.flip()

    def _draw_winning_segment_highlight(self):
        """Draws a pulsing highlight over the winning segment of the wheel."""
        # Only draw if the wheel is idle and there is a winning segment to show.
        if self.winning_segment_index is None or self.animation_state != "idle":
            return

        # COORDINATE SYSTEM FIX:
        # The winning segment is always at the top of the screen under the pointer.
        # The pointer's angle is 90 degrees in Pygame's system (0=right, 90=up).
        center_angle_deg = 90.0

        # Calculate the start and end angles for the arc, spanning one segment width.
        start_angle_deg = center_angle_deg - (self.seg_angle / 2)
        end_angle_deg   = center_angle_deg + (self.seg_angle / 2)

        # Convert degrees to radians for pygame.draw.arc
        start_rad = math.radians(start_angle_deg)
        end_rad   = math.radians(end_angle_deg)

        # Create a surface for the highlight to allow for transparency.
        highlight_surf = pygame.Surface(self.WINDOW_SIZE, pygame.SRCALPHA)
        # The 'width' of the arc is set to be large enough to cover the dice area.
        arc_width = int(self.wheel_radius * 0.35)
        # The rectangle that defines the bounds of the arc.
        bounding_rect = pygame.Rect(self.cx - self.wheel_radius, self.cy - self.wheel_radius, self.wheel_radius*2, self.wheel_radius*2)

        # The highlight pulses using a sine wave based on the flash_timer.
        # This creates a smooth fade in/out effect.
        pulse = (math.sin(self.flash_timer * 0.1) + 1) / 2 # Normalize to 0-1 range
        alpha = 50 + (pulse * 100) # Varies between 50 and 150
        highlight_color = (*COLOR_GOLD, alpha)

        # Draw the arc. Pygame's arc function takes start angle then end angle
        # and draws counter-clockwise from start to end.
        pygame.draw.arc(highlight_surf, highlight_color, bounding_rect, start_rad, end_rad, arc_width)

        # Blit the highlight onto the main screen.
        self.screen.blit(highlight_surf, (0,0))


    def _draw_game_screen(self):
        """Renders all elements for the main game screen."""
        # Draw static UI elements
        self.screen.blit(self.title_text_surf, (30, 20))
        logo_y = 20 + self.title_text_surf.get_height() + 10
        if self.logo_img: self.screen.blit(self.logo_img, (30, logo_y))
        if self.payout_table_surf:
            table_rect = self.payout_table_surf.get_rect(bottomright=(self.WINDOW_SIZE[0]-30, self.WINDOW_SIZE[1]-20))
            self.screen.blit(self.payout_table_surf, table_rect)

        # Draw the rotated wheel
        rotated = pygame.transform.rotozoom(self.wheel_img, -self.current_angle, 1.0)
        blit_center(self.screen, rotated, (self.cx, self.cy))

        # Draw the winning segment highlight ON TOP of the rotated wheel
        self._draw_winning_segment_highlight()

        # Draw the outer ring and animated pointer ON TOP of everything else
        pygame.draw.circle(self.screen, COLOR_BLACK, (self.cx, self.cy), self.wheel_radius + 20, width=6)
        draw_animated_pointer(self.screen, self.cx, self.cy, self.wheel_radius, self.pointer_anim_progress)

        # Draw spin history and stats tables
        history_title_rect = self.history_title_surf_5.get_rect(topright=(self.WINDOW_SIZE[0]-50, 60))
        self.screen.blit(self.history_title_surf_5, history_title_rect)
        y = history_title_rect.bottom + 10
        start_color = pygame.Vector3(255,255,255); end_color = pygame.Vector3(139,0,0)
        short_history = self.results_history_full[:5]
        for i, s in enumerate(short_history):
            t = i/4.0 if len(short_history)>1 else 0
            color = start_color.lerp(end_color, t)
            surf = self.history_font.render(f"{i+1}.  {s}", True, color)
            self.screen.blit(surf, surf.get_rect(topright=(self.WINDOW_SIZE[0]-50, y)))
            y += surf.get_height()
        if self.last_5_stats_surf:
            self.screen.blit(self.last_5_stats_surf, self.last_5_stats_surf.get_rect(topright=(self.WINDOW_SIZE[0]-50, y+20)))

        # Draw the winning result with a rainbow effect
        if self.result_display_text:
            self.rainbow_hue = (self.rainbow_hue + 1) % 360
            rainbow = pygame.Color(0,0,0); rainbow.hsva = (self.rainbow_hue, 100, 100, 100)
            result_surf = self.result_font.render(self.result_display_text, True, rainbow)
            result_rect = result_surf.get_rect(bottomleft=(30, self.WINDOW_SIZE[1]-20))
            self.screen.blit(result_surf, result_rect)
            # Flash the "Winning Number" title
            if (self.flash_timer // 30) % 2 == 0 and not self.test_mode:
                title_rect = self.result_title_surf.get_rect(bottomleft=result_rect.topleft)
                self.screen.blit(self.result_title_surf, title_rect)

        # Draw test mode overlay if active
        if self.test_mode:
            test_mode_surf = self.title_font.render("--- TEST MODE ---", True, (255,255,0))
            self.screen.blit(test_mode_surf, test_mode_surf.get_rect(midbottom=(self.cx, self.WINDOW_SIZE[1]-20)))
            if self.result_display_text:
                pos_surf = self.debug_font.render(f"Position: {self.test_index}", True, (255,255,0))
                result_rect = self.result_font.render(self.result_display_text, True, (0,0,0)).get_rect(bottomleft=(30, self.WINDOW_SIZE[1]-20))
                pos_rect = pos_surf.get_rect(bottomleft=result_rect.topleft)
                self.screen.blit(pos_surf, pos_rect)

    def _draw_stats_screen(self):
        """Renders the full statistics screen."""
        self.screen.blit(self.stats_title_surf, (50, 20))
        full_stats_surf = create_full_stats_table_surface("All-Time Stats", self.spin_counts_full, self.total_dice_rolled_full, self.total_spins_full, self.combo_counts_full)
        self.screen.blit(full_stats_surf, (50, 120))
        history_title_rect = self.history_title_surf_45.get_rect(left=full_stats_surf.get_width()+300, top=40)
        self.screen.blit(self.history_title_surf_45, history_title_rect)
        col_w, per_col = 350, 15
        start_color = pygame.Vector3(255,255,255); end_color = pygame.Vector3(139,0,0)
        for i, s in enumerate(self.results_history_full):
            col, row = i // per_col, i % per_col
            if col > 2: continue
            t = i / (44.0 if len(self.results_history_full)>1 else 1)
            color = start_color.lerp(end_color, t)
            surf = self.history_font.render(f"{i+1}.  {s}", True, color)
            x = history_title_rect.left + (col * col_w)
            y = history_title_rect.bottom + 10 + (row * surf.get_height())
            self.screen.blit(surf, (x, y))
        self.screen.blit(self.return_surf, self.return_surf.get_rect(centerx=self.cx, bottom=self.WINDOW_SIZE[1]-30))
        total_spins_surf = self.total_spins_font.render(f"Total Spins: {self.total_spins_full}", True, (255,255,255))
        self.screen.blit(total_spins_surf, (50, self.WINDOW_SIZE[1]-80))

    def _pick_target(self):
        """Selects a random target segment and calculates the final resting angle for the spin."""
        self.result_display_text = ""
        k = random.randrange(NUM_PEGS)
        target_segment_angle = (k + 0.5) * self.seg_angle
        spins = random.randint(MIN_SPINS, MAX_SPINS)
        
        # CORRECTED ANGLE CALCULATION:
        # Calculate final destination to place the target segment under the 90-degree pointer (TOP).
        final_destination = target_segment_angle - 90
        start_angle = self.rest_angle - WIND_UP_ANGLE_DEG
        # Calculate total rotation needed to get from wind-up start to the final destination over several spins
        total_rotation = (spins * 360) + ((final_destination - (start_angle % 360) + 360) % 360)
        self.final_angle_base = start_angle + total_rotation
        self.last_tick_idx = None

    def _process_spin_result(self, winning_result):
        """Updates all statistics based on a spin result and returns a display string."""
        self.total_spins_full += 1
        uniq = len(set(winning_result))
        if uniq == 1 and winning_result not in [(0,0,0),(9,9,9)]: self.combo_counts_full['Triples'] += 1
        elif uniq == 2: self.combo_counts_full['Doubles'] += 1
        else: self.combo_counts_full['Singles'] += 1
        if winning_result == (0,0,0):
            self.spin_counts_full['House Wins'] += 1; return "House Wins"
        elif winning_result == (9,9,9):
            self.spin_counts_full['Spin Again'] += 1; return "Spin Again"
        else:
            for d in winning_result:
                if 1 <= d <= 6: self.spin_counts_full[d] += 1; self.total_dice_rolled_full += 1
            return f"{winning_result[0]} - {winning_result[1]} - {winning_result[2]}"

    def _run_silent_simulation(self, num_spins):
        """Performs instant spins to populate statistics without animation."""
        print(f"--- Running silent simulation of {num_spins} spins ---")
        for _ in range(num_spins):
            wr = random.choice(WHEEL_RESULTS)
            txt = self._process_spin_result(wr)
            self.results_history_full.insert(0, txt)
        if len(self.results_history_full) > 45: self.results_history_full = self.results_history_full[:45]
        self._update_on_screen_stats()
        print("--- Simulation complete ---")

    def _update_on_screen_stats(self):
        """Calculates stats for the most recent 5 results and renders them to a surface."""
        short = self.results_history_full[:5]
        if not short: self.last_5_stats_surf = None; return
        spin_counts = {i:0 for i in range(1,7)}; spin_counts.update({'House Wins':0, 'Spin Again':0})
        total_dice = 0
        for s in short:
            if s == "House Wins": spin_counts['House Wins'] += 1
            elif s == "Spin Again": spin_counts['Spin Again'] += 1
            else:
                try:
                    dice = [int(d.strip()) for d in s.split("-")];
                    for d in dice:
                        if 1 <= d <= 6: spin_counts[d] += 1; total_dice += 1
                except (ValueError, IndexError): pass
        self.last_5_stats_surf = create_main_screen_stats_table("Last 5 Stats", spin_counts, total_dice, len(short))

    def _setup_mqtt(self):
        """Sets up the MQTT client, defines callbacks, and connects to the broker."""
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_message = self._on_mqtt_message
        try:
            self.mqtt_client.connect("localhost", 1883, 60)
            self.mqtt_client.loop_start() # Starts a background thread for MQTT
        except Exception as e:
            print(f"\n--- MQTT CONNECTION FAILED: {e} --- \nCould not connect to MQTT broker. You can still use keyboard controls.\n")

    def _on_mqtt_connect(self, client, userdata, flags, rc, properties):
        """Callback executed on successful connection to the MQTT broker."""
        if rc == 0:
            print("Connected to MQTT Broker successfully.")
            client.subscribe("wheel/spin") # Subscribe to the button's topic
        else:
            print(f"Failed to connect to MQTT Broker, return code {rc}\n")

    def _on_mqtt_message(self, client, userdata, msg):
        """Callback executed when a message is received from the MQTT broker."""
        if msg.topic == "wheel/spin" and msg.payload.decode() == "pressed":
            if self.animation_state == "idle" and not self.test_mode:
                self._start_spin()

    def _publish_state(self, state):
        """Publishes the current wheel state (e.g., 'spinning') for the button to react to."""
        if self.mqtt_client and self.mqtt_client.is_connected():
            self.mqtt_client.publish("wheel/state", payload=state, qos=0, retain=False)
            print(f"Published state: {state}")

    def _start_spin(self):
        """Initiates the spinning animation sequence."""
        print("Starting spin...")
        self.winning_segment_index = None # Clear previous winner's highlight
        self.animation_state = "winding_up"
        self.animation_progress = 0.0
        self.current_spin_duration = random.uniform(MIN_SPIN_TIME_SEC, MAX_SPIN_TIME_SEC)
        self._pick_target()
        self._publish_state("spinning")

    def _update_spin(self, dt):
        """Handles the main forward spin animation, including the final wobble."""
        self.animation_progress += dt / self.current_spin_duration
        u = min(1.0, self.animation_progress)
        eased_u = ease_out_cubic(u)
        wobble = end_wobble(u)
        spin_start = self.rest_angle - WIND_UP_ANGLE_DEG
        base_angle = spin_start + (self.final_angle_base - spin_start) * eased_u
        self.current_angle = base_angle + wobble
        if u >= 1.0: # Spin has finished
            self.animation_state = "idle"
            self.rest_angle = self.final_angle_base
            # Determine the winning segment index based on the final resting angle
            # The pointer is at the TOP (90 degrees).
            pointer_angle = 90
            normalized = self.rest_angle % 360
            
            # With the corrected target angle calculation in _pick_target, the 180-degree
            # patch is no longer needed. This calculation is now direct and correct.
            under_pointer = (pointer_angle - normalized + 360) % 360
            
            idx = int(under_pointer / self.seg_angle)
            self.winning_segment_index = idx # Store winner for highlighting
            winning_result = WHEEL_RESULTS[idx]
            # Process and display the result
            self.result_display_text = self._process_spin_result(winning_result)
            self.results_history_full.insert(0, self.result_display_text)
            if len(self.results_history_full) > 45:
                self.results_history_full = self.results_history_full[:45]
            self._update_on_screen_stats()
            
            # --- NEW: Send specific state message based on the outcome. ---
            if winning_result == (0, 0, 0):
                self._publish_state("flash_red")
            elif winning_result == (9, 9, 9):
                self._publish_state("flash_green")
            else:
                self._publish_state("flash_white")


# ========= ENTRY POINT =========
if __name__ == "__main__":
    game = Game()
    game.run()

