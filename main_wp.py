# Version 1.01 - 26_10_12
# Port 2234 - Achtung, identisch zum Poolserver, daher müssen Kommandos disjunkt sein
# beginnen daher alle mit W
# int. Temp um ATempOffset nach unten korrigiert
# Sommer-/Winterzeit
# Abfrage der Pumpenleisung - einfach zur Sicherheit möglich
# Debug eMails - schaltbar

import network
import time
import socket
import machine
from machine import *
import math
import umail

from secrets import *
from do_connect import *
#from machine import RTC
import ntptime
import requests
from md5lib import md5
from mencodeUTF16_LE import *


DeBug=True    # Debugmeldungen einschalten

#def sendMail(caption, detail):
def sendMail(caption):
    global DeBug
    if DeBug or caption[0]=='N': # Neustart-Meldung soll immer gesendet werden
        smtp = umail.SMTP('smtp.gmail.com', 587, username=secrets['username'], password=secrets['mpassword'])
        smtp.to(secrets['sendTo'])
        smtp.write("Subject: WP - "+caption+"\n\n")
        #smtp.write(detail)
        smtp.send()
        smtp.quit()

def get_PumpPwr():
    response = requests.get("http://192.168.178.1/login_sid.lua")
    response_content = response.content.decode('utf-8')
    response.close()
    #sendMail("PPwr 1")
    ia=response_content.index("nge>")
    ie=response_content.index("</Cha")
    challenge=response_content[ia+4:ie]
    password="38ca7ff9"
    tmp="{}-{}".format(challenge, password)
    tmp2=mencodeUTF16_LE(tmp)
    h = md5()
    h.update(tmp2)
    has = (h.digest())
    has = to_hex(has)
    username="pool"
    respons = "{}-{}".format(challenge, has)
    response = requests.get("http://192.168.178.1/login_sid.lua?username={}&response={}".format(username, respons))
    response_content = response.content.decode('utf-8')
    response.close()
    #sendMail("PPwr 2")
    ia=response_content.index("SID>")
    SID=response_content[ia+4:ia+20]
    print(SID)
    resp=requests.get("http://192.168.178.1/webservices/homeautoswitch.lua?ain=116300064720&switchcmd=getswitchpower&sid={}".format(SID))
    if resp.status_code==200:
        print("Login erfolgreich")
    response_content = resp.content.decode('utf-8')
    #sendMail("PPwr 3")
    resp1=requests.get("http://192.168.178.1/?sid={}&security:command/logout={}".format(SID,"dmy"))
    if resp1.status_code==200:
        print("Logout erfolgreich")
        resp1.close()
        return(float(response_content)/1000)
    else:
        print("Fehler bei Logout")
        resp1.close()
        return -1
   
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


# der Unterschied zwischen Pool und WP ist die IP (128 bzw 21)

ServerPort=2234 # WP   u n d   Pool
pStart=9
pDauer=10
pHand=False
pRunStatus=False

Uref=3.335 # Referenzspannung  = Pico Pin 36
Rv=9900 # Festwiderstand im Teiler
R0=8852.774 # NTC bei T0=298.15 K
B=2826.41 # Bkoeff des NTC
ATempKoeff0=20.6 # Außentemperatur über Pico
ATempKoeff1=435.06 # Lesen der Params mit 23, Setzen mit 24
ATempOffset=1.0	# wird abgezogen wg. Eigenerwärmung des Pico im Gehäuse

i59=0

iLED = Pin("LED",Pin.OUT,value=0)
time.sleep(1)

datei=open("version_wp.txt",'r')
Version=datei.read()
datei.close()

wlan = network.WLAN(network.STA_IF)
wlan.config(pm=0x00160004)
wlan.active(True)
rss=do_connect()
while True:
   try:
      ntptime.settime()
      print('Time Set Successfully')
      break
   except OSError:
      print('Time Setting...')
      continue
rtc=RTC()
tm=DatZeit()
stri="Neustart - Version: "+Version+", Zeit: "+tm+", Signal: "+str(rss)+"dB"
print(stri)
sendMail(stri)
wlanInfo=wlan.ifconfig()


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
    
    

