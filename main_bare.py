# This is intended to be a barebones version of the main.py file
# Once features are implemented and tested, they will be added here
# This serves as a backup and a way to keep core functionality

import sys
import os
import time
import serial # type: ignore
import threading
import datetime
import Resources.config as config
import Resources.OLED_2in42 as OLED_2in42
from PIL import Image,ImageDraw,ImageFont
from gpiozero import Button # type: ignore
from Resources.conversions import convertToSpeed, convertToRev, convertToTemp, convertToBattery, convertToMAF, convertToAAC, convertToInjection, convertToTiming  
from Resources.Modes.Settings.settings import *
import numpy as np
# from Resources.ConfigUpdater import ConfigUpdater

# OLED screen info
Device_SPI = config.Device_SPI
Device_I2C = config.Device_I2C
OLED_WIDTH   = 128
OLED_HEIGHT  = 64
font1 = ImageFont.truetype('Font.ttc', 18)
font2 = ImageFont.truetype('Font.ttc', 24)

# Button configs
ModeButton = Button() #switch modes (data stream, DTC, test, settings)
DisplayButton = Button(6) #switch displayed values (i.e. speed, rpm, etc. Or in settings mode switch which setting is shown)
PeakButton = Button(16) #show peak values using a button attached to GPIO Pin 16
PowerButton = Button()

def WriteText(upper,lower): #Writes text to the display
    image = Image.new('1', (128, 64), 255)
    draw = ImageDraw.Draw(image)
    draw.text((20,0),str(upper), font = font1, fill = 0)
    if lower is not None: 
        draw.text((20,24), str(lower), font = font2, fill = 0)
    image = image.rotate(180) 
    disp.ShowImage(disp.getbuffer(image))

def PortConnect(PORT):
    try:
        PORT = serial.Serial('/dev/ttyUSB0', 9600, timeout=None)
    except OSError:
        if PORT:
            print('Port is not none')
            if PORT.is_open:  # Check if PORT is not None and is open
                print('Port is open')
        else:
            if PORT:
                PORT.open()  # port is not none but is closed
            else:
                print('Failed to initialize PORT')  # Handle the case where PORT is still None
    return PORT

PORT = None  # Initialize PORT to None

disp = OLED_2in42.OLED_2in42(spi_freq = 1000000)
disp.Init()

while PORT is None:
    PORT = PortConnect()
    time.sleep(0.1)
    print('PORT = None')
    WriteText('Connecting...','Please wait')

######################################################################## 
class ReadStream(threading.Thread):
    def __init__(self, daemon):
        threading.Thread.__init__(self)
        self.daemon = daemon
        self.SPEED_Value = 0
        self.RPM_Value = 0
        self.TEMP_Value = 0
        self.BATT_Value = 0
        self.MAF_Value = 0
        self.AAC_Value = 0
        self.INJ_Value = 0
        self.TIM_Value = 0
        
        read_Thread = True; # NOTE I think this is unused? Becuase it's a different case
        self.Header = 255
        self.returnBytes = 14
        fileName = datetime.datetime.now().strftime("%d-%m-%y-%H-%M")
        
        self.start()
        
    def check_data_size(data_list):
        Header = 255
        returnBytes = 14
        try:
            if data_list[-4] != Header:
                return False
            if data_list[-3] != returnBytes:
                return False   
                    
        except (ValueError, IndexError):
            return False
        return True
                
    def consume_data(self):
        read_thread = True
        while read_thread:
            incomingData = PORT.read(16)
            if incomingData:
                dataList = list(incomingData)

            # if not self.check_data_size(dataList): ## NOTE BROKEN!! FIX ME!!!
            #     continue
                
            try:
                SPEED_Value = self.convertToSpeed(int(dataList[-2]))
                RPM_Value = self.convertToRev(int(dataList[-1]))
                TEMP_Value = self.convertToTemp(int(dataList[0]))
                BATT_Value = self.convertToBattery(float(dataList[1]))
                MAF_Value = self.convertToMAF(int(dataList[5]))
                AAC_Value = self.convertToAAC(int(dataList[8]))
                  
            except (ValueError, IndexError):
                   pass         
            time.sleep(0.002)
        return SPEED_Value, RPM_Value, TEMP_Value, BATT_Value, MAF_Value, AAC_Value, INJ_Value, TIM_Value

    def run(self):
        #PORT.write('\x5A\x0B\x5A\x01\x5A\x08\x5A\x0C\x5A\x0D\x5A\x03\x5A\x05\x5A\x09\x5A\x13\x5A\x16\x5A\x17\x5A\x1A\x5A\x1C\x5A\x21\xF0')
        PORT.write(bytes([0x5A,0x0B,0x5A,0x01,0x5A,0x08,0x5A,0x0C,0x5A,0x0D,0x5A,0x03,0x5A,0x05,0x5A,0x09,0x5A,0x13,0x5A,0x16,0x5A,0x17,0x5A,0x1A,0x5A,0x1C,0x5A,0x21,0xF0]))
        #/ Speed / CAS/RPM / CoolantTemp / BatteryVoltage / ThrottlePosition / CAS/RPM / MAF / LH02 / DigitalBit / IgnitionTiming / AAC / AFAlphaL / AFAlphaLSelfLear / M/R F/C Mnt /
        self.consume_data() 

    if config.Units_Speed == 1:
        Speed_Units = 'MPH'
        def convertToSpeed(self,inputData):
            return int(round((inputData * 2.11) * 0.621371192237334 * config.Combined_Ratio))
    else:
        Speed_Units = 'KPH'
        def convertToSpeed(self,inputData):
            return int(round((inputData * 2.11)*config.Combined_Ratio))
        
    if config.Units_Temp == 1:
        #Temp_Units = 'F'
        def convertToTemp(self,inputData):
            return (inputData - 50) * 9/5 + 32
    else:
        #Temp_Units = 'C'
        def convertToTemp(self,inputData):
            return inputData - 50

    def convertToRev(self,inputData):
        return int(round((inputData * 12.5),2))

    def convertToBattery(self,inputData):
        return round(((inputData * 80) / 1000),1)

    def convertToMAF(self,inputData):
        return inputData * 5

    def convertToAAC(self,inputData): 
        return inputData / 2

    def convertToInjection(self,inputData):
        return inputData / 100

    def convertToTiming(self,inputData):
        return 110 - inputData

    def logToFile(self,data,fileName):
        with open(fileName + '.hex', 'a+') as logFile:
            logFile.write(data)

