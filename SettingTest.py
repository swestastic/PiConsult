import sys
import os
import time
import serial # type: ignore
import threading
import datetime
from Resources import config
import Resources.OLED_2in42 as OLED_2in42
from PIL import Image,ImageDraw,ImageFont
from gpiozero import Button # type: ignore
import numpy as np
from Resources import dtc_dict as DTC_DICT

# Button configs
DisplayButton = Button(6) #switch displayed values (i.e. speed, rpm, etc. Or in settings mode switch which setting is shown)
SettingButton = Button(16) # Toggle settings 

########################### Saving and Loading Configs ############################

import json

# Load settings from the config file
def Load_Config():
    try:
        with open('configJSON.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print("Config file not found, using default settings")
        # Default settings if config file doesn't exist
        return {

            "Units_Speed": "MPH",
            "Units_Temp": "F",

            "Stock_Final": 4.083,
            "New_Final": 4.083,

            "Stock_Tire_Height": 24.9,
            "New_Tire_Height": 25.1,

            "Stock_Tire_AR": 45,
            "New_Tire_AR": 45,

            "Stock_Tire_Diam": 24.9,
            "New_Tire_Diam": 25.1,

            "Default_Display": 0
        }

# Save settings to the config file
def Save_Config(settings):
    with open('configJSON.json', 'w') as file:
        json.dump(settings, file)

# Initialize configuration
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

########################################################################################

def Increment_Settings():
    # Increments the settings index, which tells us what to show on the screen in SETTINGS_THREAD mode
    global SettingIndex
    SettingIndex = (SettingIndex + 1) % 6

def WriteText(upper,lower): 
    # Writes text to the display

    image = Image.new('1', (128, 64), 255)
    draw = ImageDraw.Draw(image)
    draw.text((20,0),str(upper), font = font1, fill = 0)
    if lower is not None: 
        draw.text((20,24), str(lower), font = font2, fill = 0)
    image = image.rotate(180) 
    disp.ShowImage(disp.getbuffer(image))

# OLED screen info
Device_SPI = config.Device_SPI
Device_I2C = config.Device_I2C
OLED_WIDTH   = 128
OLED_HEIGHT  = 64
font1 = ImageFont.truetype('Font.ttc', 18)
font2 = ImageFont.truetype('Font.ttc', 20)

disp = OLED_2in42.OLED_2in42(spi_freq = 1000000)
disp.Init()

SettingIndex = 0

DisplayValues = np.zeros(10)
DisplayText = ['RPM','SPEED','MAF','AAC','TEMP','BATT','INJ','TIM','TPS','EFF'] 

SettingText = ['Speed Units','Temp Units','Final Drive', 'Tire Size', 'Injector Size', 'Default Display']
SettingValues = [Units_Speed,Units_Temp,config.Combined_Ratio,New_Tire_Height,config.Injector_Size,DisplayText[Default_Display]]

SETTINGS_THREAD = True

############################ Main ############################

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