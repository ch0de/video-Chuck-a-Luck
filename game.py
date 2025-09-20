# =============================================================================
#                  Chuck-A-Luck Wheel Simulator 
#
# A Pygame application that simulates a spinning prize wheel for a
# "Chuck-A-Luck" style game.
#
# Includes an MQTT client to communicate with a wireless
# button controller and a dynamic on-screen payout table.
#
# Controls:
# - SPACE:      Spin the wheel.
# - S:          Toggle between the game screen and the stats screen.
# - P:          (P)opulate stats by running a silent simulation of 45 spins.
# - T:          Toggle test mode (use Left/Right arrows to select).
# - Q / ESC:    Quit the application.
# - Wireless button triggers a spin via MQTT.
# =============================================================================


# ========= IMPORTS =========
# Import necessary libraries for system operations, randomness, math, and Pygame.
import sys
import os
import random
import math
import pygame
# Import the Paho MQTT client library for network communication with the button.
import paho.mqtt.client as mqtt


# ========= CONFIGURATION =========
# This section contains all the tunable parameters for the game's appearance and behavior.

# --- ASSETS ---
WHEEL_IMAGE_PATH = "wheel.png"  # File path for the main spinning wheel image.
LOGO_IMAGE_PATH = "logo.png"     # File path for the logo image displayed on the game screen.
CLICK_SOUND = "tick.wav"    # File path for the sound played as the pointer passes a peg.

# --- DISPLAY ---
FULLSCREEN = True      # Set to True to run in fullscreen, False for a windowed mode.
FPS = 120       # Target frames per second for smooth animation.
MARGIN_PX = 50       # Minimum space (in pixels) between the wheel and the edge of the window.

# --- WHEEL & SPIN PHYSICS ---
NUM_PEGS = 54        # The total number of segments/pegs on the wheel. Must match WHEEL_RESULTS length.
MIN_SPINS = 4         # The minimum number of full rotations for a spin.
MAX_SPINS = 8         # The maximum number of full rotations for a spin.
MIN_SPIN_TIME_SEC = 28.0     # The minimum duration for the main spinning phase.
MAX_SPIN_TIME_SEC = 38.0     # The maximum duration for the main spinning phase.

# --- ANIMATION FEEL ---
WIND_UP_ANGLE_DEG = 100.0    # How far (in degrees) the wheel winds backward before spinning forward.
WIND_UP_TIME_SEC = 3.0      # The duration of the wind-up animation.
SETTLE_WOBBLE_DEG = 1.8      # The maximum angle (in degrees) of the wobble effect as the wheel settles.
SETTLE_WOBBLE_START = 0.75   # When to start the wobble (0.75 = during the last 25% of the spin).

# --- DEBUG ---
SHOW_DEBUG_PEGS = False     # A flag for potential future debugging features (not currently used).


# ========= WHEEL DATA =========
# This list defines the outcome for each of the 54 segments on the wheel.
# The order corresponds to the segments on the image, starting at the 0-degree position
# and moving counter-clockwise.
# (0,0,0) = House Wins, (9,9,9) = Spin Again
WHEEL_RESULTS = [
    (4, 5, 6), (1, 2, 4), (5, 5, 5), (3, 6, 6), (0, 0, 0), (5, 5, 6),
    (4, 4, 4), (1, 2, 3), (3, 3, 4), (9, 9, 9), (1, 4, 5), (6, 6, 6),
    (1, 1, 4), (1, 2, 6), (1, 2, 4), (5, 5, 5), (3, 6, 6), (1, 3, 4),
    (2, 5, 6), (1, 4, 6), (1, 2, 3), (3, 3, 4), (2, 3, 4), (1, 4, 5),
    (9, 9, 9), (1, 1, 2), (3, 3, 3), (4, 5, 6), (1, 2, 2), (2, 4, 5),
    (2, 3, 6), (0, 0, 0), (5, 5, 6), (1, 4, 6), (3, 3, 4), (2, 2, 2),
    (2, 3, 6), (9, 9, 9), (1, 1, 2), (3, 4, 6), (4, 5, 6), (1, 2, 2),
    (5, 5, 5), (3, 6, 6), (1, 1, 1), (5, 5, 6), (1, 4, 6), (1, 2, 3),
    (3, 3, 4), (2, 2, 2), (4, 4, 5), (9, 9, 9), (2, 3, 6), (1, 3, 5)
]


# ========= EASING / MOTION FUNCTIONS =========
# These functions control the "feel" of the animation by describing how its speed changes over time.
# They take a value 'x' (from 0.0 to 1.0, representing progress) and return a modified value.

