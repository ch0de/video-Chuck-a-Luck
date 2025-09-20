Chuck-a-Luck Prize Wheel Simulator
This project is a fully-featured prize wheel simulator built with Python and Pygame. It's designed to mimic a "Chuck-a-Luck" style casino game, complete with realistic physics-based animation, detailed statistics tracking, and integration with a custom-built wireless button controller.

The game is hosted on a Raspberry Pi 5, which also runs an MQTT broker and can create its own Wi-Fi hotspot, making the entire system portable and self-contained.

(The detailed statistics screen tracks all-time results and the last 45 spins.)

Key Features
Realistic Animation: A smooth, physically-based wheel animation using delta time and easing functions for a natural wind-up and slowdown.

Wireless Controller: Integrates seamlessly with a custom wireless button built with a Raspberry Pi Pico W. The button's RGB LEDs react to the game's state (idle, spinning, flashing) via MQTT.

Self-Contained Hotspot: The Raspberry Pi 5 can be configured to create its own Wi-Fi hotspot, making the entire system functional without an existing internet connection.

Dynamic UI: The game features two distinct screens: an interactive game screen with a dynamic payout table and a comprehensive statistics screen.

Test & Simulation Modes: Includes a test mode for manually selecting wheel outcomes and a silent simulation mode to quickly populate statistics for analysis.

Hardware Components
This project consists of two main parts: the host computer and the wireless button.

Host
Raspberry Pi 5 (or any computer capable of running Pygame)

Wireless Button Controller
Microcontroller: Raspberry Pi Pico W

Physical Button: 100mm Dome Arcade Button

Lighting: 24x WS2812B ("NeoPixel") RGB LED Ring

Power: LiPo Battery (~1200mAh) with a JST connector and a compatible charging circuit (e.g., TP4056).

Signal Integrity: A 3.3V to 5V logic level shifter for the NeoPixel data line.

Software & Setup
The project relies on a specific software stack on both the host and the controller.

1. Host Setup (Raspberry Pi 5)
A. Create a Virtual Environment:
It is highly recommended to run this project in a Python virtual environment.

# Navigate to the project directory
cd /path/to/your/game

# Create a virtual environment
python3 -m venv venv

# Activate the environment
source venv/bin/activate

B. Install Python Libraries:
With the environment active, install the required libraries.

pip install pygame paho-mqtt

C. Set Up MQTT Broker:
The game communicates with the button using an MQTT broker. Mosquitto is a lightweight and excellent choice.

# Install mosquitto
sudo apt update
sudo apt install mosquitto mosquitto-clients

# Create a config file to allow network connections
sudo nano /etc/mosquitto/conf.d/local.conf

Add the following lines to local.conf:

listener 1883
allow_anonymous true

Then, restart the broker to apply the changes:

sudo systemctl restart mosquitto

D. Set Up Wi-Fi Hotspot (Optional):
To make the system portable, you can configure the Pi 5 to be a Wi-Fi hotspot using NetworkManager.

# Install NetworkManager
sudo apt install network-manager

# Create the hotspot connection (replace ssid and psk with your own)
sudo nmcli connection add type wifi ifname wlan0 con-name Hotspot ssid "YourNetworkName" 802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared ipv4.addresses 192.168.4.1/24 wifi-sec.key-mgmt wpa-psk wifi-sec.psk "YourPassword"

# Reboot to apply
sudo reboot

2. Controller Setup (Pico W)
A. Flash MicroPython:
Ensure your Raspberry Pi Pico W is flashed with the latest version of MicroPython.

B. Install MQTT Library:
Using the Thonny IDE connected to your Pico, go to Tools > Manage packages, search for micropython-umqtt.simple, and install it.

C. Configure and Upload Script:
Open the Pico W Python script and update the configuration section with your Wi-Fi and MQTT broker details. Save the script to your Pico as main.py so it runs automatically on boot.

How to Play
Wireless Button: Press the physical button to start a spin.

SPACE: An alternative keyboard key to spin the wheel.

S: Toggles between the main game screen and the full statistics screen.

P: Runs a silent simulation of 45 spins to quickly populate the stats history.

T: Toggles a test mode where you can use the Left/Right arrow keys to manually select an outcome.

Q / ESC: Quits the application.

Pico W Wiring
Connect the components to your Raspberry Pi Pico W as follows. It is crucial that all components share a common ground (GND).

Power Circuit
Battery: Connect your LiPo battery to the B+ and B- terminals on the charging circuit.

Output to Pico: Connect the OUT+ on the charging circuit to the VSYS pin on the Pico W.

Output to Ground: Connect the OUT- on the charging circuit to any GND pin on the Pico W.

Arcade Button
The button's microswitch has two terminals.

Connect one terminal to GPIO 15.

Connect the other terminal to any GND pin.

NeoPixel LED Ring (via Logic Level Shifter)
The LED ring requires 5V power, but the Pico outputs a 3.3V data signal. A logic level shifter is required for reliable operation.

Power for Shifter & Ring:

Connect OUT+ (5V) from the charging circuit to the 5V pin on the LED Ring.

Connect OUT+ (5V) from the charging circuit to the HV (High Voltage) pin on the level shifter.

Connect the 3V3 (OUT) pin from the Pico W to the LV (Low Voltage) pin on the level shifter.

Connect GND from the Pico to the GND pin on the LED Ring and the GND pin on the level shifter.

Data Signal:

Connect GPIO 16 on the Pico W to a low-voltage channel on the shifter (e.g., LV1).

Connect the corresponding high-voltage channel (e.g., HV1) to the Data In (DI) pin on the LED Ring.
