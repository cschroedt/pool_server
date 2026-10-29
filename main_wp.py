# Version 1.08 - 26_10_29
# Port 2234 - Achtung, identisch zum Poolserver, somit müssen Kommandos disjunkt sein
# beginnen daher alle mit w
# int. Temp um ATempOffset nach unten korrigiert
# Sommer-/Winterzeit
# Abfrage der Pumpenleisung - einfach zur Sicherheit möglich
# Debug eMails - schaltbar
# Timer zur periodischen Überprüfung der Temperaturen auf Kern 1 und der PoolTemp auf Kern 0
# Timer für periodischen Sicherheitsreset

import network
import time
import socket
import machine
from machine import *
from machine import Timer
import math
import umail
import _thread
from helpers import *
import io
import sys

from secrets import *
from do_connect import *
#from machine import RTC
import ntptime
import requests
from md5lib import md5
from mencodeUTF16_LE import *


DeBug=False    # eMail-Debugmeldungen ausschalten
sensor_status=False  # Flag, das vom Timer gesetzt wird
pool_temp_abfrage=False # Flag, das im Kern1 gesetzt wird, um eine Temperatur-Abfrage in Kern0 zu starten
pool_temp=-888 # das Abfrageergebnis
sensor_status_result=False # setzt Kern1, wenn Sensor-Wert vorliegt
K1running=False # solange False, keine Messabfrage, beim Programmstart soll die WP noch aus sein
K1stop=False # True setzen um K1 zu stoppen

WPTemp=0.0 # Außentemp an WP
WP_Auto=True # wenn True, Einschalten über Minimaltemperatur
Min_Ein_WPTemp=15.0

Max_Aus_WPTemp=0.0  # Wenn Außentemperatur unter 0
Max_Aus_PoolTemp=1.5 # und Pooltemp unter 1.5 -> WP ein!!


StH_A = 5.6536991e-4
StH_B = 3.0092504e-4
StH_C = 3.8406474e-8

def DatZeit():
    jetzt=rtc.datetime()
    yr=str(jetzt[0])
    mo=str(jetzt[1])
    dy=str(jetzt[2])
    wt=str(jetzt[3])
    if int(mo)>=11 or int(mo) <=3:        
        hr=str(jetzt[4]+1) # Winterzeit
    else:
        hr=str(jetzt[4]+2) # Sommerzeit
    mi=str(jetzt[5])
    tm=yr+" "+mo+" "+dy+" "+hr+" "+mi
    return tm

def speichere_absturz(exception):
    try:
        # Aktuelle Zeit holen: (Jahr, Monat, Tag, Stunde, Minute, Sekunde, ...)
        t = time.localtime()
        zeit_str = f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d} {t[3]:02d}:{t[4]:02d}:{t[5]:02d}"
        
        # Im Append-Modus ("a") öffnen und mit Zeitstempel versehen
        with open("error.log", "a") as f:
            f.write(f"--- Absturz am {zeit_str} ---\n")
            sys.print_exception(exception, f)
            f.write("\n\n")
            
        print("Absturz gesichert: "+zeit_str)
    except Exception as e:
        print("Fehler beim Schreiben der Log-Datei:", e)
        
#def sendMail(caption, detail):
def sendMail(caption):
    global DeBug
    if DeBug or caption[0]=='N': # Neustart-Meldung soll immer gesendet werden
        try:
            smtp = umail.SMTP('smtp.gmail.com', 587, username=secrets['username'], password=secrets['mpassword'])
            smtp.to(secrets['sendTo'])
            smtp.write("Subject: WP - "+caption+"\n\n")
            #smtp.write(detail)
            smtp.send()
            smtp.quit()
        except Exception as e:
            tm=DatZeit()
            print("Fehler sendMail "+tm)
            #speichere_absturz(e)

def timer_callback(t):
    global sensor_status
    global pool_temp_abfrage
    global K1running
    # Der Timer läuft auf Kern 0 und setzt nur das Signal
    sensor_status = True
    pool_temp_abfrage = True
    K1running=True
    print("[Kern 0] Timer abgelaufen: Signal an Kern 1 gesendet und PoolTemp über Kern0 abgefragt")
    work_tim.deinit()
    work_tim.init(mode=Timer.PERIODIC, period=1800000, callback=timer_callback) # 30 min
    print("Timerzeit auf 30min")


def reset_callback(t):
    tm=DatZeit()
    print("Reset bei: "+tm)
    sendMail("WP Reset bei: "+tm+"\n")
    time.sleep(12)
    wlan.disconnect()
    wlan.active(False)
    time.sleep(1)
    machine.reset()

