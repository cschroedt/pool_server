# Version 5.736 - 26_08_11
# Port 2234
# Frostschutz WPumpe - int. Temp um ATempOffset nach unten korrigiert
# SK/BO Halbstellungen korrigiert
# Sommer-/Winterzeit
# Debug eMails
# 2. Kern als Watchdog - nein!!

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
from fritzactors import actors

DeBug=True    # Debugmeldungen einschalten

# Gemeinsames Lebenszeichen als globale Variable
core0_heartbeat = 0


#def sendMail(caption, detail):
def sendMail(caption):
    global DeBug
    if DeBug or caption[0]=='N': # Neustart-Meldung soll immer gesendet werden
        smtp = umail.SMTP('smtp.gmail.com', 587, username=secrets['username'], password=secrets['mpassword'])
        smtp.to(secrets['sendTo'])
        smtp.write("Subject: Pool - "+caption+"\n\n")
        #smtp.write(detail)
        smtp.send()
        smtp.quit()

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


#pSTOP=
ServerPort=2234 # Pool
#ServerPort=2222 # Test

#Konstanten für Laufdauer, Temperaturen, Filtersättigung
#werden später über Dateien verwaltet
pStart=9
pDauer=10

ATempKoeff0=286.47 # Außentemperatur über Pice
ATempKoeff1=-382.79 # Lesen der Params mit 23, Setzen mit 24
ATempOffset=1.0	# 

PFfrei=49.9		# Pumpenleistung Filer frei, Lesen mit 57, Schreiben mit 58
PFsaett=29.8	# Pumpenleistung Filter gesättigt, Sättigunsgrad über 59

i59=0

iLED = Pin("LED",Pin.OUT,value=0)
time.sleep(1)

datei=open("version.txt",'r')
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
stri="Neustart - Version: "+Version+", Zeit: "+tm+",7 Signal: "+str(rss)+"dB"
print(stri)
sendMail(stri)
wlanInfo=wlan.ifconfig()

pRunStatus=False # Pumpe aus/ein
pHand=False # Pumpe von Hand aus/ein - schaltet Timer und Frostschutz aus, wenn ein, da die Pumpe schon läuft

puBlock=False # Superfrostschutz, Wärmepumenverschraubung ist offen, Pumpe darf nie laufen
datei=open("Pumpe.txt",'r')
Msg=datei.read()
datei.close()
if Msg=="block":
    puBlock=True

FrostGrenze=0.1

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
    
try:
    datei=open("PFData.txt",'r')
    PData=datei.read()
    datei.close
except:
    print("Fehler lesen PFData")
    fData=str(PFfrei)+" "+str(PFsaett)
    datei=open("PFData.txt",'w')
    datei.write(fData)
    datei.close()
    
try:
    datei=open("PDData.txt",'r')
    dData=datei.read()
    datei.close
except:
    print("Fehler lesen PDData")
    datei=open("PDData.txt",'w')
    dData=str(pStart)+" "+str(pDauer)
    datei.write(dData)
    datei.close()
    

#tm=str(DatZeit())
#sendMail("Neustart: "+tm)

mins = 10 # 10 min Genauigkeit für Start/Stop Pumpe
def tick(timer):  # hier ist die Zeitabfrage
    global pRunStatus
    global pHand
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
        if imi<21 and ihr==pStart and pDauer>0 and pRunStatus==False and puBlock==False:
            Pu_n2.value(0)
            Pu_n3.value(0)
            Pu_n1.value(1)
            Pu_go.value(1)
            datei=open("Pumpe.txt",'w')
            datei.write("Pumpe n1")
            datei.close()
            pRunStatus=True
            print("Zeitsteuerung: Pumpe ein")
            print(DatZeit())
        elif imi<21 and ihr==pEnde and pDauer>0 and pRunStatus==True and puBlock==False:
            Pu_n1.value(0)
            Pu_n2.value(0)
            Pu_n3.value(0)
            Pu_go.value(0)
            datei=open("Pumpe.txt",'w')
            datei.write("Pumpe stop")
            datei.close()
            pRunStatus=False
            print("Zeitsteuerung: Pumpe aus")
            print(DatZeit())
        if temperatur<FrostGrenze and pRunStatus==False and puBlock==False:
            Pu_n2.value(0)
            Pu_n3.value(0)
            Pu_n1.value(1)
            Pu_go.value(1)
            datei=open("Pumpe.txt",'w')
            datei.write("Pumpe n1")
            datei.close()
            #pRunStatus=True
            #print("Frostschutz: Pumpe ein "+str(temperatur)+" "+str(FrostGrenze))
            #print(DatZeit())
        if temperatur>FrostGrenze and pRunStatus==False and puBlock==False:
            Pu_n1.value(0)
            Pu_n2.value(0)
            Pu_n3.value(0)
            Pu_go.value(0)
            datei=open("Pumpe.txt",'w')
            datei.write("Pumpe stop")
            datei.close()
            #pRunStatus=False
            #print("Frostschutz: Pumpe aus "+str(temperatur)+" "+str(FrostGrenze))
            #print(DatZeit())