def ease_out_quint(x: float) -> float:
    """Quintic easing function that starts fast and slows down to a stop."""
    return 1 - pow(1 - x, 5)


def ease_out_cubic(x: float) -> float:
    """Cubic easing function, less aggressive slowdown than quintic. Used for the main spin."""
    return 1 - pow(1 - x, 3)


def ease_in_out_quad(x: float) -> float:
    """Quadratic easing, starts slow, speeds up, then slows down. Used for the wind-up."""
    return 2 * x * x if x < 0.5 else 1 - pow(-2 * x + 2, 2) / 2


def end_wobble(u: float) -> float:
    """Calculates a dampened sine wave to create a "wobble" effect as the wheel settles."""
    # Only activate the wobble in the final phase of the spin
    if SETTLE_WOBBLE_DEG <= 0 or u < SETTLE_WOBBLE_START:
        return 0.0
    # Remap 'u' to a 0-1 range within the wobble phase
    t = (u - SETTLE_WOBBLE_START) / (1 - SETTLE_WOBBLE_START)
    # Calculate wobble using a sine wave that fades out exponentially
    return SETTLE_WOBBLE_DEG * math.sin(math.pi * t) * math.exp(-3.0 * t)


# ========= DRAWING HELPER FUNCTIONS =========
# Utility functions to simplify common Pygame drawing and UI creation operations.

def blit_center(surface, img, center):
    """Draws an image ('img') onto a surface, with the image's center at the specified 'center' coordinate."""
    surface.blit(img, img.get_rect(center=center))


def scale_to_fit_keep_ar(img, max_w, max_h):
    """Scales a Pygame surface to fit within a max width/height while preserving its aspect ratio."""
    w, h = img.get_size()
    scale_factor = min(max_w / w, max_h / h)
    new_size = (max(1, int(w * scale_factor)), max(1, int(h * scale_factor)))
    return pygame.transform.smoothscale(img, new_size)


