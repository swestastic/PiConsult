import sys, os, time, serial, threading, datetime, json
from Resources import config
from Utils.Settings import Load_Config, Save_Config
import Resources.OLED_2in42 as OLED_2in42
from PIL import Image, ImageDraw, ImageFont
from gpiozero import Button # type: ignore
from Utils.Read import ReadStream
from Utils.Flash import FlashText
from Utils.Logs import Create_Log_File, WriteLog
import socket
import numpy as np
import queue

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_addr = s.getsockname()[0]
        s.close()
        return ip_addr
    except Exception as e:
        WriteLog(Log_Index, e, "Getting local IP address")
        return "N/A"

# Initialize display
OLED_WIDTH, OLED_HEIGHT = 128, 64
font1 = ImageFont.truetype('Resources/Font.ttc', 18)
font2 = ImageFont.truetype('Resources/Font.ttc', 20)

def WriteText(upper, lower):
    image = Image.new('1', (OLED_WIDTH, OLED_HEIGHT), 255)
    draw = ImageDraw.Draw(image)
    if upper is not None:
        draw.text((20, 0), str(upper), font=font1, fill=0)
    if lower is not None:
        draw.text((20, 24), str(lower), font=font2, fill=0)
    disp.ShowImage(disp.getbuffer(image.rotate(180)))

# Load configs
CONF = 'Resources/configJSON.json'
Settings = Load_Config(CONF)
Settings["Log_Index"] += 1
Save_Config(CONF, Settings)
Log_Index = Settings["Log_Index"]
Create_Log_File(Log_Index)

Units_Speed = Settings["Units_Speed"]
Units_Temp = Settings["Units_Temp"]
Default_Display = Settings["Default_Display"]
RPM_Warning = Settings["RPM_Warning"]
Coolant_Warning = Settings["Coolant_Warning"]

# SPI/I2C OLED init
disp = OLED_2in42.OLED_2in42(spi_freq=1000000)
disp.Init()

# Buttons
DisplayButton = Button(23, hold_time=0.5)
PeakButton    = Button(16, hold_time=0.5)
SelectButton  = Button(26, hold_time=0.5)
ModeButton    = Button(17, hold_time=0.5)

# Shared state
DisplayIndex = Default_Display
PeakValues = np.zeros(10)
DisplayValues = np.zeros(10)
DisplayText = ['RPM','SPEED','MAF','AAC','TEMP','BATT','INJ','TIM','TPS','EFF']
Units = [
    'RPM',
    'MPH' if Units_Speed == 1 else 'KPH',
    'V',
    '%',
    'F' if Units_Temp == 1 else 'C',
    'V','%','deg','V','EFF'
]

SettingText = ['Speed Units','Temp Units','Final Drive', 'Injector Size', 'Default Display']
SettingValues = [Units_Speed,Units_Temp,config.Combined_Ratio,config.Injector_Size,DisplayText[Default_Display]]
SettingIndex = 0
SETTINGSMODE = False

READ_THREAD = False
ShowingPeak = False

# Thread-safe button queue
button_queue = queue.Queue()

def button_listener():
    while True:
        for name, btn in [('peak', PeakButton), ('display', DisplayButton),
                          ('select', SelectButton), ('mode', ModeButton)]:
            if btn.is_pressed:
                button_queue.put(name)
                time.sleep(0.2)  # debounce
        time.sleep(0.05)

def Show_Peak(idx):
    global ShowingPeak
    ShowingPeak = True
    WriteText(f"{DisplayText[idx]} PEAK", f"{PeakValues[idx]:.2f}{Units[idx]}")
    time.sleep(1.5)
    ShowingPeak = False

