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
import numpy as np
from Main_Bare_Imports.Read import ReadStream

# OLED screen info
Device_SPI = config.Device_SPI
Device_I2C = config.Device_I2C
OLED_WIDTH   = 128
OLED_HEIGHT  = 64
font1 = ImageFont.truetype('Font.ttc', 18)
font2 = ImageFont.truetype('Font.ttc', 24)

# Button configs
DisplayButton = Button(6) #switch displayed values (i.e. speed, rpm, etc. Or in settings mode switch which setting is shown)

def WriteText(upper,lower): 
    # Writes text to the display

    image = Image.new('1', (128, 64), 255)
    draw = ImageDraw.Draw(image)
    draw.text((20,0),str(upper), font = font1, fill = 0)
    if lower is not None: 
        draw.text((20,24), str(lower), font = font2, fill = 0)
    image = image.rotate(180) 
    disp.ShowImage(disp.getbuffer(image))

def PortConnect(PORT):
    # Tries to connect to serial port

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

def Increment_Display():
    # Increments the display index, which tells us what to show on the screen in READ_THEAD mode

    global DisplayIndex
    DisplayIndex = (DisplayIndex + 1) % 6

if config.Units_Speed == 1:
    Speed_Units = 'MPH'
else:
    Speed_Units = 'KPH'

if config.Units_Temp == 1:
    Temp_Units = 'F'
else:
    Temp_Units = 'C'

PORT = None  # Initialize PORT to None

disp = OLED_2in42.OLED_2in42(spi_freq = 1000000)
disp.Init()

while PORT is None:
    PORT = PortConnect()
    time.sleep(0.1)
    print('PORT = None')
    WriteText('Connecting...','Please wait')

READ_THREAD = False
SPEED_Value = 0
RPM_Value = 0
TEMP_Value = 0
BATT_Value = 0
AAC_Value = 0
MAF_Value = 0
    
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

DisplayText = ['SPEED','RPM','MAF','AAC','TEMP','BATT'] 
Units = [Speed_Units,'RPM','V','%',Temp_Units,'V']

while READ_THREAD == True:
    # NOTE Ideally creating a new list every loop is not ideal, but it's a quick fix for now
    # Long term I should create DisplayValue as a numpy array and update the values in place
    # Just need to figure out how to do that easily since there's different threads

    DisplayValue = [SPEED_Value,RPM_Value,MAF_Value,AAC_Value,TEMP_Value,BATT_Value] #this should update continuously
    WriteText(DisplayText[DisplayIndex],DisplayValue[DisplayIndex])

    DisplayButton.when_pressed = Increment_Display

    time.sleep(0.02)