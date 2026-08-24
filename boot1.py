import network
import time
from ota_updater import OTAUpdater
from secrets import *
import umail

def sendMail(caption):
    global DeBug
    if DeBug or caption[0]=='N': # Neustart-Meldung soll immer gesendet werden
        smtp = umail.SMTP('smtp.gmail.com', 587, username=secrets['username'], password=secrets['mpassword'])
        smtp.to(secrets['sendTo'])
        smtp.write("Subject: Pool - "+caption+"\n\n")
        #smtp.write(detail)
        smtp.send()
        smtp.quit()

# --- Wi-Fi Configuration ---
# You've selected these constants in your MainActivity.java, so we'll use them here.
WIFI_SSID = secrets['ssid']  # Replace with your actual Wi-Fi SSID
WIFI_PASSWORD = secrets['wlpassword'] # Replace with your actual Wi-Fi password
EXTENDER_BSSID=b'\xb0\xf2\x08\xcb\xa0\x31'
DeBug=True
# --- OTA Configuration ---
# This is the raw content URL for your GitHub repository.
# IMPORTANT: Replace "your-username/your-repo" with your actual username and repository name.
FIRMWARE_URL = "https://raw.githubusercontent.com/cschroedt/pool_server/main"

'''
# List of files to update from the repository
try:
    datei=open("FILES_TO_UPDATE.txt",'r')
    upd_str=datei.read()
    datei.close()
    FILES_TO_UPDATE = upd_str.split()
    print(FILES_TO_UPDATE)
except:
    datei=open("FILES_TO_UPDATE.txt",'w')
    datei.write("version.txt main1.py")
    datei.close()
    FILES_TO_UPDATE = ['version.txt' 'main1.py'] # Add any other files you need
    print("Except: "+str(FILES_TO_UPDATE))
'''

# --- Connect to Wi-Fi ---
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(WIFI_SSID, WIFI_PASSWORD, bssid=EXTENDER_BSSID)
#wlan.connect(WIFI_SSID, WIFI_PASSWORD)

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
    #sendMail("Conn in boot1")
    
    # --- Check for and Apply OTA Update ---
    #file_list_name="files_to_update.json"
    #ota = OTAUpdater("https://raw.githubusercontent.com/cschroedt/pool_server/main", file_list_name="files_to_update.json")
    ota = OTAUpdater("https://raw.githubusercontent.com/cschroedt/pool_server/main", "files_to_update.json")
    #ota = OTAUpdater(FIRMWARE_URL, FILES_TO_UPDATE)
    ota.check_for_updates()
    #sendMail("nach OTAup")
wlan.disconnect()
wlan.active(False)
wlan=None
# The script will now proceed to run main.py (if no reboot occurred)
print("Boot sequence finished. Starting main application...")
import main1
main1()