def process_buttons():
    global DisplayIndex, SETTINGSMODE
    while not button_queue.empty():
        ev = button_queue.get_nowait()
        if ev == 'peak' and not ShowingPeak:
            threading.Thread(target=Show_Peak, args=(DisplayIndex,), daemon=True).start()
        elif ev == 'display':
            if not SETTINGSMODE:
                DisplayIndex = (DisplayIndex + 1) % len(DisplayText)
            elif SETTINGSMODE:
                SettingIndex = (SettingIndex + 1) % len(SettingText)
        # TODO: support 'select' and 'mode' for settings or other modes
        elif ev == 'mode':
            if not SETTINGSMODE:
                SETTINGSMODE = True
            elif SETTINGSMODE:
                SETTINGSMODE = False
        elif ev == 'select':
            if not SETTINGSMODE:
                disp.close()
                disp.Init()
            elif SETTINGSMODE:
                # Handle select in settings mode
                if SettingIndex == 0:
                    if Units_Speed == 'MPH':
                        Units_Speed = 'KPH'
                        SettingValues[SettingIndex] = Units_Speed
                        Settings["Units_Speed"] = Units_Speed
                        Save_Config(CONF,Settings)

                    elif Units_Speed == 'KPH':
                        Units_Speed = 'MPH'
                        SettingValues[SettingIndex] = Units_Speed
                        Settings["Units_Speed"] = Units_Speed
                        Save_Config(CONF,Settings)

                if SettingIndex == 1: # Temp Units
                    if Units_Temp == 'F':
                        Units_Temp = 'C'
                        SettingValues[SettingIndex] = Units_Temp
                        Settings["Units_Temp"] = Units_Temp
                        Save_Config(CONF,Settings)

                    elif Units_Temp == 'C':
                        Units_Temp = 'F'
                        SettingValues[SettingIndex] = Units_Temp
                        Settings["Units_Temp"] = Units_Temp
                        Save_Config(CONF,Settings)

                if SettingIndex == 2: # Default Display
                    Default_Display = (Default_Display + 1) % 10
                    SettingValues[SettingIndex] = DisplayText[Default_Display]
                    Settings["Default_Display"] = Default_Display
                    Save_Config(CONF,Settings)

                if SettingIndex == 3: # Number of display Items
                    pass

                if SettingIndex == 4: # Speed Correction 
                    pass

                if SettingIndex == 5: # TPS Calibration
                    pass

                if SettingIndex == 6: # Data Logging On/Off
                    pass

                if SettingIndex == 7: # PWM On/Off
                    pass

                if SettingIndex == 8: # WiFi On/Off
                    pass


def PortConnect(PORT, IPAddr):
    WriteText('Connecting...', IPAddr)
    try:
        return serial.Serial('/dev/ttyUSB0', 9600, timeout=None), IPAddr
    except Exception as e:
        WriteLog(Log_Index, e, "PortConnect")
        return None, IPAddr

def ECU_Connect(PORT):
    while True:
        try:
            PORT.flushInput()
            PORT.write(bytes([0xFF,0xFF,0xEF]))
            time.sleep(0.1)
            if PORT.read_all() == b'\x00\x00\x10':
                WriteText('Connected', "")
                return True
        except Exception as e:
            WriteLog(Log_Index, e, "ECU_Connect")
            time.sleep(0.5)

# Connect serial and ECU
IPAddr = get_local_ip()
PORT = None
while PORT is None:
    PORT, IPAddr = PortConnect(PORT, IPAddr)
    time.sleep(0.1)

ECU_Connected = ECU_Connect(PORT)

# Start background threads
if ECU_Connected:
    R = ReadStream(port=PORT, daemon=True)
    threading.Thread(target=button_listener, daemon=True).start()
    READ_THREAD = True

# Main loop
while READ_THREAD:
    process_buttons()

    if not ShowingPeak and not SETTINGSMODE:
        DisplayValues[:] = [
            int(R.RPM_Value), int(R.SPEED_Value), R.MAF_Value, R.AAC_Value,
            int(R.TEMP_Value), R.BATT_Value, R.INJ_Value,
            int(R.TIM_Value), R.TPS_Value, R.FUEL_Value
        ]
        for i, v in enumerate(DisplayValues):
            PeakValues[i] = max(PeakValues[i], v)
        upper = DisplayText[DisplayIndex]
        lower = f"{DisplayValues[DisplayIndex]:.2f} {Units[DisplayIndex]}"
        WriteText(upper, lower)

        if R.RPM_Value > RPM_Warning:
            FlashText("REV LIMIT!", font1, disp, R.RPM_Value)
        if R.TEMP_Value > Coolant_Warning:
            FlashText("OVERHEAT!", font1, disp, R.TEMP_Value)

    while SETTINGSMODE:
        process_buttons()
        WriteText(SettingText[SettingIndex],SettingValues[SettingIndex]) # We probably only need to run this one instead of updating it every time the loop cyc
    time.sleep(0.05)

# ##################################################################################
# # while DTC_THREAD == True:
# #     WriteText('Code: '+str(DTC_Codes[DTCIndex])+str(' Count:')+str(DTC_Counts[DTCIndex]),str(DTC_DICT[DTC_Codes[DTCIndex]]))
# #     DisplayButton.when_held = Increment_DTC

# # while SETTINGS_THREAD == True:
# #     
