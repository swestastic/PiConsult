#This file handles connecting to the ECU via serial port
#It also handles sending and receiving data to and from the ECU
#Based on @fridlington's K11Consult program

import time
import math
import serial
import threading
import datetime

PORT = serial.Serial('/dev/ttyUSB0',9600, timeout = None) #Open the serial port, this assumes you are using the onboard USB port