mins = 10 # 10 min Genauigkeit für Start/Stop Wärmepumpe
def tick(timer):  # hier ist die Zeitabfrage
    jetzt1=rtc.datetime()
    imo=int(jetzt1[1])

    if imo>=11 or imo<=3:
        ihr=int(jetzt1[4]+1) # Winterzeit auf wenige Tage ungenau gestellt
    else:
        ihr=int(jetzt1[4]+2) # Sommerzeit
    imi=int(jetzt1[5])
    # Temperatur über inneren Sensor des pico
    i=0
    value_a=0
    # Temperatur-Sensor als Dezimalzahl lesen
    while i<20:
        value_a += sensor.read_u16()
        time.sleep(0.1)
        i+=1
    # Dezimalzahl in eine reelle Zahl umrechnen
    spannung = value_a/20 * conversion_factor
    # Spannung in Temperatur umrechnen
        #temperatur = 27 - (spannung - 0.681) / 0.001721
    temperatur = ATempKoeff0 + spannung*ATempKoeff1 - ATempOffset
    temperatur=int(temperatur*10)/10
    #print(temperatur)
    
    pEnde=pStart+pDauer
    if pEnde>24:
        pEnde-=24
        
    if pHand==False:  # nur wenn Pumpe nicht von Hand gestartet wurde...
        if imi<21 and ihr==pStart and pDauer>0 and pRunStatus==False:
            Rel.value(1)
            datei=open("WPumpe.txt",'w')
            datei.write("WPumpe ein")
            datei.close()
            pRunStatus=True
            print("Zeitsteuerung: WPumpe ein")
            print(DatZeit())
        elif imi<21 and ihr==pEnde and pDauer>0 and pRunStatus==True:
            Rel.value(0)
            datei=open("WPumpe.txt",'w')
            datei.write("WPumpe aus")
            datei.close()
            pRunStatus=False
            print("Zeitsteuerung: WPumpe aus")
            print(DatZeit())

Timer().init(freq=0.0167/mins, mode=Timer.PERIODIC, callback=tick) # 1 min für mins=1

Rel=machine.Pin(21, machine.Pin.OUT,value=0) #Relais


temp = machine.ADC(26) # ADC Kanal 0
sensor = ADC(4) # interner Sensorprint 
conversion_factor = 3.303 / (65535)


while True:
   try:
      ntptime.settime()
      print('Time Set Successfully')
      break
   except OSError:
      print('Time Setting...')
      continue
print(wlan.status())
ServerIP=wlanInfo[0]
bufferSize=1024
print(ServerIP)

UDPServer=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
UDPServer.bind((ServerIP,ServerPort))
iLED.value(1)
datei=open("WPumpe.txt",'w')
datei.write("Pumpe aus")
datei.close()