READ_THREAD = False
SPEED_Value = 0
RPM_Value = 0
TEMP_Value = 0
BATT_Value = 0
AAC_Value = 0
MAF_Value = 0
Count = 0
if config.Units_Speed == 1:
    Speed_Units = 'MPH'
else:
    Speed_Units = 'KPH'

if config.Units_Temp == 1:
    Temp_Units = 'F'
else:
    Temp_Units = 'C'

    
while READ_THREAD == False:
    try:
        print('Attempting to connect to serial port')
        WriteText('attempting to connect to serial port',None)
        
        PORT.flushInput()
        print('Input flushed')
        WriteText('Input flushed',None)
        time.sleep(0.2)
        
        PORT.write(bytes([0xFF,0xFF,0xEF])) #initialization sequence
        print('Writing initialization')
        WriteText('Writing initialization...','Please wait')
        time.sleep(0.2)

        Connected = PORT.read_all()
        print('Connected',Connected)
        time.sleep(0.2)

        if Connected == b'\x00\x00\x10':
            READ_THREAD = True
            ReadStream(True)
            WriteText('Connected',None)

    # except OSError: # NOTE run some tests and see where we enounter this error
    #     if PORT.is_open:
    #         WriteText('port open')
    #         pass
    #     else:
    #         PORT.open()
    #     WriteText('OSError')
    #     continue

    except ValueError:
        # PORT.open()
        print('value error')

def Increment_Display():
    global DisplayIndex
    DisplayIndex = (DisplayIndex + 1) % 6
    #may need to add a sleep here so it doesn't register multiple presses
    #however I don't know if this will mess things up and cause a delay in serial readings, i think it shouldn't because it's a idfferent thread

DisplayText = ['SPEED','RPM','MAF','AAC','TEMP','BATT'] 
Units = [Speed_Units,'RPM','V','%',Temp_Units,'V']

while READ_THREAD == True:
    # NOTE Ideally creating a new list every loop is not ideal, but it's a quick fix for now
    # Would it be better to use a dictionary?
    DisplayValue = [SPEED_Value,RPM_Value,MAF_Value,AAC_Value,TEMP_Value,BATT_Value] #this should update continuously
    WriteText(DisplayText[DisplayIndex],DisplayValue[DisplayIndex])

    DisplayButton.when_pressed = Increment_Display

    # WriteText(DisplayText[Count],str(DisplayValue[Count]) + Units[Count]) # Not sure if adding the strings here will actually work, needs testing 
    #ideally long term i should rewrite this so that only the value updates. There's no need to redraw the title and units every loop
    time.sleep(0.02)