def Steinhart_Hart(U):
    Rntc=9900*U/(3.335-U)
    t=1/(StH_A+StH_B*math.log(Rntc)+StH_C*(math.log(Rntc))**3) - 273.15
    print("STH: "+str(t))
    return t

def sensor_worker():
    """Diese Funktion läuft permanent auf dem zweiten Rechenkern (Core 1)"""
    global sensor_status
    global sensor_status_result
    global K1running
    global K1stop
    global WPTemp
    global Min_Ein_WPTemp
    global WP_Auto
    print("[Kern 1] Worker-Thread gestartet auf dem zweiten Kern.")
    try:

    # Sommerbetrieb!! - WP soll nur ab 15 Grad laufen, wirkliche Steuerung erfolgt über
    # den Durchflusssensor auf der Basis des Poolpumpenlaufs
        while True:
            if K1running:
                if sensor_status:
            # Flag sofort zurücksetzen, um Mehrfachauslösungen zu verhindern
                    sensor_status = False
                    tm=DatZeit()
            
                    print("[Kern 1] Lese Sensor aus...")
            # --- HIER SENSOR-CODE ---
                    i=0
                    temp_spg=0
                    while i<10:
                        temp_spg += temp.read_u16()
                        time.sleep(0.1)
                        i+=1
                    Ur = Uref * float(temp_spg/10) / 65535  # ADC value to voltage conversion
                    
                    #Rntc=Rv*(Uref/Ur-1)
        
                    #ftemp=1/(1/298.15+1/B*math.log(R0/Rntc))-273.15
                    
                    ftemp=Steinhart_Hart(Ur)
            
                    print(f"[Kern 1] Sensor-Messwert: {ftemp}")
                    WPTemp=ftemp
            # WP einschalten ab 15 Grad, sonst aus
                    if ftemp>=Min_Ein_WPTemp and WP_Auto:
                        Rel.value(1)
                        iLED.value(1)
                        datei=open("WPein_tm.txt",'w')
                        datei.write(tm)
                        datei.close()
                        datei=open("WP.txt",'w')
                        datei.write("ein")
                        datei.close()
                        sensor_status_result=True
                        print("2 sensor_status: "+str(sensor_status)+" pool_temp_abfrage: "+str(pool_temp_abfrage)+" "+tm)
                    elif WP_Auto:
                        Rel.value(0)
                        iLED.value(0)
                        datei=open("WPaus_tm.txt",'w')
                        datei.write(tm)
                        datei.close()
                        datei=open("WP.txt",'w')
                        datei.write("aus")
                        datei.close()
                        sensor_status_result=True
                        print("2 sensor_status: "+str(sensor_status)+" pool_temp_abfrage: "+str(pool_temp_abfrage)+" "+tm)
         
        # Kurze Pause, um Kern 1 nicht zu 100% mit Leerlauf zu belasten
        
                time.sleep(1)
            elif K1stop:
                break
            else:
                time.sleep(1)
    except Exception as e:
        i=0
        #speichere_absturz(e)

def get_PoolTemp():    # holt Wassertemperatur vom Poolserver - muss auf Core0 laufen!
    ppwr=get_PumpPwr()-3 # die ist aber nur korrekt, wenn die Pumpe läuft
    print("get_PoolTemp ppwr: "+str(ppwr))
    backEncoded=str("20").encode('utf-8')
    UDPServer.sendto(backEncoded,addressP)
    time.sleep(0.5)
    #UDPServer.sendto(backEncoded,addressP)    
    #time.sleep(0.1)
    try:
        tm=DatZeit()
        message,address=UDPServer.recvfrom(bufferSize)
    except Exception as e:
        print("Poolserver down")
        sendMail("Poolserver down: "+tm)
        #speichere_absturz(e)
        return -9999
    messageDecoded=message.decode('utf-8')
    #if messageDecoded=="w22":
    if address!=addressP:
        UDPServer.sendto(backEncoded,addressP)
        time.sleep(0.5)
        message,address=UDPServer.recvfrom(bufferSize)
        messageDecoded=message.decode('utf-8')
        print("PoolTemp - 2. Versuch")
    print('Empfangen UPool:',messageDecoded,' von ',address[0])
    utmp=float(messageDecoded)
    wtmp = -225.01 + 148.89 * utmp; # aktuelle Formel des Poolservers - scheint ok zu sein
    print("1 sensor_status: "+str(sensor_status)+" pool_temp_abfrage: "+str(pool_temp_abfrage)+" "+tm)
    if ppwr>10:
        return wtmp
    else:
        return wtmp+100 # Pumpe steht, gemessene Temperatur ist die im Schacht (-100)
    

