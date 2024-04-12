#!/usr/bin/python
# dashboard.py

#Copyright (C) 2014 Eilidh Fridlington http://eilidh.fridlington.com

#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <http://www.gnu.org/licenses/>







import sys
import os
#import pygame
import time
import math
#from pygame.locals import *
#import pygame.gfxdraw
import serial
import threading
import datetime
import config
import OLED_2in42
from PIL import Image,ImageDraw,ImageFont
from gpiozero import Button

#os.environ['SDL_VIDEO_WINDOW_POS'] = 'center'

OLED_WIDTH   = 128 #OLED width #there is also a duplicate of this further down, can probably remove one of them
OLED_HEIGHT  = 64  #OLED height

ModeButton = Button(2) #switch modes using a button attached to GPIO Pin 2
PeakButton = Button(3) #show peak values using a button attached to GPIO Pin 3

#pygame.init()
# picdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'pic')
# print(picdir)
font1 = ImageFont.truetype('Font.ttc', 18)
font2 = ImageFont.truetype('Font.ttc', 24)
def writetext(upper,lower):
    image = Image.new('1', (128, 64), 255)
    draw = ImageDraw.Draw(image)
    draw.text((20,0),str(upper), font = font1, fill = 0)
    if lower is not None: 
        draw.text((20,24), str(lower), font = font2, fill = 0)
    image = image.rotate(180) 
    disp.ShowImage(disp.getbuffer(image))

PORT = None  # Initialize PORT to None

def portconnect():
    global PORT
    try:
        PORT = serial.Serial('/dev/ttyUSB0', 9600, timeout=None)
    except OSError:
        if PORT:
            print('Port is not none')
            if PORT.is_open:  # Check if PORT is not None and is open
                print('Port is open')
                # writetext('Port open')
        else:
            if PORT:
                PORT.open()  # port is not none but is closed
            else:
                print('Failed to initialize PORT')  # Handle the case where PORT is still None
while PORT is None:
    portconnect()
    time.sleep(1)
    print('PORT = None')
    #writetext('PORT=None')
# portconnect()

# if PORT is not None:
#     pass
# else:
#     #writetext('PORT=None')
#     print('PORT = None')
#     #portconnect()

