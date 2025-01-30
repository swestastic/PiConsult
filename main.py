### Current Issues:
### 1. Some issues with DisplayButton not always cycling properly, or it will only work consistently if you hit PeakButton first
### 2. PeakButton does not hold the Peak display for the full 1.5 seconds, it only shows for one frame.

import sys,os,time,serial,threading,datetime,json #type: ignore
from Resources import config
from Main_Bare_Imports.Settings import Load_Config, Save_Config
import Resources.OLED_2in42 as OLED_2in42
from PIL import Image,ImageDraw,ImageFont
from gpiozero import Button # type: ignore
import numpy as np
from Resources import dtc_dict as DTC_DICT
from Main_Bare_Imports.Read import ReadStream
from Main_Bare_Imports.Flash import FlashText, Center_Text
import socket

def get_local_ip():
    try:
        # Connect to an external IP to find the local IP address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Google DNS server, doesn't actually send data
        ip_addr = s.getsockname()[0]
        s.close()
        return ip_addr
    except Exception as e:
        return None
        # return f"Error occurred: {e}"

IPAddr = get_local_ip()

# OLED screen info
Device_SPI = config.Device_SPI
Device_I2C = config.Device_I2C
OLED_WIDTH   = 128
OLED_HEIGHT  = 64
font1 = ImageFont.truetype('Font.ttc', 18)
font2 = ImageFont.truetype('Font.ttc', 20)

# Button configs
DisplayButton = Button(23, hold_time=0.25) #switch displayed values (i.e. speed, rpm, etc. Or in settings mode switch which setting is shown)
PeakButton = Button(16, hold_time=0.25) # Show peak value of current mode
SelectButton = Button(26, hold_time=0.25)
ModeButton = Button(17, hold_time=0.25) # Switch between modes

# General Configs
CONF = 'configJSON.json' # config file
Settings = Load_Config(CONF)

Units_Speed = Settings["Units_Speed"] # Farenheit or Celsius
Units_Temp = Settings["Units_Temp"] # MPH or KPH
Stock_Tire_Height = Settings["Stock_Tire_Height"] # Stock tire height
Stock_Tire_AR = Settings["Stock_Tire_AR"] # Stock tire aspect ratio
Stock_Tire_Diam = Settings["Stock_Tire_Diam"] # Stock tire diameter
New_Tire_Height = Settings["New_Tire_Height"] # New tire height
New_Tire_AR = Settings["New_Tire_AR"] # New tire aspect ratio
New_Tire_Diam = Settings["New_Tire_Diam"] # New tire diameter
Default_Display = Settings["Default_Display"] # Default display when in READ_THREAD mode
Injector_Size = Settings["Injector_Size"] # Injector size
Coolant_Warning = Settings["Coolant_Warning"] # Coolant warning temperature
RPM_Warning = Settings["RPM_Warning"] # RPM warning value
PWM_Index = Settings["PWM_Index"] # PWM index, 999 is off

def WriteText(upper,lower): 
    # Writes text to the display
    image = Image.new('1', (128, 64), 255)
    draw = ImageDraw.Draw(image)
    if upper is not None:
        draw.text((20,0),str(upper), font = font1, fill = 0)
    if lower is not None: 
        draw.text((20,24), str(lower), font = font2, fill = 0)
    image = image.rotate(180) 
    disp.ShowImage(disp.getbuffer(image))

def PortConnect(PORT, IPAddr):
    # Tries to connect to serial port
    WriteText('Connecting...',IPAddr)
            
    try:
        PORT = serial.Serial('/dev/ttyUSB0', 9600, timeout=None)
    except OSError:
        if PORT:
            if PORT.is_open:  # Check if PORT is not None and is open
                IPAddr = get_local_ip() # Update the IP address
                WriteText('Port is open',str(IPAddr))
        else:
            if PORT:
                PORT.open()  # port is not none but is closed
            else:
                IPAddr = get_local_ip() # Update the IP address
                WriteText('Init Fail',str(IPAddr))  # Handle the case where PORT is still None
    return PORT, IPAddr

def ECU_Connect(PORT,ECU_CONNECTED,IPAddr):
    # Attempts to connect to the ECU using the initialization sequence.
    # Then depending on which mode we want we can send the mode-specific
    # initialization sequence
    
    while ECU_CONNECTED == False:
        try:
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
                PORT, IPAddr = PortConnect(PORT,IPAddr)

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

def reset_display():
    # Function to reset the display to normal updates.
    global ShowingPeak
    ShowingPeak = False  # Reset state to normal updates

