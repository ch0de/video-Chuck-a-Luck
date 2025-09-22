# Import necessary libraries
import network
import time
from machine import Pin
from umqtt.simple import MQTTClient
from neopixel import NeoPixel
import math

# =============================================================================
# --- CONFIGURATION (EDIT THESE VALUES) ---
# =============================================================================
# Your Wi-Fi network name (SSID) and password
WIFI_SSID = "game"
WIFI_PASS = "1234567890"

# The IP address of your Raspberry Pi 5 running the MQTT broker
# If the Pi is hosting a hotspot, this is typically "192.168.4.1"
MQTT_BROKER = "192.168.4.1"

# A unique identifier for this specific Pico device on the MQTT network.
MQTT_CLIENT_ID = "pico_wheel_button"

# How often (in milliseconds) to send a "ping" to the MQTT broker.
# This acts as a heartbeat to keep the connection from being closed due to inactivity.
MQTT_PING_INTERVAL_MS = 500

# --- LED ANIMATION CONFIGURATION ---
# Set to True to enable a smooth pulsing "breathing" effect for the idle state.
# Set to False for a simple, solid green light.
IDLE_BREATHING_EFFECT = True
IDLE_BREATHE_SPEED_MS = 20         # Speed of the breathing effect (lower is faster).
IDLE_BREATHE_MIN_BRIGHTNESS = 30   # The dimmest the LED will get (0-255).
IDLE_BREATHE_MAX_BRIGHTNESS = 200  # The brightest the LED will get (0-255).

# The animation style to use when the wheel is in the "spinning" state.
# Options: 'chasing_rainbow', 'cycling_color'
SPIN_ANIMATION_MODE = 'cycling_color'
CHASING_RAINBOW_SPEED_MS = 1 # Delay between steps for the rainbow chase (lower is faster).
CYCLING_COLOR_SPEED_MS = 5   # Delay between color changes for the solid cycle (lower is faster).

# --- NEW: FLASH AND FADE CONFIGURATION ---
# Number of times the LEDs should flash for each result color.
FLASH_COUNT_WHITE = 13
FLASH_COUNT_RED = 13
FLASH_COUNT_GREEN = 13

# Duration in milliseconds for one half of a flash cycle (the fade-in or fade-out).
# A full flash (in and out) will take twice this duration.
FLASH_FADE_DURATION_MS = 300
# The duration in milliseconds to wait with the LEDs off after flashing is complete.
POST_FLASH_DELAY_MS = 2000
# The duration in milliseconds for the final fade from black to the green idle color.
FADE_TO_GREEN_DURATION_MS = 2000
# The target color for the 'idle' state, represented as (Red, Green, Blue).
IDLE_COLOR = (0, 50, 0)
# =============================================================================


# --- PIN SETUP ---
# Configure the GPIO pin for the arcade button. It's connected to GPIO 15.
# Pin.IN means it's an input pin.
# Pin.PULL_UP means an internal resistor is used to pull the voltage high, so the button just needs to connect the pin to Ground (GND) when pressed.
button = Pin(15, Pin.IN, Pin.PULL_UP)
# Configure the NeoPixel ring.
NUM_LEDS = 24 # The number of LEDs in the ring.
# Initialize the NeoPixel object on GPIO pin 16.
pixels = NeoPixel(Pin(16), NUM_LEDS)


# --- GLOBAL VARIABLES ---
# These variables hold the state and timing information for the script.
mqtt_client = None               # Will hold the MQTT client object after connection.
current_state = "idle"           # The master state of the LED ring (e.g., "idle", "spinning", "flash_red").
last_button_state = True         # Used to detect a button press (change from not pressed to pressed).
debounce_time = 0                # Timestamp used to prevent multiple rapid-fire button presses.

# Animation and network timing variables
last_anim_update = 0             # Timestamp of the last animation frame update.
last_ping = 0                    # Timestamp of the last MQTT ping.
loop_counter = 0                 # A simple counter for periodic debug printing.
rainbow_step = 0                 # Current position in the rainbow color wheel (0-255).