########################################################################
class ReadStream(threading.Thread):

    def __init__(self, daemon):
        threading.Thread.__init__(self)
        self.daemon = daemon
        self.MPH_Value = 0
        self. RPM_Value = 0
        self. TEMP_Value = 0
        self. BATT_Value = 0
        self. MAF_Value = 0
        self. AAC_Value = 0
        self. INJ_Value = 0
        self. TIM_Value = 0
        
        read_Thread = True;
        self.Header = 255
        self.returnBytes = 14
        fileName = datetime.datetime.now().strftime("%d-%m-%y-%H-%M")
        
        self.start()
        
        
    def check_data_size(data_list):
        Header = 255
        returnBytes = 14
        try:
            # if dataList[-4] != self.Header:
            #     return False
            # if dataList[-3] != self.returnBytes:
            #         return False   
            if data_list[-4] != Header:
                return False
            if data_list[-3] != returnBytes:
                return False   
                    
        except (ValueError, IndexError):
            return False
        return True
                
    def consume_data(self):
        global MPH_Value, RPM_Value, TEMP_Value, BATT_Value, MAF_Value, AAC_Value, INJ_Value, TIM_Value
        read_thread = True
        while read_thread:
            incomingData = PORT.read(16)
            #incomingData = str(incomingData)
            #print('incomingData',incomingData)
            if incomingData:
                dataList = list(incomingData)
                #dataList = map(ord,incomingData)
                #dataList = list(dataList)
                
                #print('datalist',list(dataList))
                #print('typedatalist',type(list(dataList)))
                #print('datalistzero',list(dataList)[0])

            if not self.check_data_size(dataList): ##BROKEN!!! FIX ME
                continue
                
            try:
                MPH_Value = self.convertToMPH(int(dataList[-2]))
                RPM_Value = self.convertToRev(int(dataList[-1]))
                TEMP_Value = self.convertToTemp(int(dataList[0]))
                BATT_Value = self.convertToBattery(float(dataList[1]))
                MAF_Value = self.convertToMAF(int(dataList[5]))
                AAC_Value = self.convertToAAC(int(dataList[8]))


                # print('mph',MPH_Value)
                # print('rpm',RPM_Value)
                # print('temp',TEMP_Value)
                # print('batt',BATT_Value)   
                # print('aac',AAC_Value)
                # print('maf',MAF_Value)
                  
            except (ValueError, IndexError):
                   pass         
            time.sleep(0.002)

    def run(self):
        #PORT.write('\x5A\x0B\x5A\x01\x5A\x08\x5A\x0C\x5A\x0D\x5A\x03\x5A\x05\x5A\x09\x5A\x13\x5A\x16\x5A\x17\x5A\x1A\x5A\x1C\x5A\x21\xF0')
        PORT.write(bytes([0x5A,0x0B,0x5A,0x01,0x5A,0x08,0x5A,0x0C,0x5A,0x0D,0x5A,0x03,0x5A,0x05,0x5A,0x09,0x5A,0x13,0x5A,0x16,0x5A,0x17,0x5A,0x1A,0x5A,0x1C,0x5A,0x21,0xF0]))
        #? Speed ? CAS/RPM ? CoolantTemp ? BatteryVoltage ? ThrottlePosition ? CAS/RPM ? MAF ? LH02 ? DigitalBit ? IgnitionTiming ? AAC ? AFAlphaL ? AFAlphaLSelfLear ? M/R F/C Mnt ?
        #cant think of  a reason for declerations and initialisations to be seperate
        self.consume_data() 
    
    def convertToMPH(self,inputData):
        return int(round ((inputData * 2.11) * 0.621371192237334)) #add a toggle for changing this to kph?

    def convertToRev(self,inputData):
        return int(round((inputData * 12.5),2))

    def convertToTemp(self,inputData): #add a toggle for changing this to farenheight? 
        return inputData - 50

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
MPH_Value = 0
RPM_Value = 0
TEMP_Value = 0
BATT_Value = 0
AAC_Value = 0
MAF_Value = 0
Count = 0

disp = OLED_2in42.OLED_2in42(spi_freq = 1000000)
disp.Init()
# Device_SPI = config.Device_SPI
# Device_I2C = config.Device_I2C

Device_SPI = 1 #might be able to get rid of these since i fixed config.py reference? needs testing
Device_I2C = 0

OLED_WIDTH   = 128 #OLED width
OLED_HEIGHT  = 64  #OLED height
    
while READ_THREAD == False:
    try:
        print('attempting to connect to serial port')
        writetext('attempting to connect to serial port',None)
        
        PORT.flushInput()
        print('flushed input')
        writetext('flushed input',None)
        time.sleep(0.5)
        
        #PORT.write(b'\xFF\xFF\xEF') #had to add the b because i was getting a typeerror
        PORT.write(bytes([0xFF,0xFF,0xEF]))
        print('write to port')
        writetext('writing data',None)
        time.sleep(0.5)
        #PORT.read(1)
        #Connected = PORT.read(1)
        Connected = PORT.read_all()
        print('connected',Connected)
        if Connected == b'\x00\x00\x10':
            READ_THREAD = True
            ReadStream(True)
            writetext('connected',None)

    # except OSError:
    #     if PORT.is_open:
    #         writetext('port open')
    #         pass
    #     else:
    #         PORT.open()
    #     writetext('OSError')
    #     continue

    except ValueError:
        # PORT.open()
        print('value error')


def Increment_Mode():
    global Count
    Count += 1
    if Count > 5:
        Count = 0
    #may need to add a sleep here so it doesn't register multiple presses
    #however I don't know if this will mess things up and cause a delay in serial readings
DisplayText = ['MPH','RPM','MAF','AAC','TEMP','BATT'] #moved this outside so it's not set every loop
PeakValues = [0,0,0,0,0,0]

def Show_Peak():
    global Count
    writetext(PeakValues[Count]) #Modify writetext to allow for writing to the upper right or something for peak value

