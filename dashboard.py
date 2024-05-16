import sys
import os
import time
import math
import serial
import threading
import datetime
import config
import OLED_2in42
from PIL import Image,ImageDraw,ImageFont
from gpiozero import Button

# OLED screen info
Device_SPI = config.Device_SPI
Device_I2C = config.Device_I2C
OLED_WIDTH   = 128
OLED_HEIGHT  = 64
font1 = ImageFont.truetype('Font.ttc', 18)
font2 = ImageFont.truetype('Font.ttc', 24)

# Button configs
ModeButton = Button() #switch modes (data stream, DTC, test, settings)
DisplayButton = Button(6) #switch displayed values using a button attached to GPIO Pin 6
PeakButton = Button(16) #show peak values using a button attached to GPIO Pin 16
PowerButton = Button()


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
        else:
            if PORT:
                PORT.open()  # port is not none but is closed
            else:
                print('Failed to initialize PORT')  # Handle the case where PORT is still None
disp = OLED_2in42.OLED_2in42(spi_freq = 1000000)
disp.Init()
while PORT is None:
    portconnect()
    time.sleep(1)
    print('PORT = None')
    writetext('port','port')

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
        
        read_Thread = True;
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
        global SPEED_Value, RPM_Value, TEMP_Value, BATT_Value, MAF_Value, AAC_Value, INJ_Value, TIM_Value
        read_thread = True
        while read_thread:
            incomingData = PORT.read(16)
            if incomingData:
                dataList = list(incomingData)

            # if not self.check_data_size(dataList): ##BROKEN!!! FIX ME
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

    def run(self):
        #PORT.write('\x5A\x0B\x5A\x01\x5A\x08\x5A\x0C\x5A\x0D\x5A\x03\x5A\x05\x5A\x09\x5A\x13\x5A\x16\x5A\x17\x5A\x1A\x5A\x1C\x5A\x21\xF0')
        PORT.write(bytes([0x5A,0x0B,0x5A,0x01,0x5A,0x08,0x5A,0x0C,0x5A,0x0D,0x5A,0x03,0x5A,0x05,0x5A,0x09,0x5A,0x13,0x5A,0x16,0x5A,0x17,0x5A,0x1A,0x5A,0x1C,0x5A,0x21,0xF0]))
        #? Speed ? CAS/RPM ? CoolantTemp ? BatteryVoltage ? ThrottlePosition ? CAS/RPM ? MAF ? LH02 ? DigitalBit ? IgnitionTiming ? AAC ? AFAlphaL ? AFAlphaLSelfLear ? M/R F/C Mnt ?
        #cant think of  a reason for declerations and initialisations to be seperate
        self.consume_data() 
    
    if config.Units_MPH == 1:
        #Speed_Units = 'MPH'
        def convertToSpeed(self,inputData):
            return int(round((inputData * 2.11) * 0.621371192237334 * config.Combined_Ratio))
    else:
        #Speed_Units = 'KPH'
        def convertToSpeed(self,inputData):
            return int(round((inputData * 2.11)*config.Combined_Ratio))
        
    if config.Units_Farenheight == 1:
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

# disp = OLED_2in42.OLED_2in42(spi_freq = 1000000)
# disp.Init()
    
while READ_THREAD == False:
    try:
        print('attempting to connect to serial port')
        writetext('attempting to connect to serial port',None)
        
        PORT.flushInput()
        print('flushed input')
        writetext('flushed input',None)
        time.sleep(0.5)
        
        PORT.write(bytes([0xFF,0xFF,0xEF])) #initialization sequence
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


def Increment_Display():
    global Count
    Count += 1
    if Count > 5:
        Count = 0
    #may need to add a sleep here so it doesn't register multiple presses
    #however I don't know if this will mess things up and cause a delay in serial readings
