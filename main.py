import network
import time
from machine import Pin
from umqtt.simple import MQTTClient
from neopixel import NeoPixel

# =============================================================================
# --- CONFIGURATION (EDIT THESE VALUES) ---
# =============================================================================
# Your Wi-Fi network name and password
WIFI_SSID = "YourNetworkName"
WIFI_PASS = "YourPassword"

# The IP address of your Raspberry Pi 5 running the game
# If using the hotspot, this should be "192.168.4.1"
MQTT_BROKER = "192.168.4.1"

# A unique ID for this button
MQTT_CLIENT_ID = "pico_wheel_button"
# =============================================================================


# --- PIN SETUP ---
# Arcade button is connected between GPIO 15 and GND
button = Pin(15, Pin.IN, Pin.PULL_UP)

# NeoPixel ring's Data In is connected to GPIO 16
NUM_LEDS = 24
pixels = NeoPixel(Pin(16), NUM_LEDS)


# --- GLOBAL VARIABLES ---
mqtt_client = None
current_state = "idle"
last_button_state = True # Assume button is not pressed initially
debounce_time = 0


# --- LED HELPER FUNCTIONS ---
def set_pixels(color):
    """Fills all LEDs with a single color."""
    pixels.fill(color)
    pixels.write()

def rainbow_cycle(wait_ms):
    """Cycles through rainbow colors."""
    for j in range(255):
        for i in range(NUM_LEDS):
            pixel_index = (i * 256 // NUM_LEDS) + j
            pixels[i] = wheel(pixel_index & 255)
        pixels.write()
        time.sleep_ms(wait_ms)

def wheel(pos):
    """Helper function to generate rainbow colors."""
    if pos < 85:
        return (pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return (0, pos * 3, 255 - pos * 3)


# --- WIFI & MQTT FUNCTIONS ---
def connect_wifi():
    """Connects the Pico W to your Wi-Fi network."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to Wi-Fi...")
        wlan.connect(WIFI_SSID, WIFI_PASS)
        while not wlan.isconnected():
            time.sleep(1)
    print(f"Connected! IP: {wlan.ifconfig()[0]}")

def mqtt_callback(topic, msg):
    """This function is called every time a message is received from the broker."""
    global current_state
    decoded_msg = msg.decode('utf-8')
    print(f"Received MQTT message: Topic='{topic.decode()}', Message='{decoded_msg}'")
    current_state = decoded_msg # Update the button's state

def connect_mqtt():
    """Connects to the MQTT broker and subscribes to the state topic."""
    global mqtt_client
    mqtt_client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER)
    mqtt_client.set_callback(mqtt_callback)
    mqtt_client.connect()
    mqtt_client.subscribe("wheel/state")
    print("Connected to MQTT Broker and subscribed to 'wheel/state'")


# =============================================================================
# --- MAIN LOOP ---
# =============================================================================
print("Starting button script...")
connect_wifi()
connect_mqtt()

# Set the initial LED color to green for the 'idle' state
set_pixels((0, 50, 0))

while True:
    try:
        # Check for any new incoming MQTT messages (non-blocking)
        mqtt_client.check_msg()

        # --- Handle Button Press ---
        # Read the button state and add a "debounce" to prevent multiple presses
        now = time.ticks_ms()
        is_pressed = button.value() == 0 # Pin is low when pressed due to PULL_UP
        
        if is_pressed and not last_button_state and time.ticks_diff(now, debounce_time) > 200:
            print("Button Pressed! Publishing to 'wheel/spin'")
            mqtt_client.publish("wheel/spin", "pressed")
            debounce_time = now # Reset debounce timer
        
        last_button_state = is_pressed

        # --- Update LEDs Based on State ---
        if current_state == "spinning":
            rainbow_cycle(1) # This is a blocking animation, runs for ~0.25s
        
        elif current_state == "flashing":
            print("State is 'flashing'. Animating LEDs.")
            for _ in range(5): # Flash white 5 times
                set_pixels((255, 255, 255))
                time.sleep(0.2)
                set_pixels((0, 0, 0))
                time.sleep(0.2)
            
            # After flashing, return to idle
            current_state = "idle" 
            set_pixels((0, 50, 0)) # Green
        
        # If the state is 'idle', the green color is already set, so we do nothing.
            
        time.sleep(0.01) # A small delay to keep the Pico from running too hot

    except Exception as e:
        print(f"An error occurred: {e}")
        time.sleep(5)
        # Attempt to reconnect if something went wrong
        print("Attempting to reconnect...")
        try:
            connect_mqtt()
        except Exception as e_reconnect:
            print(f"Reconnect failed: {e_reconnect}")