while READ_THREAD == True:
    DisplayValue = [MPH_Value,RPM_Value,MAF_Value,AAC_Value,TEMP_Value,BATT_Value] #this should update continuously
    # for i in range(len(DisplayValue)):
    #     if PeakValues[i] < DisplayValue[i]: #update the peak value if the current value is higher
    #         PeakValues[Count] = DisplayValue[Count]

    writetext(DisplayText[Count],DisplayValue[Count])

    ModeButton.when_pressed = Increment_Mode
    # PeakButton.while_pressed = Show_Peak
    # if ModeButton.is_pressed:
    #     Count += 1
    #     if Count > 5:
    #         Count = 0
    # #print('READ_THREAD true')
    # print('BATT_Value',BATT_Value) #this is not updating for some reason
    # writetext('RPM',RPM_Value)

    time.sleep(0.02)

    
# while READ_THREAD == True:

#     pygame.time.Clock().tick(60)

#     for event in pygame.event.get():

#         if event.type==pygame.QUIT:
#             PORT.flushInput()
#             PORT.close()
#             sys.exit()

#         if event.type is KEYDOWN and event.key == K_q:
#             PORT.flushInput()
#             PORT.close()
#             sys.exit()

#         if event.type is KEYDOWN and event.key == K_w:
#             pygame.display.set_mode((width,height))
#             pygame.mouse.set_visible(False)
#             surface1X = surface1WindowedX
#             surface1Y = surface1WindowedY
#             surface2X = surface2WindowedX
#             surface2Y = surface2WindowedY
#             surface3X = surface3WindowedX
#             surface3Y = surface3WindowedY
#             surface4X = surface4WindowedX
#             surface4Y = surface4WindowedY
#             surface5X = surface5WindowedX
#             surface5Y = surface5WindowedY
#             surface6X = surface6WindowedX
#             surface6Y = surface6WindowedY
#             screen.fill(0x000000)

#         if event.type is KEYDOWN and event.key == K_f:
#             pygame.display.set_mode((monitorX,monitorY), FULLSCREEN)
#             surface1X = surface1FullscreenX
#             surface1Y = surface1FullscreenY
#             surface2X = surface2FullscreenX
#             surface2Y = surface2FullscreenY
#             surface3X = surface3FullscreenX
#             surface3Y = surface3FullscreenY
#             surface4X = surface4FullscreenX
#             surface4Y = surface4FullscreenY
#             surface5X = surface5FullscreenX
#             surface5Y = surface5FullscreenY
#             surface6X = surface6FullscreenX
#             surface6Y = surface6FullscreenY
#             screen.fill(0x000000)
#             pygame.mouse.set_visible(False)

#     surface1.fill(0x000000)
#     surface2.fill(0x0000FF)
#     surface3.fill(0x0000FF)
#     surface4.fill(0x0000FF)
#     surface5.fill(0x0000FF)
#     surface6.fill(0x0000FF)

#     indicatorNeedle(surface1,MPH_Value,648,650,650,sixty,BLACK,0,0,10,12,6,1,False,False)
#     indicatorNeedle(surface2,RPM_Value,488,500,500,sixty,BLACK,0,0,500,10,5,100,False,False)
#     indicatorNeedle(surface3,MAF_Value,168,170,170,twenty,BLACK,-45,-45,50,6,3,10,True,False,"MAF",millivolt)
#     indicatorNeedle(surface4,AAC_Value,168,170,170,twenty,BLACK,45,45,10,6,3,1,True,False,"AAC",percent)
#     indicatorNeedle(surface5,TEMP_Value,148,150,150,twenty,BLACK,-45,45,16,6,3,1,True,False,"Temperature",degree)
#     indicatorNeedle(surface6,BATT_Value,148,150,150,twenty,BLACK,-45,45,2,6,3,1,True,False,"Battery",volt)


#     screen.blit(surface1,(surface1X,surface1Y))
#     screen.blit(surface2,(surface2X,surface2Y))
#     screen.blit(surface3,(surface3X,surface3Y))
#     screen.blit(surface4,(surface4X,surface4Y))
#     screen.blit(surface5,(surface5X,surface5Y))
#     screen.blit(surface6,(surface6X,surface6Y))

#     #time.sleep(0.02)

#     pygame.display.update()