Timer().init(freq=0.0167/mins, mode=Timer.PERIODIC, callback=tick) # 1 min für mins=1



Sk_auf=machine.Pin(8, machine.Pin.OUT,value=0)
Bo_auf=machine.Pin(9, machine.Pin.OUT,value=0)
Fil_ruec=machine.Pin(12, machine.Pin.OUT,value=0)
Bec_zu=machine.Pin(15, machine.Pin.OUT,value=0)
Kan_auf=machine.Pin(22, machine.Pin.OUT,value=0)

Pu_go=machine.Pin(16, machine.Pin.OUT,value=0)
Pu_n1=machine.Pin(17, machine.Pin.OUT,value=0)
Pu_n2=machine.Pin(18, machine.Pin.OUT,value=0)
Pu_n3=machine.Pin(19, machine.Pin.OUT,value=0)

M_Sk_auf=machine.Pin(10, machine.Pin.IN)
M_Bo_auf=machine.Pin(11, machine.Pin.IN)
M_Fil_ruec=machine.Pin(14, machine.Pin.IN)
M_Fil_fil=machine.Pin(13, machine.Pin.IN)
M_Kan_zu=machine.Pin(20, machine.Pin.IN)
M_Kan_auf=machine.Pin(21, machine.Pin.IN)
M_Bec_zu=machine.Pin(26, machine.Pin.IN)
M_Bec_auf=machine.Pin(27, machine.Pin.IN)

temp = machine.ADC(28)
sensor = ADC(4)
conversion_factor = 3.303 / (65535)

#iLED = Pin("LED",Pin.OUT,value=0)
#time.sleep(1)
#wlan = network.WLAN(network.STA_IF)

#wlan.active(True)
#do_connect()
#wlanInfo=wlan.ifconfig()
#print(wlanInfo)
#smtp = umail.SMTP('smtp.gmail.com', 587, username='z087320002@gmail.com', password='tqrthrlfpjimflxy')
#smtp.to('z08732-0002@gmx.de')
#smtp.write("Subject: Status Poolserver\n\n")
#smtp.write("vor Hauptschleife")
#smtp.send()
#smtp.quit()

#Pu_n2.value(0)  # soll auf jeden fall laufen
#Pu_n3.value(0)
#Pu_n1.value(1)
#Pu_go.value(1)
#sendMail("Pumpe n1")

while True:
   try:
      ntptime.settime()
      print('Time Set Successfully')
      break
   except OSError:
      print('Time Setting...')
      continue
# #print(wlan.status())
ServerIP=wlanInfo[0]
bufferSize=1024
#print('UDP Server läuft und wartet...')

UDPServer=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
UDPServer.bind((ServerIP,ServerPort))
iLED.value(1)
datei=open("Pumpe.txt",'w')
datei.write("Pumpe stop")
datei.close()
#jetzt = rtc.datetime()
#stri=jetzt[0]+" "+jetzt[1]+" "+jetzt[2]+" "+jetzt[4]+" "+jetzt[5]+" "+jetzt[6]+" "

#print("vor Hauptschleife")

