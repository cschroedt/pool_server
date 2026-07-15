import network
import time
import ntptime
from secrets import *
from machine import Pin

def do_connect(ssid=secrets['ssid'],psk=secrets['wlpassword']):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(ssid, psk)
        iLED = Pin("LED",Pin.OUT,value=0)

        # Wait for connect or fail
        wait = 15
        while wait > 0:
            iLED.value(1)
            if wlan.status() < 0 or wlan.status() >= 3:
                break
            wait -= 1
            print('waiting for connection...')
            time.sleep(1)
            iLED.value(0)

    # Handle connection error
    if wlan.status() != 3:
        raise RuntimeError('wifi connection failed')
    else:
        print('connected')
        #ip=wlan.ifconfig()[0]
        wlan.config(pm=0x0010) # max Leistung
        #print('network config: ', ip)
        #return ip
        return wlan.status('rssi')
    
def sync_time():
    """Synchronisiert die interne Uhr via NTP."""
    try:
        print("Synchronisiere Uhrzeit via NTP...")
        ntptime.settime()
        print("Uhrzeit erfolgreich synchronisiert:", rtc.datetime())
    except Exception as e:
        print("Fehler bei der NTP-Synchronisation:", e)
        
def disconnect():
    """Trennt die WLAN-Verbindung sauber."""
    wlan = network.WLAN(network.STA_IF)
    if wlan.isconnected():
        wlan.disconnect()
        wlan.active(False)
        print("WLAN getrennt.")
        time.sleep(1)
        
def check_time_callback(t):
    """
    Timer-Interrupt-Callback.
    Läuft jede Minute und prüft, ob es 01:00 Uhr ist.
    """
    global sync_triggered
    now = rtc.datetime()  # Format: (Jahr, Monat, Tag, Wochentag, Stunde, Minute, Sekunde, Subsekunde)
    Stunde = now[4]
    Minute = now[5]
    
    # Prüfen, ob es genau 01:00 Uhr ist
    if Stunde == 1 and Minute == 0:
        if not sync_triggered:
            sync_triggered = True  # Signal an die Hauptschleife senden        
        
        
