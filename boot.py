import network
import time
from secrets import *
from ota_updater import OTAUpdater

# --- Wi-Fi Configuration ---
# You've selected these constants in your MainActivity.java, so we'll use them here.
WIFI_SSID = secrets['ssid'] # Replace with your actual Wi-Fi SSID
WIFI_PASSWORD = secrets['password'] # Replace with your actual Wi-Fi password

# --- OTA Configuration ---
# This is the raw content URL for your GitHub repository.
# IMPORTANT: Replace "your-username/your-repo" with your actual username and repository name.
FIRMWARE_URL = "https://raw.githubusercontent.com/cschroedt/pool_server/main"
# List of files to update from the repository
FILES_TO_UPDATE = ['boot1.py', 'main1.py', 'version.txt', 'do_connect.py', 'secrets.py'] # Add any other files you need

# --- Connect to Wi-Fi ---
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
#wlan.connect(WIFI_SSID, WIFI_PASSWORD)
wlan.connect('R21W', 'Rainlesberg12')

# Wait for connection
max_wait = 10
while max_wait > 0:
    if wlan.status() < 0 or wlan.status() >= 3:
        break
    max_wait -= 1
    print('Waiting for connection...')
    time.sleep(1)

if wlan.status() != 3:
    print('Network connection failed. Skipping update.')
else:
    print('Connected to Wi-Fi.')
    print('IP address:', wlan.ifconfig()[0])
    
    # --- Check for and Apply OTA Update ---
    ota = OTAUpdater(FIRMWARE_URL, FILES_TO_UPDATE)
    ota.check_for_updates()
datei=open("version.txt",'r')
msg=datei.read()
datei.close
wlan.disconnect()
wlan.active(False)
wlan=None
# The script will now proceed to run main.py (if no reboot occurred)
print("Boot sequence finished. Starting main application...")
import main1
main1()
