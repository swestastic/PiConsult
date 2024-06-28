#!/usr/bin/python
# -*- coding:utf-8 -*-

import sys
import os
# picdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'pic')
# libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'lib')
# if os.path.exists(libdir):
#     sys.path.append(libdir)
#     print(libdir)

import logging    
import time
import traceback
# from waveshare_OLED import OLED_2in42
import Resources.OLED_2in42 as OLED_2in42
from PIL import Image,ImageDraw,ImageFont
logging.basicConfig(level=logging.DEBUG)

from gpiozero import Button

try:
    disp = OLED_2in42.OLED_2in42(spi_freq = 1000000)
    #button = Button(2)
    
    logging.info("\r2.42inch OLED ")
    # Initialize library.
    disp.Init()
    # Clear display.
    logging.info("clear display")
    disp.clear()

    # Create blank image for drawing.
    image1 = Image.new('1', (disp.width, disp.height), "WHITE")
    draw = ImageDraw.Draw(image1)
    # font1 = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 18)
    # font2 = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 24)

    font1 = ImageFont.truetype('Font.ttc', 18)
    font2 = ImageFont.truetype('Font.ttc', 24)

    logging.info ("***draw line")
    draw.line([(0,0),(127,0)], fill = 0)
    draw.line([(0,0),(0,63)], fill = 0)
    draw.line([(0,63),(127,63)], fill = 0)
    draw.line([(127,0),(127,63)], fill = 0)
    logging.info ("***draw text")
    draw.text((20,0), 'Consult ', font = font1, fill = 0)
    draw.text((20,24), u'微雪电子 ', font = font2, fill = 0)
    image1 = image1.rotate(180) 
    disp.ShowImage(disp.getbuffer(image1))
    time.sleep(3)
    
    image2 = Image.new('1', (disp.width, disp.height), 255)
    draw = ImageDraw.Draw(image2)
    # font1 = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 18)
    # font2 = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 24)

    font1 = ImageFont.truetype('Font.ttc', 18)
    font2 = ImageFont.truetype('Font.ttc', 24)
    
    logging.info('starting counter')
    draw.text((20,0), 'Consult ', font = font1, fill = 0)
    i=0
    while i < 20:
        image2 = Image.new('1', (disp.width, disp.height), 255)
        draw = ImageDraw.Draw(image2)
        draw.text((20,0), 'Consult ', font = font1, fill = 0)
        draw.text((20,24), str(i), font = font2, fill = 0)
        image2 = image2.rotate(180) 
        disp.ShowImage(disp.getbuffer(image2))
        time.sleep(1)
        #disp.clear()
        draw.rectangle([(0,0),(disp.width,disp.height)],fill=0) #Use this instead of disp.clear() to avoid flashing pixels upon redraw 
        i+=1
    
    #logging.info ("***draw image")
    #Himage2 = Image.new('1', (disp.width, disp.height), 255)  # 255: clear the frame
    #bmp = Image.open(os.path.join(picdir, 'waveshare.bmp'))
    #Himage2.paste(bmp, (0,0))
    #Himage2=Himage2.rotate(180) 	
    #disp.ShowImage(disp.getbuffer(Himage2)) 
    #time.sleep(3)    
    disp.clear()

except IOError as e:
    logging.info(e)
    
except KeyboardInterrupt:    
    logging.info("ctrl + c:")
    disp.module_exit()
    exit()