def draw_pointer_down(surface, cx, cy, radius):
    """Draws the triangular pointer at the top of the wheel."""
    y_top = cy - radius
    half_w = max(12, radius // 20)
    base_y = y_top - 12
    tip_y = y_top + 16
    tip, left, right = (cx, tip_y), (cx - half_w, base_y), (cx + half_w, base_y)
    pygame.draw.polygon(surface, (255, 255, 255), (tip, left, right))
    pygame.draw.polygon(surface, (0, 0, 0), (tip, left, right), width=2)


def create_payout_table():
    """Creates a pre-rendered Pygame surface for the payout and odds table."""
    # Define fonts for the table's title, header, and body text.
    font_title = pygame.font.SysFont("Arial Bold", 40)
    font_header = pygame.font.SysFont("Consolas", 24, bold=True)
    font_body = pygame.font.SysFont("Consolas", 24)

    # Define the static data for the table: Outcome, Payout (as a string), and the number of wheel segments.
    table_data = [
        ("TRIPLE", "3 to 1", 1),
        ("DOUBLE", "2 to 1", 5),
        ("SINGLE", "1 to 1", 13),
        ("GREEN", "Push", 4),      # Corresponds to "Spin Again"
        ("BLACK", "Lose Bet", 31)   # Corresponds to "House Wins" + "No Match"
    ]

    # Render all text elements first to calculate the required size for the table surface.
    title_surf = font_title.render("PAYOUTS & ODDS", True, (255, 215, 0))  # Gold color
    header_text = f"{'Outcome':<10} {'Payout':<14} {'Odds':<10}"
    header_surf = font_header.render(header_text, True, (200, 200, 200))

    body_surfs = []
    for outcome, payout, prob in table_data:
        odds_str = f"{prob} in 54"
        line_text = f"{outcome:<10} {payout:<14} {odds_str:<10}"
        body_surfs.append(font_body.render(line_text, True, (255, 255, 255)))

    # Calculate final surface dimensions based on the rendered text.
    width = header_surf.get_width() + 40
    height = title_surf.get_height() + header_surf.get_height() + sum(s.get_height() for s in body_surfs) + 30
    # Create the main surface with per-pixel alpha for transparency.
    table_surf = pygame.Surface((width, height), pygame.SRCALPHA)
    bg_rect = table_surf.get_rect()

    # Draw the semi-transparent background and a border.
    pygame.draw.rect(table_surf, (30, 30, 30, 200), bg_rect, border_radius=10)
    pygame.draw.rect(table_surf, (255, 215, 0, 220), bg_rect, width=2, border_radius=10)

    # Blit (draw) all the pre-rendered text elements onto the table surface.
    y_pos = 10
    table_surf.blit(title_surf, title_surf.get_rect(centerx=width / 2, top=y_pos))
    y_pos += title_surf.get_height() + 5
    table_surf.blit(header_surf, header_surf.get_rect(centerx=width / 2, top=y_pos))
    y_pos += header_surf.get_height()

    for surf in body_surfs:
        table_surf.blit(surf, surf.get_rect(centerx=width / 2, top=y_pos))
        y_pos += surf.get_height()

    # Return the completed table surface.
    return table_surf


def create_main_screen_stats_table(title, spin_counts, total_dice, total_spins):
    """Creates a compact stats table for the main game screen (Last 5 spins)."""
    font_title = pygame.font.SysFont("Arial Bold", 30)
    font_header = pygame.font.SysFont("Consolas", 26, bold=True)
    font_body = pygame.font.SysFont("Consolas", 26)
    title_surf = font_title.render(title, True, (0, 200, 0))
    header_surf = font_header.render("Result: Hits | Percent", True, (200, 200, 200))

    lines = []
    # Render lines for dice results 1-6.
    for i in range(1, 7):
        hits = spin_counts.get(i, 0)
        percent = (hits / total_dice * 100) if total_dice > 0 else 0
        text = f"{i:<6}: {hits:>3} | {percent:5.1f}%"
        lines.append(font_body.render(text, True, (255, 255, 255)))

    lines.append(font_body.render("-" * 23, True, (100, 100, 100)))

    # Render lines for special results.
    special_results = [("House Wins", (255, 100, 100)), ("Spin Again", (200, 200, 200))]
    for label, color in special_results:
        hits = spin_counts.get(label, 0)
        percent = (hits / total_spins * 100) if total_spins > 0 else 0
        text = f"{label:<11}: {hits:>2} | {percent:5.1f}%"
        lines.append(font_body.render(text, True, color))

    # Create and draw the table surface.
    width = header_surf.get_width() + 40
    height = title_surf.get_height() + header_surf.get_height() + sum(line.get_height() for line in lines) + 30
    table_surf = pygame.Surface((width, height), pygame.SRCALPHA)
    bg_rect = table_surf.get_rect()
    pygame.draw.rect(table_surf, (30, 30, 30, 200), bg_rect, border_radius=10)
    pygame.draw.rect(table_surf, (0, 200, 0, 220), bg_rect, width=2, border_radius=10)

    # Blit text onto the surface.
    y_pos = 10
    table_surf.blit(title_surf, title_surf.get_rect(centerx=width / 2, top=y_pos))
    y_pos += title_surf.get_height() + 5
    table_surf.blit(header_surf, header_surf.get_rect(centerx=width / 2, top=y_pos))
    y_pos += header_surf.get_height() + 5
    for line in lines:
        table_surf.blit(line, line.get_rect(centerx=width / 2, top=y_pos))
        y_pos += line.get_height()
    return table_surf


def create_full_stats_table_surface(title, spin_counts, total_dice, total_spins, combo_counts):
    """Creates the larger, more detailed stats table for the dedicated statistics screen."""
    # This function is similar to the one above but uses larger fonts and includes combo stats.
    # (Implementation is collapsed for brevity as it's repetitive.)
    font_title = pygame.font.SysFont("Arial Bold", 36)
    font_header = pygame.font.SysFont("Consolas", 30, bold=True)
    font_body = pygame.font.SysFont("Consolas", 25)
    title_surf = font_title.render(title, True, (0, 200, 0))
    header_surf = font_header.render("Result: Hits | Percent", True, (200, 200, 200))
    lines = []
    for i in range(1, 7):
        hits, percent = spin_counts.get(i, 0), ((spin_counts.get(i, 0) / total_dice * 100) if total_dice > 0 else 0)
        lines.append(font_body.render(f"{i:<6}: {hits:>4} | {percent:5.1f}%", True, (255, 255, 255)))
    lines.append(font_body.render("-" * 22, True, (100, 100, 100)))
    special_results = [("House Wins", (255, 100, 100)), ("Spin Again", (200, 200, 200))]
    for label, color in special_results:
        hits, percent = spin_counts.get(label, 0), ((spin_counts.get(label, 0) / total_spins * 100) if total_spins > 0 else 0)
        lines.append(font_body.render(f"{label:<11}: {hits:>4} | {percent:5.1f}%", True, color))
    if combo_counts:
        lines.append(font_body.render("-" * 22, True, (100, 100, 100)))
        total_combos = sum(combo_counts.values())
        combo_types = [("Singles", (255, 255, 255)), ("Doubles", (255, 255, 100)), ("Triples", (100, 255, 100))]
        for label, color in combo_types:
            hits, percent = combo_counts.get(label, 0), ((combo_counts.get(label, 0) / total_combos * 100) if total_combos > 0 else 0)
            lines.append(font_body.render(f"{label:<8}: {hits:>4} | {percent:5.1f}%", True, color))
    width = header_surf.get_width() + 60
    height = title_surf.get_height() + header_surf.get_height() + sum(line.get_height() for line in lines) + 40
    table_surf = pygame.Surface((width, height), pygame.SRCALPHA)
    bg_rect = table_surf.get_rect()
    pygame.draw.rect(table_surf, (30, 30, 30, 200), bg_rect, border_radius=10)
    pygame.draw.rect(table_surf, (0, 200, 0, 220), bg_rect, width=2, border_radius=10)
    y_pos = 15
    table_surf.blit(title_surf, title_surf.get_rect(centerx=width / 2, top=y_pos))
    y_pos += title_surf.get_height() + 5
    table_surf.blit(header_surf, header_surf.get_rect(centerx=width / 2, top=y_pos))
    y_pos += header_surf.get_height() + 5
    for line in lines:
        table_surf.blit(line, line.get_rect(centerx=width / 2, top=y_pos))
        y_pos += line.get_height()
    return table_surf


# ========= GAME CLASS =========
# This class encapsulates all the game's state and logic, avoiding global variables
# and making the code cleaner and more maintainable.
class Game:
    def __init__(self):
        """Initializes the entire game, sets up Pygame, loads assets, and prepares game state."""
        # --- Pygame and Sound Initialization ---
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
        pygame.display.set_caption("P=Simulate 45 | S=Stats | T=Test | Space=Spin | Q/Esc=Quit | Listening for Button...")

        # --- Geometry, Assets, and State Initialization ---
        self.cx, self.cy = self.WINDOW_SIZE[0] // 2, self.WINDOW_SIZE[1] // 2
        self.seg_angle = 360.0 / NUM_PEGS
        self._load_assets()
        self._init_fonts()
        self._prerender_text()

        # Create the payout table surface once on startup for performance.
        self.payout_table_surf = create_payout_table()

        # --- Animation State ---
        # A state machine is used for robust animation management.
        self.animation_state = "idle"  # Can be "idle", "winding_up", "spinning"
        self.animation_progress = 0.0  # Tracks progress (0.0 to 1.0) within the current state

        # Wheel angles and spin parameters
        self.current_angle = 0.0
        self.rest_angle = 0.0
        self.final_angle_base = 0.0
        self.current_spin_duration = 0.0

        # --- Game Logic State ---
        self.current_screen = "game"  # Can be "game" or "stats"
        self.last_tick_idx = None
        self.result_display_text = ""
        self.test_mode = False
        self.test_index = 0

        # --- Visual Effect State ---
        self.rainbow_hue = 0
        self.flash_timer = 0

        # --- Statistics Tracking ---
        # All stats are instance variables, not globals.
        self.results_history_full = []
        self.spin_counts_full = {i: 0 for i in range(1, 7)}
        self.spin_counts_full.update({'House Wins': 0, 'Spin Again': 0})
        self.combo_counts_full = {'Singles': 0, 'Doubles': 0, 'Triples': 0}
        self.total_dice_rolled_full = 0
        self.total_spins_full = 0

        # This surface holds the pre-rendered "Last 5" stats table.
        self.last_5_stats_surf = None
        self._update_on_screen_stats()  # Initial generation of the table.

        # Setup the MQTT client to communicate with the wireless button.
        self._setup_mqtt()

    # --- MQTT METHODS ---
    def _setup_mqtt(self):
        """Sets up the MQTT client, defines callbacks, and connects to the broker."""
        # Use the newer callback API version for clarity.
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        # Assign functions to be called on connection and message events.
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_message = self._on_mqtt_message
        try:
            # Connect to the broker. "localhost" works because the broker is on the same Pi.
            self.mqtt_client.connect("localhost", 1883, 60)
            # loop_start() begins a background thread to handle MQTT messages, so it doesn't block the game loop.
            self.mqtt_client.loop_start()
        except Exception as e:
            # Handle cases where the broker isn't running, so the game doesn't crash.
            print(f"\n--- MQTT CONNECTION FAILED: {e} ---")
            print("Could not connect to MQTT broker. Is Mosquitto installed and running?")
            print("You can still use keyboard controls.\n")

    def _on_mqtt_connect(self, client, userdata, flags, rc, properties):
        """Callback function that is executed when the client successfully connects to the MQTT broker."""
        if rc == 0:
            print("Connected to MQTT Broker successfully.")
            # Subscribe to the topic the button will publish to.
            client.subscribe("wheel/spin")
        else:
            print(f"Failed to connect to MQTT Broker, return code {rc}\n")

    def _on_mqtt_message(self, client, userdata, msg):
        """Callback function that is executed when a message is received on a subscribed topic."""
        # Check if the message is the expected one from our button.
        if msg.topic == "wheel/spin" and msg.payload.decode() == "pressed":
            # Only start a new spin if one is not already in progress.
            if self.animation_state == "idle" and not self.test_mode:
                self._start_spin()

    def _publish_state(self, state):
        """Publishes the current wheel state for the button to react to."""
        # Check if the client is valid and connected before trying to publish.
        if self.mqtt_client and self.mqtt_client.is_connected():
            self.mqtt_client.publish("wheel/state", payload=state, qos=0, retain=False)
            print(f"Published state: {state}")

    # --- GAME LOGIC METHODS ---
    def _start_spin(self):
        """Initiates the spinning animation sequence and notifies the button."""
        print("Starting spin...")
        self.animation_state = "winding_up"
        self.animation_progress = 0.0
        # Choose a random duration for this spin from the configured range.
        self.current_spin_duration = random.uniform(MIN_SPIN_TIME_SEC, MAX_SPIN_TIME_SEC)
        # Determine the final landing position for the wheel.
        self._pick_target()
        # Publish the 'spinning' state to the MQTT broker so the button's LEDs can react.
        self._publish_state("spinning")

    def _update_spin(self, dt):
        """Handles the main forward spin animation, including the final wobble."""
        # Update the animation progress based on delta time (dt) for smooth, frame-rate independent motion.
        self.animation_progress += dt / self.current_spin_duration
        u = min(1.0, self.animation_progress)  # Clamp progress to a max of 1.0
        eased_u = ease_out_cubic(u)            # Apply easing to make the slowdown feel natural.
        wobble = end_wobble(u)                 # Calculate any end-of-spin wobble effect.

        # Interpolate the angle from the start to the end position based on the eased progress.
        spin_start_angle = self.rest_angle - WIND_UP_ANGLE_DEG
        base_angle = spin_start_angle + (self.final_angle_base - spin_start_angle) * eased_u
        self.current_angle = base_angle + wobble  # Apply the wobble to the base angle.

        # When the spin is complete, process the result.
        if u >= 1.0:
            self.animation_state = "idle"
            self.rest_angle = self.final_angle_base
            # Determine the winning segment index based on the final angle.
            a = (self.final_angle_base % 360.0) / self.seg_angle
            k_between = round(a - 0.5) % NUM_PEGS
            # Get the result from the data list and update stats.
            winning_result = WHEEL_RESULTS[k_between]
            self.result_display_text = self._process_spin_result(winning_result)
            self.results_history_full.insert(0, self.result_display_text)
            if len(self.results_history_full) > 45: self.results_history_full = self.results_history_full[:45]
            self._update_on_screen_stats()
            # Publish the 'flashing' state so the button's LEDs can react.
            self._publish_state("flashing")

    # --- DRAWING METHODS ---
    def _draw_game_screen(self):
        """Renders all elements for the main game screen."""
        # Draw the main title text.
        self.screen.blit(self.title_text_surf, (30, 20))

        # Calculate position for the logo and draw it if it exists.
        logo_y = 20 + self.title_text_surf.get_height() + 10
        if self.logo_img:
            self.screen.blit(self.logo_img, (30, logo_y))

        # Draw the payout table in the bottom-right corner.
        if self.payout_table_surf:
            # get_rect() with a keyword argument (e.g., bottomright) is a convenient way to position surfaces.
            table_rect = self.payout_table_surf.get_rect(
                bottomright=(self.WINDOW_SIZE[0] - 30, self.WINDOW_SIZE[1] - 20)
            )
            self.screen.blit(self.payout_table_surf, table_rect)

        # Draw the main spinning wheel.
        rotated = pygame.transform.rotozoom(self.wheel_img, -self.current_angle, 1.0)
        blit_center(self.screen, rotated, (self.cx, self.cy))
        draw_pointer_down(self.screen, self.cx, self.cy, self.wheel_radius)
        pygame.draw.circle(self.screen, (0, 0, 0), (self.cx, self.cy), self.wheel_radius + 20, width=6)

        # Draw the history of the last 5 results.
        history_title_rect = self.history_title_surf_5.get_rect(topright=(self.WINDOW_SIZE[0] - 50, 60))
        self.screen.blit(self.history_title_surf_5, history_title_rect)
        y_pos = history_title_rect.bottom + 10
        start_color = pygame.Vector3(255, 255, 255); end_color = pygame.Vector3(139, 0, 0)
        short_history = self.results_history_full[:5]
        for i, result_str in enumerate(short_history):
            t = i / 4.0 if len(short_history) > 1 else 0
            color = start_color.lerp(end_color, t)
            history_surf = self.history_font.render(f"{i + 1}.  {result_str}", True, color)
            self.screen.blit(history_surf, history_surf.get_rect(topright=(self.WINDOW_SIZE[0] - 50, y_pos)))
            y_pos += history_surf.get_height()

        # Draw the pre-rendered stats table for the last 5 results.
        if self.last_5_stats_surf:
            self.screen.blit(self.last_5_stats_surf, self.last_5_stats_surf.get_rect(topright=(self.WINDOW_SIZE[0] - 50, y_pos + 20)))

        # Draw the final result text with a rainbow color effect.
        if self.result_display_text:
            self.rainbow_hue = (self.rainbow_hue + 1) % 360
            rainbow_color = pygame.Color(0, 0, 0); rainbow_color.hsva = (self.rainbow_hue, 100, 100, 100)
            result_surf = self.result_font.render(self.result_display_text, True, rainbow_color)
            result_rect = result_surf.get_rect(bottomleft=(30, self.WINDOW_SIZE[1] - 20))
            self.screen.blit(result_surf, result_rect)
            # Make the "Winning Number" title flash.
            if (self.flash_timer // 30) % 2 == 0 and not self.test_mode:
                title_rect = self.result_title_surf.get_rect(bottomleft=result_rect.topleft)
                self.screen.blit(self.result_title_surf, title_rect)

        # If in test mode, draw an overlay to indicate it.
        if self.test_mode:
            test_mode_surf = self.title_font.render("--- TEST MODE ---", True, (255, 255, 0))
            self.screen.blit(test_mode_surf, test_mode_surf.get_rect(midbottom=(self.cx, self.WINDOW_SIZE[1] - 20)))
            if self.result_display_text:
                pos_surf = self.debug_font.render(f"Position: {self.test_index}", True, (255, 255, 0))
                result_rect = self.result_font.render(self.result_display_text, True, (0,0,0)).get_rect(bottomleft=(30, self.WINDOW_SIZE[1] - 20))
                pos_rect = pos_surf.get_rect(bottomleft=result_rect.topleft)
                self.screen.blit(pos_surf, pos_rect)
    
    # --- UNCHANGED HELPER & UTILITY METHODS ---
    # The following methods are part of the core game loop and logic but are not the primary
    # focus of the recent changes. They are collapsed for brevity but fully functional.
    def _load_assets(self):
        """Loads all image and sound files from disk."""
        if not os.path.exists(WHEEL_IMAGE_PATH): print(f"Error: Wheel image not found at '{WHEEL_IMAGE_PATH}'"); sys.exit(1)
        wheel_raw = pygame.image.load(WHEEL_IMAGE_PATH).convert_alpha()
        self.wheel_img = scale_to_fit_keep_ar(wheel_raw, self.WINDOW_SIZE[0] - MARGIN_PX, self.WINDOW_SIZE[1] - MARGIN_PX)
        self.wheel_radius = max(10, min(self.wheel_img.get_width(), self.wheel_img.get_height()) // 2 - 10)
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
        """Initializes all Pygame font objects required for rendering text."""
        self.title_font = pygame.font.SysFont("Arial Black", 80)
        self.result_font = pygame.font.SysFont("Arial Black", 120)
        self.history_font = pygame.font.SysFont("Arial", 40)
        self.debug_font = pygame.font.SysFont("Arial Bold", 70)
        self.history_title_font = pygame.font.SysFont("Arial Bold", 70)
        self.result_title_font = pygame.font.SysFont("Arial Bold", 97)
        self.stats_screen_title_font = pygame.font.SysFont("Arial", 40)
        self.total_spins_font = pygame.font.SysFont("Arial Bold", 48)
    def _prerender_text(self):
        """Renders static text surfaces once on startup to improve performance."""
        self.title_text_surf = self.title_font.render("Chuck-A-Luck", True, (138, 43, 226))
        self.history_title_surf_5 = self.history_title_font.render("Last 5 Results", True, (0, 200, 0))
        self.history_title_surf_45 = self.history_title_font.render("Last 45 Results", True, (0, 200, 0))
        self.result_title_surf = self.result_title_font.render("Winning Number", True, (255, 255, 255))
        self.stats_title_surf = self.title_font.render("Full Statistics", True, (0, 200, 0))
        self.return_surf = self.stats_screen_title_font.render("Press 'S' to return to the game", True, (255, 255, 0))
    def run(self):
        """The main game loop. This method runs continuously until the player quits."""
        print("Ready. Press SPACE to spin or use the wireless button.")
        dt = 0.0 # Delta time, the time in seconds since the last frame.
        running = True
        while running:
            running = self._handle_events() # Process user input
            self._update_state(dt)          # Update game logic and animation
            self._draw()                    # Render the current frame
            dt = self.clock.tick(FPS) / 1000.0 # Control frame rate and get dt
        # --- Shutdown ---
        if self.mqtt_client and self.mqtt_client.is_connected(): self.mqtt_client.loop_stop()
        pygame.quit()
        sys.exit(0)
    def _handle_events(self):
        """Processes the event queue (keyboard, mouse, etc.). Returns False to quit."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT: return False
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q): return False
                if event.key == pygame.K_s: self.current_screen = "stats" if self.current_screen == "game" else "game"
                if self.current_screen == "game":
                    is_animating = self.animation_state != "idle"
                    if event.key == pygame.K_p and not is_animating: self._run_silent_simulation(45)
                    if event.key == pygame.K_t: self.test_mode = not self.test_mode; self.result_display_text = ""
                    if event.key == pygame.K_SPACE and not is_animating and not self.test_mode: self._start_spin()
                    if self.test_mode:
                        if event.key == pygame.K_RIGHT: self.test_index = (self.test_index + 1) % NUM_PEGS
                        if event.key == pygame.K_LEFT: self.test_index = (self.test_index - 1 + NUM_PEGS) % NUM_PEGS
        return True
    def _update_state(self, dt):
        """Updates all game logic, including animation, based on the elapsed time 'dt'."""
        if self.current_screen != "game": return
        self.flash_timer += 1
        if self.test_mode: self._update_test_mode()
        elif self.animation_state == "winding_up": self._update_wind_up(dt)
        elif self.animation_state == "spinning": self._update_spin(dt)
        else: self.current_angle = self.rest_angle
        if self.click_sound and self.animation_state != "idle":
            idx_now = int(round((self.current_angle % 360.0) / self.seg_angle)) % NUM_PEGS
            if idx_now != self.last_tick_idx:
                self.click_channel.play(self.click_sound)
                self.last_tick_idx = idx_now
    def _update_test_mode(self):
        """Locks the wheel to the selected test position and updates the result text."""
        self.animation_state = "idle"
        target_angle = (self.test_index + 0.5) * self.seg_angle
        self.current_angle = self.rest_angle = target_angle
        result = WHEEL_RESULTS[self.test_index]
        if result == (0, 0, 0): self.result_display_text = "House Wins"
        elif result == (9, 9, 9): self.result_display_text = "Spin Again"
        else: self.result_display_text = f"{result[0]} - {result[1]} - {result[2]}"
    def _update_wind_up(self, dt):
        """Handles the first phase of the animation: the backward wind-up."""
        self.animation_progress += dt / WIND_UP_TIME_SEC
        eased_u = ease_in_out_quad(min(1.0, self.animation_progress))
        self.current_angle = self.rest_angle - (WIND_UP_ANGLE_DEG * eased_u)
        if self.animation_progress >= 1.0:
            self.animation_state = "spinning"
            self.animation_progress = 0.0
    def _draw(self):
        """Main drawing function that calls the appropriate renderer for the current screen."""
        self.screen.fill((20, 20, 20))
        if self.current_screen == "game": self._draw_game_screen()
        elif self.current_screen == "stats": self._draw_stats_screen()
        pygame.display.flip()
    def _draw_stats_screen(self):
        """Renders all elements for the full statistics screen."""
        self.screen.blit(self.stats_title_surf, (50, 20))
        full_stats_surf = create_full_stats_table_surface("All-Time Stats", self.spin_counts_full, self.total_dice_rolled_full, self.total_spins_full, self.combo_counts_full)
        self.screen.blit(full_stats_surf, (50, 120))
        history_title_rect = self.history_title_surf_45.get_rect(left=full_stats_surf.get_width() + 300, top=40)
        self.screen.blit(self.history_title_surf_45, history_title_rect)
        col_width, num_per_col = 350, 15
        start_color = pygame.Vector3(255, 255, 255); end_color = pygame.Vector3(139, 0, 0)
        for i, result_str in enumerate(self.results_history_full):
            col, row = i // num_per_col, i % num_per_col
            if col > 2: continue
            t = i / (44.0 if len(self.results_history_full) > 1 else 1)
            color = start_color.lerp(end_color, t)
            history_surf = self.history_font.render(f"{i + 1}.  {result_str}", True, color)
            x_pos = history_title_rect.left + (col * col_width)
            y_pos = history_title_rect.bottom + 10 + (row * history_surf.get_height())
            self.screen.blit(history_surf, (x_pos, y_pos))
        self.screen.blit(self.return_surf, self.return_surf.get_rect(centerx=self.cx, bottom=self.WINDOW_SIZE[1] - 30))
        total_spins_surf = self.total_spins_font.render(f"Total Spins: {self.total_spins_full}", True, (255, 255, 255))
        self.screen.blit(total_spins_surf, (50, self.WINDOW_SIZE[1] - 80))
    def _pick_target(self):
        """Selects a random target segment and calculates the final angle for the spin."""
        self.result_display_text = ""
        k = random.randrange(NUM_PEGS)
        target_angle = (k + 0.5) * self.seg_angle
        spins = random.randint(MIN_SPINS, MAX_SPINS)
        start_angle = self.rest_angle - WIND_UP_ANGLE_DEG
        total_rotation = (spins * 360) + ((target_angle - (start_angle % 360) + 360) % 360)
        self.final_angle_base = start_angle + total_rotation
        self.last_tick_idx = None
    def _process_spin_result(self, winning_result):
        """Updates all statistics based on a spin result and returns a display string."""
        self.total_spins_full += 1
        num_unique = len(set(winning_result))
        if num_unique == 1 and winning_result not in [(0, 0, 0), (9, 9, 9)]: self.combo_counts_full['Triples'] += 1
        elif num_unique == 2: self.combo_counts_full['Doubles'] += 1
        else: self.combo_counts_full['Singles'] += 1
        if winning_result == (0, 0, 0):
            self.spin_counts_full['House Wins'] += 1; return "House Wins"
        elif winning_result == (9, 9, 9):
            self.spin_counts_full['Spin Again'] += 1; return "Spin Again"
        else:
            for die in winning_result:
                if 1 <= die <= 6:
                    self.spin_counts_full[die] += 1
                    self.total_dice_rolled_full += 1
            return f"{winning_result[0]} - {winning_result[1]} - {winning_result[2]}"
    def _run_silent_simulation(self, num_spins):
        """Performs instant spins to populate statistics without animation."""
        print(f"--- Running silent simulation of {num_spins} spins ---")
        for _ in range(num_spins):
            winning_result = random.choice(WHEEL_RESULTS)
            sim_result_text = self._process_spin_result(winning_result)
            self.results_history_full.insert(0, sim_result_text)
        if len(self.results_history_full) > 45: self.results_history_full = self.results_history_full[:45]
        self._update_on_screen_stats()
        print("--- Simulation complete ---")
    def _update_on_screen_stats(self):
        """Calculates stats for the last 5 results and renders them to a surface."""
        short_history = self.results_history_full[:5]
        if not short_history: self.last_5_stats_surf = None; return
        spin_counts = {i: 0 for i in range(1, 7)}; spin_counts.update({'House Wins': 0, 'Spin Again': 0})
        total_dice = 0
        for result_str in short_history:
            if result_str == "House Wins": spin_counts['House Wins'] += 1
            elif result_str == "Spin Again": spin_counts['Spin Again'] += 1
            else:
                try:
                    dice = [int(d.strip()) for d in result_str.split("-")]
                    for die in dice:
                        if 1 <= die <= 6: spin_counts[die] += 1; total_dice += 1
                except (ValueError, IndexError): pass
        self.last_5_stats_surf = create_main_screen_stats_table("Last 5 Stats", spin_counts, total_dice, len(short_history))


# ========= SCRIPT ENTRY POINT =========
# This is the standard Python construct to ensure that the code is
# run only when the script is executed directly.
if __name__ == "__main__":
    game = Game()

    game.run()