def Show_Peak(DisplayIndex):
    global ShowingPeak
    ShowingPeak = True
    threading.Timer(1.5, reset_display).start()
    WriteText(None,None) # Clear the display
    while ShowingPeak == True:
        WriteText(str(DisplayText[DisplayIndex])+' PEAK',str(PeakValues[DisplayIndex])+str(Units[DisplayIndex]))
    

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
Units = ['RPM',Speed_Units,'V','%',Temp_Units,'V','%','deg','V','EFF']
DTC_Codes = []
DTC_Counts = []
DTCIndex = 0

disp = OLED_2in42.OLED_2in42(spi_freq = 1000000)
disp.Init()

READ_THREAD = False
DTC_THREAD = False
SETTINGS_THREAD = False
ShowingPeak = False

PORT = None
ECU_CONNECTED = False

while PORT is None:
    PORT, IPAddr = PortConnect(PORT,IPAddr)
    # time.sleep(0.1)
    WriteText('Connecting...',IPAddr)

####################################### Main loop #######################################

ECU_CONNECTED = ECU_Connect(PORT,ECU_CONNECTED,IPAddr) # This will connect to the ECU using initialization sequence '0xFF,0xFF,0xEF'

if ECU_CONNECTED == True:
    # if Mode == 0: # NOTE Placeholder for when we set up the modes
    READ_THREAD = True # this tells us to start displaying info on the screen
    R = ReadStream(port=PORT, daemon=True) # This sends init and ingests data from the ECU in a separate thread 
    time.sleep(0.1)
    
while READ_THREAD == True:
    if not ShowingPeak:
        DisplayValues[:] = int(R.RPM_Value),int(R.SPEED_Value),R.MAF_Value,R.AAC_Value,int(R.TEMP_Value),R.BATT_Value,R.INJ_Value,int(R.TIM_Value),R.TPS_Value,R.FUEL_Value
        WriteText(DisplayText[DisplayIndex],str(DisplayValues[DisplayIndex])+str(Units[DisplayIndex]))
        for i in range(len(DisplayValues)):
            if DisplayValues[i] > PeakValues[i]:
                PeakValues[i] = DisplayValues[i]

        DisplayButton.when_held = Increment_Display
        PeakButton.when_held = lambda: Show_Peak(DisplayIndex)

        if R.RPM_Value > RPM_Warning:
            FlashText("REV LIMIT!", font1, disp, R.RPM_Value, flashes=6, flash_interval=0.125)

        if R.TEMP_Value > Coolant_Warning:
            FlashText("OVERHEAT!", font1, disp, R.TEMP_Value, flashes=6, flash_interval=0.125)
        time.sleep(0.02)

# while DTC_THREAD == True:
#     WriteText('Code: '+str(DTC_Codes[DTCIndex])+str(' Count:')+str(DTC_Counts[DTCIndex]),str(DTC_DICT[DTC_Codes[DTCIndex]]))
#     DisplayButton.when_held = Increment_DTC

# while SETTINGS_THREAD == True:
#     WriteText(SettingText[SettingIndex],SettingValues[SettingIndex]) # We probably only need to run this one instead of updating it every time the loop cyc
#     DisplayButton.when_held = Increment_Settings
    
#     if SelectButton.is_held: # change the value of the setting
#         if SettingIndex == 0: # Speed Units
#             if Units_Speed == 'MPH':
#                 Units_Speed = 'KPH'
#                 SettingValues[SettingIndex] = Units_Speed
#                 Settings["Units_Speed"] = Units_Speed
#                 Save_Config(CONF,Settings)

#             elif Units_Speed == 'KPH':
#                 Units_Speed = 'MPH'
#                 SettingValues[SettingIndex] = Units_Speed
#                 Settings["Units_Speed"] = Units_Speed
#                 Save_Config(CONF,Settings)

#         if SettingIndex == 1: # Temp Units
#             if Units_Temp == 'F':
#                 Units_Temp = 'C'
#                 SettingValues[SettingIndex] = Units_Temp
#                 Settings["Units_Temp"] = Units_Temp
#                 Save_Config(CONF,Settings)

#             elif Units_Temp == 'C':
#                 Units_Temp = 'F'
#                 SettingValues[SettingIndex] = Units_Temp
#                 Settings["Units_Temp"] = Units_Temp
#                 Save_Config(CONF,Settings)

#         if SettingIndex == 2: # Number of display Items
#             pass

#         if SettingIndex == 3: # Default Display
#             Default_Display = (Default_Display + 1) % 10
#             SettingValues[SettingIndex] = DisplayText[Default_Display]
#             Settings["Default_Display"] = Default_Display
#             Save_Config(CONF,Settings)

#         if SettingIndex == 4: # Speed Correction 
#             pass

#         if SettingIndex == 5: # TPS Calibration
#             pass

#         if SettingIndex == 6: # Data Logging On/Off
#             pass

#         if SettingIndex == 7: # PWM On/Off
#             pass

#         if SettingIndex == 8: # WiFi On/Off
#             pass