#sendMail("vor Hauptschleife - 1")

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
    #print(time.time())
    
    message,address=UDPServer.recvfrom(bufferSize)
    messageDecoded=message.decode('utf-8')
    print('Empfangen:',messageDecoded,' von ',address[0])
    back='Emfangen: '+messageDecoded
    sendMail(back+' '+tm)

    #backEncoded=back.encode('utf-8')
    #UDPServer.sendto(backEncoded,address)
    if messageDecoded == "01":   # Ventilstellungen lesen
        M_Sk_auf=machine.Pin(10, machine.Pin.OUT)
        M_Bo_auf=machine.Pin(11, machine.Pin.OUT)
        M_Fil_ruec=machine.Pin(14, machine.Pin.OUT)
        M_Fil_fil=machine.Pin(13, machine.Pin.OUT)
        M_Kan_zu=machine.Pin(20, machine.Pin.OUT)
        M_Kan_auf=machine.Pin(21, machine.Pin.OUT)
        M_Bec_zu=machine.Pin(26, machine.Pin.OUT)
        M_Bec_auf=machine.Pin(27, machine.Pin.OUT)
        M_Sk_auf=machine.Pin(10, machine.Pin.IN)
        M_Bo_auf=machine.Pin(11, machine.Pin.IN)
        M_Fil_ruec=machine.Pin(14, machine.Pin.IN)
        M_Fil_fil=machine.Pin(13, machine.Pin.IN)
        M_Kan_zu=machine.Pin(20, machine.Pin.IN)
        M_Kan_auf=machine.Pin(21, machine.Pin.IN)
        M_Bec_zu=machine.Pin(26, machine.Pin.IN)
        M_Bec_auf=machine.Pin(27, machine.Pin.IN)
        #print("Skimmer/Boden: ",M_Sk_auf.value()," ",M_Bo_auf.value())
        #print("Filter: ",M_Fil_fil.value()," ",M_Fil_ruec.value())
        #print("Becken: ",M_Bec_zu.value()," ",M_Bec_auf.value())
        #print("Kanal: ",M_Kan_zu.value()," ",M_Kan_auf.value())
        Stellungen="Ventilstellungen: \n"
        datei=open("SK_BO.txt",'r')
        Stellungen+="\n"+datei.read()
        datei.close()
        #Stellungen+="Skimmer/Boden: "+str(M_Sk_auf.value())+" "+str(M_Bo_auf.value())
        Stellungen+="\nFilter: "+str(M_Fil_fil.value())+" "+str(M_Fil_ruec.value())
        Stellungen+="\nBecken: "+str(M_Bec_zu.value())+" "+str(M_Bec_auf.value())
        Stellungen+="\nKanal: "+str(M_Kan_zu.value())+" "+str(M_Kan_auf.value())
        datei=open("Pumpe.txt",'r')
        Stellungen+="\n"+datei.read()
        datei.close()
        print(Stellungen)
        backEncoded=Stellungen.encode('utf-8')
        UDPServer.sendto(backEncoded,address)
        
    elif messageDecoded == "02":	# Skimmer auf
        Bo_auf.value(0)
        Sk_auf.value(1)
        datei=open("SK_BO.txt",'w')
        datei.write("Skimmer auf")
        datei.close()
        datei=open("SK_BO_tm.txt",'w')
        #datei.write(tm+"\n"+str(time.time()))
        datei.write(tm)
        datei.close()
        #datei=open("SK_BO_tm",'r')
        #stri=datei.read()
        #datei.close()
        #print(stri)
    elif messageDecoded == "03":	# Boden auf
        Sk_auf.value(0)
        Bo_auf.value(1)
        datei=open("SK_BO.txt",'w')
        datei.write("Boden auf")
        datei.close()
        datei=open("SK_BO_tm.txt",'w')
        #datei.write(tm+"\n"+str(time.time()))
        datei.write(tm)
        datei.close()
    elif messageDecoded == "04": # Filter filtern
        Fil_ruec.value(0)
        datei=open("Filter_tm.txt",'w')
        #datei.write(tm+"\n"+str(time.time()))
        datei.write(tm)
        datei.close()
    elif messageDecoded == "05": # Filter rückspülen
        Fil_ruec.value(1)
        datei=open("Filter_tm.txt",'w')
        #datei.write(tm+"\n"+str(time.time()))
        datei.write(tm)
        datei.close()
    elif messageDecoded == "06": # Becken auf
        Bec_zu.value(0)
        datei=open("Becken_tm.txt",'w')
        #datei.write(tm+"\n"+str(time.time()))
        datei.write(tm)
        datei.close()
    elif messageDecoded == "07": # Becken zu
        Bec_zu.value(1)
        datei=open("Becken_tm.txt",'w')
        #datei.write(tm+"\n"+str(time.time()))
        datei.write(tm)
        datei.close()
    elif messageDecoded == "x8xy": # Kanal auf
        Kan_auf.value(1)
        datei=open("Kanal_tm.txt",'w')
        #datei.write(tm+"\n"+str(time.time()))
        datei.write(tm)
        datei.close()
    elif messageDecoded == "09": # Kanal zu
        Kan_auf.value(0)
        datei=open("Kanal_tm.txt",'w')
        #datei.write(tm+"\n"+str(time.time()))
        datei.write(tm)
        datei.close()
    elif messageDecoded == "10": # Pumpe stop
        Pu_n1.value(0)
        Pu_n2.value(0)
        Pu_n3.value(0)
        Pu_go.value(0)
        datei=open("Pumpe.txt",'w')
        datei.write("Pumpe stop")
        datei.close()
        pHand=False
    elif messageDecoded == "11" and puBlock==False: # Pumpe n1
        Pu_n2.value(0)
        Pu_n3.value(0)
        Pu_n1.value(1)
        Pu_go.value(1)
        datei=open("Pumpe.txt",'w')
        datei.write("Pumpe n1")
        datei.close()
        pHand=True
    elif messageDecoded == "12" and puBlock==False: # Pumpe n2
        Pu_n1.value(0)
        Pu_n3.value(0)
        Pu_n2.value(1)
        Pu_go.value(1)
        datei=open("Pumpe.txt",'w')
        datei.write("Pumpe n2")
        datei.close()
        pHand=True
    elif messageDecoded == "13" and puBlock==False: # Pumpe n3
        Pu_n1.value(0)
        Pu_n2.value(0)
        Pu_n3.value(1)
        Pu_go.value(1)
        datei=open("Pumpe.txt",'w')
        datei.write("Pumpe n3")
        datei.close()
        pHand=True
    elif messageDecoded == "20":   # Fühlerspg. für Temperatur
        i=0
        temp_spg=0
        while i<20:
            temp_spg += temp.read_u16()
            time.sleep(0.1)
            i+=1
        Vr = 3.303 * float(temp_spg/20) / 65535  # ADC value to voltage conversion
        stri="Temp-Spannung: "+str(Vr)
        print(stri)
        backEncoded=str(Vr).encode('utf-8')
        UDPServer.sendto(backEncoded,address)
        sendMail("Gesendet: "+stri)
        UDPServer.sendto(backEncoded,address)
        time.sleep(0.1)
        UDPServer.sendto(backEncoded,address)
    elif messageDecoded == '21': # Temperatur interner Sensor
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



    #elif messageDecoded=="26": # lese Frostgrenze, TempKoeffs
        #Msg="FrostGrenze, TempKoeffs: "+str(FrostGrenze)+" "+str(TempKoeff0)+" "+str(TempKoeff1)
        #backEncoded=Msg.encode('utf-8')
        #UDPServer.sendto(backEncoded,address)
    elif messageDecoded.find('23')>-1 and messageDecoded.find('23') < 2: # lese ATempData
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
            print("Except 23")
    elif messageDecoded.find("24")>-1 and messageDecoded.find('24') < 2: # schreibe ATempData
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
            print("Except 24")

    #elif messageDecoded == '23': # Temperatur Außenfühler Heizung
        #response = requests.get("http://192.168.178.67:8080")
    #elif messageDecoded == '24': # Temperatur Kollektor
        #response = requests.get("http://192.168.178.67:8080")
    elif messageDecoded == "30":   # Skimmer und Boden auf
        Msg="Das dauert jetzt etwas, bitte warten..."
        backEncoded=Msg.encode('utf-8')
        UDPServer.sendto(backEncoded,address)
        Sk_auf.value(0) # zunächst Boden auf anfahren
        Bo_auf.value(1)
        time.sleep(25) # sicherheitshalber warten
        print("Boden offen, noch 9s")
        Bo_auf.value(0) # Skimmer auf anfahren
        Sk_auf.value(1)
        time.sleep(6.5)
        Bo_auf.value(0)
        Sk_auf.value(0) # und alles anhalten        
        Msg="Skimmer und Boden sind auf"
        backEncoded=Msg.encode('utf-8')
        UDPServer.sendto(backEncoded,address)
        print("fertig")
        datei=open("SK_BO.txt",'w')
        datei.write("Skimmer und Boden auf")
        datei.close()
        datei=open("SK_BO_tm.txt",'w')
        #datei.write(tm+"\n"+str(time.time()))
        datei.write(tm)
        datei.close()
    elif messageDecoded == "31":   # Skimmer und Boden zu
        Msg="Das dauert jetzt etwas, bitte warten..."
        backEncoded=Msg.encode('utf-8')
        UDPServer.sendto(backEncoded,address)
        Bo_auf.value(0) # zunächst Skimmer auf anfahren
        Sk_auf.value(1)
        time.sleep(25) # sicherheitshalber warten
        print("Boden offen, noch 9s")
        Sk_auf.value(0) # Boden auf anfahren
        Bo_auf.value(1)
        time.sleep(9.0)
        Bo_auf.value(0)
        Sk_auf.value(0) # und alles anhalten        
        Msg="Skimmer und Boden sind geschlossen"
        backEncoded=Msg.encode('utf-8')
        UDPServer.sendto(backEncoded,address)
        print("fertig")
        datei=open("SK_BO.txt",'w')
        datei.write("Skimmer und Boden zu")
        datei.close()
        datei=open("SK_BO_tm.txt",'w')
        #datei.write(tm+"\n"+str(time.time()))
        datei.write(tm)
        datei.close()
    elif messageDecoded == "39":   # Skimmer und Boden stromlos
        Bo_auf.value(0)
        Sk_auf.value(0)
    elif messageDecoded == "40": # Datum/Zeit ausgeben
        #Msg = tm+"\n"+str(time.time())
        Msg = DatZeit()
        backEncoded=str(Msg).encode('utf-8')
        UDPServer.sendto(backEncoded,address)
        print("gesendet: "+Msg)
    elif (messageDecoded == "42" or messageDecoded == "43"): # Datum/Zeit der letzten Sk_Bo-Bewegung ausgeben
        datei=open("SK_BO_tm.txt",'r')
        Msg = datei.read()
        datei.close()
        print("42: "+Msg)
        backEncoded=str(Msg).encode('utf-8')
        UDPServer.sendto(backEncoded,address)
    elif (messageDecoded == "44" or messageDecoded == "45"): # Datum/Zeit der letzten Filter-Bewegung ausgeben
        datei=open("Filter_tm.txt",'r')
        Msg = datei.read()
        datei.close()
        backEncoded=str(Msg).encode('utf-8')
        UDPServer.sendto(backEncoded,address)
    elif (messageDecoded == "46" or messageDecoded == "47"): # Datum/Zeit der letzten Becken-Bewegung ausgeben
        datei=open("Becken_tm.txt",'r')
        Msg = datei.read()
        datei.close()
        backEncoded=str(Msg).encode('utf-8')
        UDPServer.sendto(backEncoded,address)
    elif (messageDecoded == "48" or messageDecoded == "49"): # Datum/Zeit der letzten Kanal-Bewegung ausgeben
        datei=open("Kanal_tm.txt",'r')
        Msg = datei.read()
        datei.close()
        backEncoded=str(Msg).encode('utf-8')
        UDPServer.sendto(backEncoded,address)
    elif (messageDecoded == "51"): # Wärmepumpe aus
        succ=actors(1)
        print(succ)
        backEncoded=str(succ).encode('utf-8')
        UDPServer.sendto(backEncoded,address)
    elif (messageDecoded == "52"): # Wärmepumpe ein
        succ=actors(2)
        print(succ)
        backEncoded=str(succ).encode('utf-8')
        UDPServer.sendto(backEncoded,address)
        
    elif (messageDecoded == "57"): # Pumpenleistungen für Sättigung lesen
        datei=open("PFData.txt",'r')
        PFData=datei.read()
        datei.close()
        backEncoded=PFData.encode('utf-8')
        UDPServer.sendto(backEncoded,address)
        
    elif (messageDecoded.find("58"))>-1: # Pumpenleistungen schreiben
        messageDecoded=message.decode('utf-8')
        messageDecoded=messageDecoded[3:]
        PFfrei=float(messageDecoded[0:messageDecoded.find(' ')])
        messageDecoded=messageDecoded[messageDecoded.find(' ')+1:]
        PFsaett=float(messageDecoded)
        datei=open("PFData.txt",'w')
        datei.write(str(PFfrei)+" "+str(PFsaett))
        datei.close()
        
    elif (messageDecoded == "59"): # Pumpenleistung senden

        if i59>0:
            pwr=actors(9,SID)
            time.sleep(1)
            pwr=stri[0:stri.find(' ')-1]
            backEncoded=(str(pwr)+" "+str(PFfrei)+" "+str(PFsaett)).encode('utf-8')
            UDPServer.sendto(backEncoded,address)
            print(backEncoded)
        if i59==0:
            stri=actors(9,"")
            SID=stri[stri.find(' ')+1:]
            print(SID)
            i59=1
            pwr=stri[0:stri.find(' ')-1]
            backEncoded=(str(pwr)+" "+str(PFfrei)+" "+str(PFsaett)).encode('utf-8')
            UDPServer.sendto(backEncoded,address)
            print(backEncoded)
        #time.sleep(1)
        #UDPServer.close()
        #UDPServer=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        #UDPServer.bind((ServerIP,ServerPort))
        
    elif (messageDecoded == "60"): # Laufdauer-Parameter Pumpe lesen (Stunden)
        datei=open("PDData.txt",'r')
        pDData=datei.read()
        datei.close()
        backEncoded=pDData.encode('utf-8')
        UDPServer.sendto(backEncoded,address)
        
    elif (messageDecoded.find("61"))>-1: # Parameter Pumpe schreiben
        messageDecoded=message.decode('utf-8')
        messageDecoded=messageDecoded[3:]
        pStart=int(messageDecoded[0:messageDecoded.find(' ')])
        messageDecoded=messageDecoded[messageDecoded.find(' ')+1]
        pDauer=int(messageDecoded)
        datei=open("PDData.txt",'w')
        datei.write(str(pStart)+" "+str(pDauer))
        datei.close()
        
    elif (messageDecoded == "69"): # Laufdauer Pumpe löschen
        PDauer=0
        
    elif (messageDecoded == "7777"): # WP-Verschraubung ist offen, Pumpe darf nie laufen
        puBlock=True
        datei=open("Pumpe.txt",'w')
        datei.write("Pumpe geblockt")
        datei.close()
        Pu_n1.value(0)
        Pu_n2.value(0)
        Pu_n3.value(0)
        Pu_go.value(0)
        print("Pumpe geblockt")
    elif (messageDecoded == "8888"): # alles wieder gut...
        datei=open("Pumpe.txt",'w')
        puBlock=False
        datei.write("Pumpe stop")
        datei.close()
        print("Pumpe normal")
    elif (messageDecoded == "999x"): # Server stop
        smtp = umail.SMTP('smtp.gmail.com', 587, username='z087320002@gmail.com', password='tqrthrlfpjimflxy')
        smtp.to('z08732-0002@gmx.de')
        smtp.write("Subject: Poolserver-Stop\n\n")
        smtp.write("main1 angehalten")
        smtp.send()
        smtp.quit()
        #import sys
        #import os
        #os.remove('boot.py')
        print("Server stoppt...")
        #sys.exit()
        break
    else:
        print("Ungültiges Kommando")
# Lebenszeichen aktualisieren
    core0_heartbeat = (core0_heartbeat + 1) % 1_000_000

    time.sleep(0.1)        



            
            
            
                
            
            
    
    






