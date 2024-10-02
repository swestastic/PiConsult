# NOTE PORT is not defined in this file, might cause issues? 
# May need to be imported after PORT is defined in main_bare_with_imports.py

import serial #type: ignore
import threading
import datetime
import time
from Resources import config

class ReadStream(threading.Thread):
    def __init__(self, port, daemon):
        threading.Thread.__init__(self)
        self.daemon = daemon
        self.port = port
        self.SPEED_Value = 0
        self.RPM_Value = 0
        self.TEMP_Value = 0
        self.BATT_Value = 0
        self.TPS_Value = 0
        self.MAF_Value = 0
        self.AAC_Value = 0
        self.INJ_Value = 0
        self.TIM_Value = 0
        self.TPS_Value = 0
        self.FUEL_Value = 0
        
        self.Header = 255
        self.returnBytes = 14
        fileName = datetime.datetime.now().strftime("%d-%m-%y-%H-%M") # NOTE This is unused
        
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
        read_thread = True
        while read_thread == True:
            incomingData = self.port.read(16) # NOTE Might need to adjust this is we change init command
            if incomingData:
                dataList = list(incomingData)

            # if not self.check_data_size(dataList): ## NOTE BROKEN!! FIX ME!!!
            #     continue
                
            try:
                self.SPEED_Value = self.convertToSpeed(int(dataList[-2]))
                self.RPM_Value = self.convertToRev(int(dataList[-1]))
                self.TEMP_Value = self.convertToTemp(int(dataList[0]))
                self.BATT_Value = self.convertToBattery(float(dataList[1]))
                self.TPS_Value = self.convertToTPS(float(dataList[2])) # Not sure if this is the correct value in dataList
                self.MAF_Value = self.convertToMAF(int(dataList[5]))
                self.AAC_Value = self.convertToAAC(int(dataList[8]))
                self.INJ_Value = self.convertToInjection(int(dataList[6])) # Not sure if this is the correct value in dataList
                self.TIM_Value = self.convertToTiming(int(dataList[9])) # Not sure if this is the correct value in dataList
                self.TPS_Value = self.convertToTPS(float(dataList[2])) # Not sure if this is the correct value in dataList
                self.FUEL_Value = self.convertToFuel(float(dataList[-2]),float(dataList[6]))

            except (ValueError, IndexError):
                   pass
            time.sleep(0.002)
        return self.SPEED_Value, self.RPM_Value, self.TEMP_Value, self.BATT_Value, self.TPS_Value, self.MAF_Value, self.AAC_Value, self.INJ_Value, self.TIM_Value

    def run(self):
        self.port.write(bytes([0x5A,0x0B,0x5A,0x01,0x5A,0x08,0x5A,0x0C,0x5A,0x0D,0x5A,0x03,0x5A,0x05,0x5A,0x09,0x5A,0x13,0x5A,0x16,0x5A,0x17,0x5A,0x1A,0x5A,0x1C,0x5A,0x21,0xF0]))
        #/ Speed / CAS/RPM / CoolantTemp / BatteryVoltage / ThrottlePosition / CAS/RPM / MAF / LH02 / DigitalBit / IgnitionTiming / AAC / AFAlphaL / AFAlphaLSelfLear / M/R F/C Mnt /
        self.consume_data() 

    if config.Units_Speed == 1:
        Speed_Units = 'MPH'
        def convertToSpeed(self,inputData):
            return int(round((inputData * 2.11) * 0.621371192237334 * config.Combined_Ratio))
        
        def convertToFuel(self,speed,injector): # Miles per gallon #NOTE Needs testing
            # round((60 * 2.11 * 0.621371192237334 * 1) / (0.5 * 4.28),2) #Mi
            return round((speed * 2.11 * 0.621371192237334 * config.Combined_Ratio) / (injector/100 * 4.28),2)
    else:
        Speed_Units = 'KPH'
        def convertToSpeed(self,inputData):
            return int(round((inputData * 2.11)*config.Combined_Ratio))

        def convertToFuel(self,speed,injector): # Km/L #NOTE Broken!! Fix Me
            # round((96.56 * 2.11  * 1) / (0.5*16.2),2) #KM
            return round((speed * 2.11  * config.Combined_Ratio) / (injector/100*1000*16.2),2) # NOTE Broken need to figure out the correct factor for this
        
    if config.Units_Temp == 1:
        #Temp_Units = 'F'
        def convertToTemp(self,inputData):
            return (inputData - 50) * 9/5 + 32
    else:
        #Temp_Units = 'C'
        def convertToTemp(self,inputData):
            return inputData - 50

    def convertToRev(self,inputData): # RPM
        return int(round((inputData * 12.5),2))

    def convertToBattery(self,inputData): # Volts
        return round(((inputData * 80) / 1000),1)

    def convertToMAF(self,inputData): # Volts
        return inputData * 5 / 1000

    def convertToAAC(self,inputData):  # % Duty Cycle
        return inputData / 2

    def convertToInjection(self,inputData): # % Duty Cycle
        return inputData / 100

    def convertToTiming(self,inputData): # Degrees BTDC
        return 110 - inputData
    
    def convertToTPS(self,inputData): # Volts
        return inputData * 20 / 1000

    def logToFile(self,data,fileName):
        with open(fileName + '.hex', 'a+') as logFile:
            logFile.write(data)