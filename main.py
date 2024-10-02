# This is intended to be a barebones version of the main.py file
# Once features are implemented and tested, they will be added here
# This serves as a backup and a way to keep core functionality

import sys,os,time,serial,threading,datetime,json #type: ignore
from Resources import config
from Main_Bare_Imports.Settings import Load_Config, Save_Config
import Resources.OLED_2in42 as OLED_2in42
from PIL import Image,ImageDraw,ImageFont
from gpiozero import Button # type: ignore
import numpy as np
from Resources import dtc_dict as DTC_DICT
from Main_Bare_Imports.Read import ReadStream

# OLED screen info
Device_SPI = config.Device_SPI
Device_I2C = config.Device_I2C
OLED_WIDTH   = 128
OLED_HEIGHT  = 64
font1 = ImageFont.truetype('Font.ttc', 18)
font2 = ImageFont.truetype('Font.ttc', 20)

# Button configs
DisplayButton = Button(6) #switch displayed values (i.e. speed, rpm, etc. Or in settings mode switch which setting is shown)
PeakButton = Button(16) # Show peak value of current mode
SettingButton = Button(26)

# ModeButton = Button() # Switch between modes
# PowerButton = Button() # Power button to turn off the device
# PowerButton.hold_time = 2 # Hold for 2 seconds to shut down

# General Configs

Settings = Load_Config()

Units_Speed = Settings["Units_Speed"]
Units_Temp = Settings["Units_Temp"]
Stock_Tire_Height = Settings["Stock_Tire_Height"]
Stock_Tire_AR = Settings["Stock_Tire_AR"]
Stock_Tire_Diam = Settings["Stock_Tire_Diam"]
New_Tire_Height = Settings["New_Tire_Height"]
New_Tire_AR = Settings["New_Tire_AR"]
New_Tire_Diam = Settings["New_Tire_Diam"]
Default_Display = Settings["Default_Display"]
Injector_Size = Settings["Injector_Size"]

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
            if PORT.is_open:  # Check if PORT is not None and is open
                WriteText('Port is open',None)
        else:
            if PORT:
                PORT.open()  # port is not none but is closed
            else:
                WriteText('Init Fail',None)  # Handle the case where PORT is still None
    return PORT

def ECU_Connect(PORT,ECU_CONNECTED):
    # Attempts to connect to the ECU using the initialization sequence.
    # Then depending on which mode we want we can send the mode-specific
    # initialization sequence
    
    while ECU_CONNECTED == False:
        try:
            WriteText('Connecting...','Please wait')
            
            PORT.flushInput()
            WriteText('Input flushed','Please wait')
            time.sleep(0.1)
            
            PORT.write(bytes([0xFF,0xFF,0xEF])) #initialization sequence
            WriteText('Writing init...','Please wait')
            time.sleep(0.1)

            Connected = PORT.read_all()

            if Connected == b'\x00\x00\x10':
                WriteText('Connected',None)
                ECU_CONNECTED = True

            else: # NOTE might be able to remove this
                PORT = PortConnect(PORT)

        except ValueError:
            # PORT.open()
            print('Value error')
    return ECU_CONNECTED

def Increment_Display():
    # Increments the display index, which tells us what to show on the screen in READ_THEAD mode
    global DisplayIndex
    DisplayIndex = (DisplayIndex + 1) % 10

def Increment_DTC():
    global DTCIndex
    DTCIndex = (DTCIndex + 1) % len(DTC_Codes)

def Increment_Settings():
    # Increments the settings index, which tells us what to show on the screen in SETTINGS_THREAD mode
    global SettingIndex
    SettingIndex = (SettingIndex + 1) % 6

def Show_Peak():
    global DisplayIndex
    WriteText('Peak'+str(DisplayText[DisplayIndex]),str(PeakValues[DisplayIndex])+str(Units[DisplayIndex]))
    time.sleep(1.5)

def Shutdown():
    global disp, READ_THREAD, DTC_THREAD
    # Shuts down the device
    WriteText('Shutting down',None) 
    time.sleep(1)
    disp.clear()
    disp.module_exit()
    READ_THREAD = False
    DTC_THREAD = False
    os.system('sudo shutdown now')

if config.Units_Speed == 1:
    Speed_Units = 'MPH'
else:
    Speed_Units = 'KPH'