while True:
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
    
    
    message,address=UDPServer.recvfrom(bufferSize)
    messageDecoded=message.decode('utf-8')
    print('Empfangen:',messageDecoded,' von ',address[0])
    back='Emfangen: '+messageDecoded
    sendMail(back+' W0.1 '+tm)

    #backEncoded=back.encode('utf-8')
    #UDPServer.sendto(backEncoded,address)
    if messageDecoded == "w00":   # WP aus
        Rel.value(0)
        datei=open("WPaus_tm.txt",'w')
        datei.write(tm)
        datei.close()
        datei=open("WP.txt",'w')
        datei.write("aus")
        datei.close()
        backEncoded=str("WP aus").encode('utf-8')
        UDPServer.sendto(backEncoded,address)
        time.sleep(0.1)
        UDPServer.sendto(backEncoded,address)    
        time.sleep(0.1)
        UDPServer.sendto(backEncoded,address)    
        
    elif messageDecoded == "w01":	# WP ein
        Rel.value(1)
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
        backEncoded=str(stri).encode('utf-8')
        UDPServer.sendto(backEncoded,address)
        time.sleep(0.1)
        UDPServer.sendto(backEncoded,address)    
        time.sleep(0.1)
        UDPServer.sendto(backEncoded,address)
        
    elif messageDecoded == "w04S": # Poolpumpenleistung abfragen
        ppwr=get_PumpPwr()-3
        stri=str(ppwr)
        backEncoded=str(ppwr).encode('utf-8')
        UDPServer.sendto(backEncoded,address)
        sendMail("PuLeistung : "+stri)
        UDPServer.sendto(backEncoded,address)
        time.sleep(0.1)
        UDPServer.sendto(backEncoded,address)    
        time.sleep(0.1)
        UDPServer.sendto(backEncoded,address)    
        
    elif messageDecoded == "w20":   # Fühlerspg. für Temperatur
        i=0
        temp_spg=0
        while i<20:
            temp_spg += temp.read_u16()
            time.sleep(0.1)
            i+=1
        Ur = Uref * float(temp_spg/20) / 65535  # ADC value to voltage conversion
        stri="Temp-Spannung: "+str(Ur)
        print(stri)
        
        backEncoded=str(Ur).encode('utf-8')
        UDPServer.sendto(backEncoded,address)
        sendMail("Gesendet: "+stri)
        UDPServer.sendto(backEncoded,address)
        time.sleep(0.1)
        UDPServer.sendto(backEncoded,address)
        Rntc=Rv*(Uref/Ur-1)
        temp=1/(1/273.15+1/B*math.log(R0/Rntc))
        
    elif messageDecoded == 'w21': # Temperatur interner Sensor
        i=0
        value_a=0
        # Temparatur-Sensor als Dezimalzahl lesen
        while i<20:
            value_a += sensor.read_u16()
            time.sleep(0.1)
            i+=1
    # Dezimalzahl in eine reelle Zahl umrechnen
        spannung = value_a/20 * conversion_factor
    # Spannung in Temperatur umrechnen
        temperatur = ATempKoeff0 + spannung*ATempKoeff1 -ATempOffset
        temperatur=int(temperatur*10)/10
        stri="Temperatur (Grad C): "+str(temperatur)
        print(stri)
        backEncoded=(str(temperatur)+"\n"+str(spannung)).encode('utf-8')
        UDPServer.sendto(backEncoded,address)
        sendMail("Gesendet: "+stri)
        UDPServer.sendto(backEncoded,address)
        time.sleep(0.1)
        UDPServer.sendto(backEncoded,address)



    elif messageDecoded.find('w23')>-1 and messageDecoded.find('w23') < 2: # lese ATempData
        try:
            datei=open("ATempData.txt",'r')
            TempData=datei.read()
            datei.close()
            backEncoded=TempData.encode('utf-8')
            UDPServer.sendto(backEncoded,address)
            ATempKoeff0=float(TempData[0:TempData.find(' ')-1])
            TempData=TempData[TempData.find(' ')+1:]
            ATempKoeff1=float(TempData[0:TempData.find(' ')-1])
            TempData=TempData[TempData.find(' ')+1:]
            ATempOffset=float(TempData[0:])
        except:
            print("Except W23")
    elif messageDecoded.find("w24")>-1 and messageDecoded.find('w24') < 2: # schreibe ATempData
        try:
            TempData=messageDecoded[3:]
            print(TempData)
            datei=open("ATempData.txt",'w')
            datei.write(TempData)
            datei.close()
            ATempKoeff0=float(TempData[0:TempData.find(' ')-1])
            print(ATempKoeff0)
            TempData=TempData[TempData.find(' ')+1:]
            ATempKoeff1=float(TempData[0:TempData.find(' ')-1])
            print(ATempKoeff1)
            TempData=TempData[TempData.find(' ')+1:]
            ATempOffset=float(TempData[0:])
            print(ATempOffset)
        except:
            print("Except W24")

        
    elif (messageDecoded == "w998Dbg"):
        DeBug=True
        sendMail("Debug on")
    elif (messageDecoded == "w998noDbg"):
        DeBug=False     
        sendMail("Debug off")
    elif (messageDecoded == "w999x"): # Server stop
        smtp = umail.SMTP('smtp.gmail.com', 587, username=secrets['username'], password=secrets['mpassword'])
        smtp.to('z08732-0002@gmx.de')
        smtp.write("Subject: WPserver-Stop\n\n")
        smtp.write("main1 angehalten")
        smtp.send()
        smtp.quit()
        print("Server stoppt...")
        break
    elif (messageDecoded == "w999z"): # Server reset
        smtp = umail.SMTP('smtp.gmail.com', 587, username=secrets['username'], password=secrets['mpassword'])
        smtp.to('z08732-0002@gmx.de')
        smtp.write("Subject: WPserver-Reset\n\n")
        smtp.write("Alles angehalten, Konsole verfügbar")
        smtp.send()
        smtp.quit()
        print("WPserver reset...\n")
        machine.reset()
        break
    else:
        print("Ungültiges Kommando")



            
            
            
                
            
            
    
    