# der Unterschied zwischen Pool und WP ist die IP (128 bzw 21)

ServerPort=2234 # WP   u n d   Pool

Uref=3.335 # Referenzspannung  = Pico Pin 36
Rv=9900 # Festwiderstand im Teiler
#R0=9738.05 # NTC bei T0=298.15 K
#B=2826.41 # Bkoeff des NTC
ATempKoeff0=316.4 # Außentemperatur über Pico
ATempKoeff1=-435.06 # Lesen der Params mit 23, Setzen mit 24
ATempOffset=1.0	# wird abgezogen wg. Eigenerwärmung des Pico im Gehäuse
addressP=('192.168.178.128', 2234) # der Poolserver

i59=0

iLED = Pin("LED",Pin.OUT,value=0)
time.sleep(3)

datei=open("version_wp.txt",'r')
Version=datei.read()
datei.close()

wlan = network.WLAN(network.STA_IF)
#wlan.config(pm=0x00160004)
wlan.config(pm = 0xA4110)
wlan.active(True)

rss=do_connect()
while True:
   try:
      ntptime.settime()
      print('Time Set Successfully')
      break
   except OSError as e:
      print('Time Setting...')
      #speichere_absturz(e)
      continue
rtc=RTC()
tm=DatZeit()
stri="Neustart - Version: "+Version+", Zeit: "+tm+", Signal: "+str(rss)+"dB"
print(stri)
sendMail(stri)
wlanInfo=wlan.ifconfig()

"""   die brauchen wir hier nicht
try:
    datei=open("ATempData.txt",'r')
    TempData=datei.read()
    datei.close()
    ATempKoeff0=float(TempData[0:TempData.find(' ')])
    TempData=TempData[TempData.find(' ')+1:]
    ATempKoeff1=float(TempData[0:TempData.find(' ')-1])
    TempData=TempData[TempData.find(' ')+1:]
    ATempOffset=float(TempData[0:])
except:
    print("Fehler lesen ATempData")
    TempData=str(ATempKoeff0)+" "+str(ATempKoeff1)+" "+str(ATempOffset)
    datei=open("ATempData.txt",'w')
    print(TempData)
    datei.write(TempData)
    datei.close()
"""    
    

# 1. Den Worker-Thread auf dem zweiten Kern (Core 1) starten
try:
    _thread.start_new_thread(sensor_worker, ())
except Exception as e:
    print("Kern1 ist schon aktiv")
    #speichere_absturz(e)
    
# 2. Den Timer einrichten (alle 60 Minuten = 3.600.000 ms)
# Zum Testen kannst du den Wert z.B. auf 10000 (10 Sekunden) verkürzen.
work_tim = Timer()
#work_tim.init(mode=Timer.PERIODIC, period=3600000, callback=timer_callback)
work_tim.init(mode=Timer.PERIODIC, period=80000, callback=timer_callback) # 100s anfangs, dann immer 30 min
   
reset_tim = Timer() # ein Sicherheitsreset
reset_tim.init(mode=Timer.PERIODIC, period=24000000, callback=reset_callback) # 400 min


Rel=machine.Pin(21, machine.Pin.OUT,value=0) #Relais


temp = machine.ADC(26) # ADC Kanal 0
sensor = ADC(4) # interner Sensor
conversion_factor = 3.335 / (65535)


while True:
   try:
      ntptime.settime()
      print('Time Set Successfully')
      break
   except OSError:
      print('Time Setting...')
      continue
#print(wlan.status())
ServerIP=wlanInfo[0]
bufferSize=1024
#print(ServerIP)

try:
    UDPServer=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    UDPServer.bind((ServerIP,ServerPort))
    UDPServer.settimeout(120.0)
    print("UDP gestartet: "+tm)
except Exception as e:
    print("Fehler bei UDP setzen: "+tm)
    #speichere_absturz(e)
    
iLED.value(0)
#datei=open("WPumpe.txt",'w')
#datei.write("Pumpe aus")
#datei.close()
Rel.value(0)
datei=open("WPaus_tm.txt",'w')
datei.write(tm)
datei.close()
datei=open("WP.txt",'w')
datei.write("aus")
datei.close()