if config.Units_Temp == 1:
    Temp_Units = 'F'
else:
    Temp_Units = 'C'

SettingIndex = 0
DisplayIndex = Default_Display

DisplayValues = np.zeros(10)
DisplayText = ['RPM','SPEED','MAF','AAC','TEMP','BATT','INJ','TIM','TPS','EFF'] 

SettingText = ['Speed Units','Temp Units','Final Drive', 'Tire Size', 'Injector Size', 'Default Display']
SettingValues = [Units_Speed,Units_Temp,config.Combined_Ratio,New_Tire_Height,config.Injector_Size,DisplayText[Default_Display]]

PeakValues = np.zeros(10)
Units = ['RPM',Speed_Units,'V','%',Temp_Units,'V','%','deg','%','EFF']
DTC_Codes = []
DTC_Counts = []
DTCIndex = 0

disp = OLED_2in42.OLED_2in42(spi_freq = 1000000)
disp.Init()

READ_THREAD = False
DTC_THREAD = False
SETTINGS_THREAD = False
TESTS_THREAD = False

PORT = None
ECU_CONNECTED = False

while PORT is None:
    PORT = PortConnect(PORT)
    # time.sleep(0.1)
    WriteText('Connecting...','Please wait')

####################################### Main loop #######################################

ECU_CONNECTED = ECU_Connect(PORT,ECU_CONNECTED) # This will connect to the ECU using initialization sequence '0xFF,0xFF,0xEF'

if ECU_CONNECTED == True:
    # if Mode == 0: # NOTE Placeholder for when we set up the modes
    READ_THREAD = True
    R = ReadStream(port=PORT, daemon=True)
    time.sleep(0.1)
    
while READ_THREAD == True:
    DisplayValues[:] = int(R.RPM_Value),int(R.SPEED_Value),R.MAF_Value,R.AAC_Value,int(R.TEMP_Value),R.BATT_Value,R.INJ_Value,int(R.TIM_Value),R.TPS_Value,R.FUEL_Value
    WriteText(DisplayText[DisplayIndex],str(DisplayValues[DisplayIndex])+str(Units[DisplayIndex]))
    for i in range(len(DisplayValues)):
        if DisplayValues[i] > PeakValues[i]:
            PeakValues[i] = DisplayValues[i]

    DisplayButton.when_pressed = Increment_Display
    if PeakButton.is_pressed:
        Show_Peak()

    # PowerButton.when_held = Shutdown

    time.sleep(0.02)

while DTC_THREAD == True:
    WriteText('Code: '+str(DTC_Codes[DTCIndex])+str(' Count:')+str(DTC_Counts[DTCIndex]),str(DTC_DICT[DTC_Codes[DTCIndex]]))
    DisplayButton.when_pressed = Increment_DTC

while SETTINGS_THREAD == True:
    WriteText(SettingText[SettingIndex],SettingValues[SettingIndex]) # We probably only need to run this one instead of updating it every time the loop cycles

    DisplayButton.when_pressed = Increment_Settings
    
    if SettingButton.is_pressed:
        if SettingIndex == 0:
            if Units_Speed == 'MPH':
                Units_Speed = 'KPH'
                SettingValues[SettingIndex] = Units_Speed
                Settings["Units_Speed"] = Units_Speed
                Save_Config(Settings)

            elif Units_Speed == 'KPH':
                Units_Speed = 'MPH'
                SettingValues[SettingIndex] = Units_Speed
                Settings["Units_Speed"] = Units_Speed
                Save_Config(Settings)

        if SettingIndex == 1:
            if Units_Temp == 'F':
                Units_Temp = 'C'
                SettingValues[SettingIndex] = Units_Temp
                Settings["Units_Temp"] = Units_Temp
                Save_Config(Settings)

            elif Units_Temp == 'C':
                Units_Temp = 'F'
                SettingValues[SettingIndex] = Units_Temp
                Settings["Units_Temp"] = Units_Temp
                Save_Config(Settings)

        if SettingIndex == 2:
            pass

        if SettingIndex == 3:
            pass

        if SettingIndex == 4:
            pass

        if SettingIndex == 5:
            Default_Display = (Default_Display + 1) % 10
            SettingValues[SettingIndex] = DisplayText[Default_Display]
            Settings["Default_Display"] = Default_Display
            Save_Config(Settings)