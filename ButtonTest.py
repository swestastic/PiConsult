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
from Main_Bare_Imports.Flash import FlashText, Center_Text
import socket

# OLED screen info
Device_SPI = config.Device_SPI
Device_I2C = config.Device_I2C
OLED_WIDTH   = 128
OLED_HEIGHT  = 64
font1 = ImageFont.truetype('Font.ttc', 18)
font2 = ImageFont.truetype('Font.ttc', 20)

# Button configs
DisplayButton = Button(23, hold_time=0.5) #switch displayed values (i.e. speed, rpm, etc. Or in settings mode switch which setting is shown)
PeakButton = Button(16, hold_time=0.5) # Show peak value of current mode
SelectButton = Button(26, hold_time=0.5)
ModeButton = Button(17, hold_time=0.5) # Switch between modes

def WriteText(upper,lower): 
    # Writes text to the display
    image = Image.new('1', (128, 64), 255)
    draw = ImageDraw.Draw(image)
    draw.text((20,0),str(upper), font = font1, fill = 0)
    if lower is not None: 
        draw.text((20,24), str(lower), font = font2, fill = 0)
    image = image.rotate(180) 
    disp.ShowImage(disp.getbuffer(image))

disp = OLED_2in42.OLED_2in42(spi_freq = 1000000)
disp.Init()

while True:
    # if DisplayButton.is_pressed:
    #     WriteText('Display','Display Pressed')
    # if PeakButton.is_pressed:
    #     WriteText('Peak','Peak Pressed')
    # if SelectButton.is_pressed:
    #     WriteText('Select','Select Pressed')
    # if ModeButton.is_pressed:
    #     WriteText('Mode','Mode Pressed')

    # if DisplayButton.is_held:
    #     WriteText('Display','Display Held')
    # if PeakButton.is_held:
    #     WriteText('Peak','Peak Held')
    # if SelectButton.is_held:
    #     WriteText('Select','Select Held')
    # if ModeButton.is_held:
    #     WriteText('Mode','Mode Held')

    # we need to use lambda becuase when_pressed and when_held only accept functions with zero or one inputs normally
    DisplayButton.when_pressed = lambda: WriteText('Display','Display Pressed') 
    PeakButton.when_pressed = lambda: WriteText('Peak','Peak Pressed')
    SelectButton.when_pressed = lambda: WriteText('Select','Select Pressed')
    ModeButton.when_pressed = lambda: WriteText('Mode','Mode Pressed')

    DisplayButton.when_held = lambda: WriteText('Display','Display Held')
    PeakButton.when_held = lambda: WriteText('Peak','Peak Held')
    SelectButton.when_held = lambda: WriteText('Select','Select Held')
    ModeButton.when_held = lambda: WriteText('Mode','Mode Held')