# State variables for the multi-stage flash-and-fade animation sequence.
flash_color_target = (0, 0, 0)   # The color to flash (e.g., red, green, or white).
flash_target_count = 0           # How many flashes to perform for the current sequence.
flash_count_completed = 0        # How many flashes have been completed so far.
flash_is_fading_in = True        # Tracks whether the current animation is fading in or out.
flash_anim_start_time = 0        # Timestamp for when the current fade started.
post_flash_delay_start_time = 0  # Timestamp for when the post-flash dark period started.
fade_to_green_start_time = 0     # Timestamp for when the final fade to green started.


# --- LED HELPER FUNCTIONS ---
def set_pixels(color):
    """Fills all LEDs with a single solid color and writes it to the strip."""
    pixels.fill(color)
    pixels.write()

def wheel(pos):
    """Helper function to generate a color from a position on a 256-step rainbow wheel."""
    # Input a value 0 to 255 to get a color value.
    # The colors are a transition r - g - b - back to r.
    if pos < 85:
        return (pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return (0, pos * 3, 255 - pos * 3)

# --- NON-BLOCKING ANIMATION HANDLERS ---
# Each of these functions manages the logic for a specific LED state.
# They are "non-blocking," meaning they run quickly and don't use long `sleep` delays,
# allowing the main loop to remain responsive.

def handle_idle_leds():
    """Sets the LEDs to a solid green color for the idle state (if not already set)."""
    if pixels[0] != IDLE_COLOR:
        set_pixels(IDLE_COLOR)

def handle_breathing_idle_leds():
    """Creates a smooth, pulsing "breathing" effect for the idle state."""
    global rainbow_step, last_anim_update
    now = time.ticks_ms()
    # Only update the animation after a specific delay to control the speed.
    if time.ticks_diff(now, last_anim_update) > IDLE_BREATHE_SPEED_MS:
        # Use a sine wave to generate a smooth curve for brightness changes.
        brightness_normalized = (math.sin(rainbow_step * (math.pi / 128)) + 1) / 2
        # Map the sine wave's output (0.0 to 1.0) to the configured min/max brightness range.
        brightness = int(IDLE_BREATHE_MIN_BRIGHTNESS + brightness_normalized * (IDLE_BREATHE_MAX_BRIGHTNESS - IDLE_BREATHE_MIN_BRIGHTNESS))
        set_pixels((0, brightness, 0)) # Set the green channel to the calculated brightness.
        rainbow_step = (rainbow_step + 1) % 256 # Advance the position in the sine wave cycle.
        last_anim_update = now

def handle_chasing_rainbow_leds():
    """Creates a 'chasing' effect where rainbow colors move around the ring."""
    global rainbow_step, last_anim_update
    now = time.ticks_ms()
    if time.ticks_diff(now, last_anim_update) > CHASING_RAINBOW_SPEED_MS:
        for i in range(NUM_LEDS):
            # Calculate the color for each pixel based on its position and the current rainbow step.
            pixel_index = (i * 256 // NUM_LEDS) + rainbow_step
            pixels[i] = wheel(pixel_index & 255)
        pixels.write()
        rainbow_step = (rainbow_step + 1) % 256 # Advance the rainbow, making it spin.
        last_anim_update = now

def handle_cycling_color_leds():
    """Smoothly cycles all LEDs through the rainbow colors simultaneously."""
    global rainbow_step, last_anim_update
    now = time.ticks_ms()
    if time.ticks_diff(now, last_anim_update) > CYCLING_COLOR_SPEED_MS:
        color = wheel(rainbow_step & 255) # Get the next color in the sequence.
        set_pixels(color) # Set all pixels to that color.
        rainbow_step = (rainbow_step + 1) % 256 # Advance to the next color.
        last_anim_update = now

def handle_fading_flash_leds():
    """Handles the smooth fade-in and fade-out flashing effect for a given color."""
    global flash_count_completed, flash_is_fading_in, flash_anim_start_time, current_state, post_flash_delay_start_time

    now = time.ticks_ms()
    # Calculate how far along we are in the current fade animation.
    elapsed = time.ticks_diff(now, flash_anim_start_time)
    progress = min(elapsed / FLASH_FADE_DURATION_MS, 1.0) # Progress from 0.0 to 1.0.

    # If fading in, brightness goes from 0 to 1. If fading out, it goes from 1 to 0.
    brightness = progress if flash_is_fading_in else 1.0 - progress
    
    # Calculate the current color based on the target color and the calculated brightness.
    r = int(flash_color_target[0] * brightness)
    g = int(flash_color_target[1] * brightness)
    b = int(flash_color_target[2] * brightness)
    set_pixels((r, g, b))

    # Check if the current fade (in or out) is complete.
    if progress >= 1.0:
        flash_anim_start_time = now # Reset the timer for the next phase.
        
        if flash_is_fading_in:
            # If we just finished fading in, the next phase is to fade out.
            flash_is_fading_in = False
        else:
            # If we just finished fading out, that's one complete flash cycle.
            flash_is_fading_in = True
            flash_count_completed += 1
            # Check if we have completed the required number of flashes.
            if flash_count_completed >= flash_target_count:
                print("Flashing complete. Starting post-flash delay.")
                set_pixels((0, 0, 0)) # Ensure LEDs are off.
                current_state = "post_flash_delay" # Transition to the next state.
                post_flash_delay_start_time = now

def handle_post_flash_delay():
    """Handles the dark period after flashing, before fading back to green."""
    global current_state, fade_to_green_start_time

    now = time.ticks_ms()
    elapsed = time.ticks_diff(now, post_flash_delay_start_time)

    # Once the configured delay time has passed, move to the next state.
    if elapsed >= POST_FLASH_DELAY_MS:
        print("Post-flash delay complete. Fading to green...")
        current_state = "fade_to_green"
        fade_to_green_start_time = now

def handle_fade_to_green():
    """Handles the smooth transition from black to the idle green color."""
    global current_state
    
    now = time.ticks_ms()
    elapsed = time.ticks_diff(now, fade_to_green_start_time)
    progress = min(elapsed / FADE_TO_GREEN_DURATION_MS, 1.0)
    
    # Linearly interpolate each color channel from 0 to the target IDLE_COLOR value.
    r = int(IDLE_COLOR[0] * progress)
    g = int(IDLE_COLOR[1] * progress)
    b = int(IDLE_COLOR[2] * progress)
    set_pixels((r, g, b))
    
    # When the fade is complete, switch back to the final 'idle' state.
    if progress >= 1.0:
        print("Fade to green complete. Entering idle state.")
        current_state = "idle"

# --- WIFI & MQTT FUNCTIONS ---
def connect_wifi():
    """Connects the Pico W to the configured Wi-Fi network."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to Wi-Fi...")
        wlan.connect(WIFI_SSID, WIFI_PASS)
        # Wait until the connection is established.
        while not wlan.isconnected():
            time.sleep(1)
    print(f"Connected! IP: {wlan.ifconfig()[0]}")

def mqtt_callback(topic, msg):
    """Function that is called every time a message is received from the MQTT broker."""
    global current_state, rainbow_step, flash_color_target, flash_count_completed, flash_is_fading_in, flash_anim_start_time, flash_target_count
    
    decoded_msg = msg.decode('utf-8')
    print(f"Received MQTT message: Topic='{topic.decode()}', Message='{decoded_msg}'")
    
    # Only change the state if the new message is different from the current state.
    if decoded_msg != current_state:
        current_state = decoded_msg
        rainbow_step = 0 # Reset animation counters on state change.
        
        # If the new state is a flash command, initialize the flash animation variables.
        if current_state.startswith("flash_"):
            flash_count_completed = 0
            flash_is_fading_in = True
            flash_anim_start_time = time.ticks_ms()
            
            # Set the target color and flash count based on the specific message received.
            if current_state == "flash_red":
                flash_color_target = (255, 0, 0)
                flash_target_count = FLASH_COUNT_RED
            elif current_state == "flash_green":
                flash_color_target = (0, 255, 0)
                flash_target_count = FLASH_COUNT_GREEN
            else: # Default case for "flash_white" or any other unrecognized flash command.
                flash_color_target = (255, 255, 255)
                flash_target_count = FLASH_COUNT_WHITE

def connect_mqtt():
    """Connects to the MQTT broker and subscribes to the 'wheel/state' topic."""
    global mqtt_client
    try:
        mqtt_client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER, keepalive=60)
        mqtt_client.set_callback(mqtt_callback) # Register the callback function.
        mqtt_client.connect()
        mqtt_client.subscribe("wheel/state") # Listen for messages on this topic.
        print("Connected to MQTT Broker and subscribed to 'wheel/state'")
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}")
        time.sleep(5) # Wait before a potential retry.

# =============================================================================
# --- MAIN SCRIPT EXECUTION ---
# =============================================================================
try:
    # This is the main entry point of the script.
    print("Starting button script...")
    connect_wifi()
    connect_mqtt()

    # Set the initial LED state based on the configuration.
    if IDLE_BREATHING_EFFECT:
        handle_breathing_idle_leds()
    else:
        handle_idle_leds()
        
    last_ping = time.ticks_ms()

    # The main loop runs forever.
    while True:
        try:
            now = time.ticks_ms()
            
            # This is essential. It checks for any incoming MQTT messages and calls the
            # mqtt_callback function if a message has arrived.
            mqtt_client.check_msg()

            # Periodically send a keep-alive ping to the broker.
            if time.ticks_diff(now, last_ping) > MQTT_PING_INTERVAL_MS:
                mqtt_client.ping()
                last_ping = now
            
            # --- Handle Button Press ---
            # Read the button's current state. It's 0 (False) when pressed due to the PULL_UP resistor.
            is_pressed = button.value() == 0
            # Check for a "falling edge" - a transition from not pressed to pressed.
            # The debounce timer prevents a single physical press from registering multiple times.
            if is_pressed and not last_button_state and time.ticks_diff(now, debounce_time) > 200:
                print("Button Pressed! Publishing to 'wheel/spin'")
                # Publish a message to the 'wheel/spin' topic to trigger the game.
                mqtt_client.publish("wheel/spin", "pressed")
                debounce_time = now # Reset the debounce timer.
            # Remember the current button state for the next loop iteration.
            last_button_state = is_pressed

            # --- State Machine: Update LEDs Based on current_state ---
            # This block calls the appropriate animation handler for the current state.
            if current_state == "spinning":
                if SPIN_ANIMATION_MODE == 'chasing_rainbow':
                    handle_chasing_rainbow_leds()
                elif SPIN_ANIMATION_MODE == 'cycling_color':
                    handle_cycling_color_leds()
            elif current_state.startswith("flash_"):
                handle_fading_flash_leds()
            elif current_state == "post_flash_delay":
                handle_post_flash_delay()
            elif current_state == "fade_to_green":
                handle_fade_to_green()
            else: # The default state is "idle".
                if IDLE_BREATHING_EFFECT:
                    handle_breathing_idle_leds()
                else:
                    handle_idle_leds()
                    
            # A very short sleep to prevent the loop from consuming 100% CPU,
            # while still being highly responsive.
            time.sleep_ms(1)
            
        except Exception as e:
            # If any error occurs within the main loop, print it and try to recover.
            print(f"An error occurred in the main loop: {e}")
            time.sleep(5)
            print("Attempting to reconnect...")
            connect_mqtt()
finally:
    # This code runs when the script is stopped (e.g., with Ctrl+C).
    # It's important for cleanup.
    print("\nScript terminating. Turning off LEDs and disconnecting.")
    set_pixels((0, 0, 0)) # Turn all LEDs off.
    if mqtt_client:
        mqtt_client.disconnect() # Disconnect cleanly from the MQTT broker.