DisplayText = ['SPEED','RPM','MAF','AAC','TEMP','BATT'] #moved this outside so it's not set every loop
#Units = [Speed_Units,'RPM','V','%',Temp_Units,'V']
PeakValues = [0,0,0,0,0,0]

def Show_Peak():
    global Count
    writetext(PeakValues[Count]) #Modify writetext to allow for writing to the upper right or something for peak value

def SettingsMode():
    writetext('Temp Units','') #second one should be the current units, referenced from config?
    DisplayButton.when_pressed = None #This should be a function that shows the next setting
    PeakButton.when_pressed - None #This should be a function that changes the value of the current setting


def Increment_Mode():
    global Mode
    Mode += 1 
    if Mode > 3:
        Mode = 0
    
    #first we need to send a stop bit so the ECU stops sending data
    PORT.write(bytes([0x30])
               
    #then we need to initialize whichever mode we're switching to
    if Mode == 0: #data stream
        writetext('data stream',None)
        PORT.write(bytes([0x5A,0x0B,0x5A,0x01,0x5A,0x08,0x5A,0x0C,0x5A,0x0D,0x5A,0x03,0x5A,0x05,0x5A,0x09,0x5A,0x13,0x5A,0x16,0x5A,0x17,0x5A,0x1A,0x5A,0x1C,0x5A,0x21,0xF0]))
    if Mode == 1: #DTC
        writeText('DTC',None)
        ModeButton.wait_for_press(timeout=3.0) #allow for a 3 second window to keep selecting modes 
            if ModeButton.is_pressed:
                Mode += 1
        PORT.write(bytes([0xD1])) #Tell ECU to send DTCs
    if Mode == 2: #test
        ModeButton.wait_for_press(timeout=3.0) #allow for a 3 second window to keep selecting modes 
                if ModeButton.is_pressed:
                    Mode += 1
        #PORT.write(bytes([0xD2]))
    if Mode == 3: #settings
        ModeButton.wait_for_press(timeout=3.0) #allow for a 3 second window to keep selecting modes 
            if ModeButton.is_pressed:
                Mode += 1
        SettingsMode()
        

def StreamData():
    global SPEED_Value, RPM_Value, TEMP_Value, BATT_Value, MAF_Value, AAC_Value
    DisplayValue = [SPEED_Value,RPM_Value,MAF_Value,AAC_Value,TEMP_Value,BATT_Value] #this should update continuously
    for i in range(len(DisplayValue)):
        if PeakValues[i] < DisplayValue[i]: #update the peak value if the current value is higher
            PeakValues[i] = DisplayValue[i]
    writetext(DisplayText[Count],DisplayValue[Count])

def Modes():
    global Mode
    if Mode == 0: #data steam
        StreamData()
    if Mode == 1: # dtc
        pass
    if Mode == 2: # test
        pass
    if Mode == 3: # settings
        pass
        
def Shutdown():
    os.system('sudo shutdown -h now')

while READ_THREAD == True:
    #might be a more efficient way to do this, so we're not copying the values every loop
    #maybe a list of names that points to the value or something? 
    
    DisplayValue = [SPEED_Value,RPM_Value,MAF_Value,AAC_Value,TEMP_Value,BATT_Value] #this should update continuously
    
    for i in range(len(DisplayValue)):
        if PeakValues[i] < DisplayValue[i]: #update the peak value if the current value is higher
            PeakValues[i] = DisplayValue[i]

    writetext(DisplayText[Count],DisplayValue[Count])

    DisplayButton.when_pressed = Increment_Display
    PeakButton.while_pressed = Show_Peak
    ModeButton.when_pressed = Increment_Mode
    PowerButton.when_pressed = Shutdown

    #writetext(DisplayText[Count],str(DisplayValue[Count]) + Units[Count]) # Not sure if adding the strings here will actually work, needs testing 
    #ideally long term i should rewrite this so that only the value updates. There's no need to redraw the title and units every loop
    time.sleep(0.02)