while True:						# Hauptschleife!!
    jetzt=rtc.datetime()
    yr=str(jetzt[0])
    mo=str(jetzt[1])
    dy=str(jetzt[2])
    wt=str(jetzt[3])
    if int(mo)>=11 or int(mo) <=3:        
        hr=str(jetzt[4]+1) # Winterzeit
    else:
        hr=str(jetzt[4]+2) # Sommerzeit
    mi=str(jetzt[5])
    tm=yr+" "+mo+" "+dy+" "+hr+" "+mi
    print("Warten auf Empfang: "+tm)
    rss=do_connect()
    print("Signal: "+str(rss)+" dBm")
    
    try:
        message,address=UDPServer.recvfrom(bufferSize)
        messageDecoded=message.decode('utf-8')
        print('Empfangen1: ',messageDecoded,' von ',address[0])
        if pool_temp_abfrage==True:
            pool_temp_abfrage=False
            pool_temp=get_PoolTemp()
            print("PoolTemp: "+str(pool_temp))
            back="PoolTemp: "+str(pool_temp)
            sendMail(back+" "+tm)
    except OSError as e:
        #speichere_absturz(e)
        messageDecoded="UDP Timeout"
        print("UDP Timeout")
        tm=DatZeit()
        print("3 sensor_status: "+str(sensor_status)+" pool_temp_abfrage: "+str(pool_temp_abfrage)+" "+tm)
        if pool_temp_abfrage==True:
            pool_temp_abfrage=False
            pool_temp=get_PoolTemp()
            print("PoolTemp: "+str(pool_temp))
            back="PoolTemp: "+str(pool_temp)
            sendMail(back+" "+tm)
    if sensor_status_result:
        sensor_status_result=False
        sendMail("WP-Temp: "+str(WPTemp)+" "+tm)
        
    # hier der Frostschutz
    if WPTemp<Max_Aus_WPTemp and pool_temp<Max_Aus_PoolTemp:
        print("Frostschutz aktiv")
        Rel.value(1)
        iLED.value(1)
        datei=open("WPein_tm.txt",'w')
        datei.write(tm)
        datei.close()
        datei=open("WP.txt",'w')
        datei.write("ein")
        datei.close()

        
    if messageDecoded == "w00":   # WP aus
        Rel.value(0)
        iLED.value(0)
        datei=open("WPaus_tm.txt",'w')
        datei.write(tm)
        datei.close()
        datei=open("WP.txt",'w')
        datei.write("aus")
        datei.close()
        print(address)
        backEncoded=str("WP aus").encode('utf-8')
        UDPServer.sendto(backEncoded,address)
        time.sleep(0.1)
        UDPServer.sendto(backEncoded,address)    
        time.sleep(0.1)
        UDPServer.sendto(backEncoded,address)    
        
    elif messageDecoded == "w01":	# WP ein
        Rel.value(1)
        iLED.value(1)
        datei=open("WPein_tm.txt",'w')
        datei.write(tm)
        datei.close()
        datei=open("WP.txt",'w')
        datei.write("ein")
        datei.close()
        backEncoded=str("WP ein").encode('utf-8')
        UDPServer.sendto(backEncoded,address)
        time.sleep(0.1)
        UDPServer.sendto(backEncoded,address)    
        time.sleep(0.1)
        UDPServer.sendto(backEncoded,address)
        
    elif messageDecoded == "w09":	# WP Status abfragen
        datei=open("WP.txt",'r')
        stri=datei.read()
        datei.close()
        print("WP Status "+stri)
        backEncoded=str(stri).encode('utf-8')
        UDPServer.sendto(backEncoded,address)
        time.sleep(0.1)
        UDPServer.sendto(backEncoded,address)    
        time.sleep(0.1)
        UDPServer.sendto(backEncoded,address)
        
#     elif messageDecoded == "w04S": # Poolpumpenleistung abfragen
#         ppwr=get_PumpPwr()-3
#         stri=str(ppwr)
#         backEncoded=str(ppwr).encode('utf-8')
#         UDPServer.sendto(backEncoded,address)
#         sendMail("PuLeistung : "+stri)
#         UDPServer.sendto(backEncoded,address)
#         time.sleep(0.1)
#         UDPServer.sendto(backEncoded,address)    
#         time.sleep(0.1)
#         UDPServer.sendto(backEncoded,address)    
        
    elif messageDecoded == "w20":   # Fühlerspg. für Temperatur
        print("Start WP-Temp")
        i=0
        temp_spg=0
        while i<10:
            temp_spg += temp.read_u16()
            time.sleep(0.1)
            i+=1
        Ur = Uref * float(temp_spg/10) / 65535  # ADC value to voltage conversion
        print("Ur liegt vor")
        #Rntc=Rv*(Uref/Ur-1)
        
        #ftemp=1/(1/298.15+1/B*math.log(R0/Rntc))-273.15
        ftemp=Steinhart_Hart(Ur)
        stri="Spg/Temp: "+str(Ur)+"\n"+str(ftemp)
        print(stri)
        sendMail("Gesendet: "+stri)
        backEncoded=stri.encode('utf-8')
        UDPServer.sendto(backEncoded,address)
        time.sleep(0.1)
        UDPServer.sendto(backEncoded,address)
        time.sleep(0.1)
        UDPServer.sendto(backEncoded,address)
    elif messageDecoded == 'w22':
        poolTemp=get_PoolTemp()
        print("PoolTemp: "+str(poolTemp))
       
#     elif messageDecoded == 'w21': # Temperatur interner Sensor
#         i=0
#         value_a=0
#         # Temparatur-Sensor als Dezimalzahl lesen
#         while i<20:
#             value_a += sensor.read_u16()
#             time.sleep(0.1)
#             i+=1
#     # Dezimalzahl in eine reelle Zahl umrechnen
#         spannung = value_a/20 * conversion_factor
#     # Spannung in Temperatur umrechnen
#         temperatur = ATempKoeff0 + ATempKoeff1*spannung - ATempOffset
#         temperatur=int(temperatur*10)/10
#         stri="Temperatur (Grad C): "+str(temperatur)
#         print(stri)
#         backEncoded=(str(temperatur)+"\n"+str(spannung)).encode('utf-8')
#         UDPServer.sendto(backEncoded,address)
#         sendMail("Gesendet: "+stri)
#         UDPServer.sendto(backEncoded,address)
#         time.sleep(0.1)
#         UDPServer.sendto(backEncoded,address)
# 
# 
# 
#     elif messageDecoded.find('w23')>-1 and messageDecoded.find('w23') < 2: # lese ATempData
#         try:
#             datei=open("ATempData.txt",'r')
#             TempData=datei.read()
#             datei.close()
#             backEncoded=TempData.encode('utf-8')
#             UDPServer.sendto(backEncoded,address)
#             ATempKoeff0=float(TempData[0:TempData.find(' ')-1])
#             TempData=TempData[TempData.find(' ')+1:]
#             ATempKoeff1=float(TempData[0:TempData.find(' ')-1])
#             TempData=TempData[TempData.find(' ')+1:]
#             ATempOffset=float(TempData[0:])
#         except:
#             print("Except W23")
#     elif messageDecoded.find("w24")>-1 and messageDecoded.find('w24') < 2: # schreibe ATempData
#         try:
#             TempData=messageDecoded[3:]
#             print(TempData)
#             datei=open("ATempData.txt",'w')
#             datei.write(TempData)
#             datei.close()
#             ATempKoeff0=float(TempData[0:TempData.find(' ')-1])
#             print(ATempKoeff0)
#             TempData=TempData[TempData.find(' ')+1:]
#             ATempKoeff1=float(TempData[0:TempData.find(' ')-1])
#             print(ATempKoeff1)
#             TempData=TempData[TempData.find(' ')+1:]
#             ATempOffset=float(TempData[0:])
#             print(ATempOffset)
#         except:
#             print("Except W24")
        
    elif (messageDecoded == "w880"):
        WP_Auto=False
        sendMail("WP_Auto off")
    elif (messageDecoded == "w881"):
        WP_Auto=True
        sendMail("WP_Auto on")
        
        
    elif (messageDecoded == "w998Dbg"):
        DeBug=True
        sendMail("Debug on")
    elif (messageDecoded == "w998noDbg"):
        sendMail("Debug off")
        DeBug=False     
    elif (messageDecoded == "w999x"): # Server stop
        sendMail("WPserver-Stop\n\n")
        print("WPserver stoppt...")
        work_tim.deinit()
        K1running=False
        with open("exit.flag", "w") as f:
            f.write("stop")
        time.sleep(0.2)
        machine.soft_reset()
        break
    elif (messageDecoded == "w999z"): # Server reset
        sendMail("WPserver-Reset\n\n")
        print("WPserver reset...\n")
        work_tim.deinit()
        K1running=False
        K1stop=True
        #with open("exit.flag", "w") as f:
            #f.write("stop")
        time.sleep(0.2)
        machine.reset()
        break
    else:
        print("Ungültiges Kommando")



            
            
            
                
            
            
    
    





