# NOTE PORT is passed into ReadStream from Main.py.

import serial #type: ignore
import threading
import datetime
import time
import os

from dependencies.settings import Load_Config


CONFIG_FILE = os.path.join(os.path.dirname(__file__), "configJSON.json")

class ReadStream(threading.Thread):
    def __init__(self, port, daemon, settings=None):
        threading.Thread.__init__(self)
        self.daemon = daemon
        self.port = port
        self._settings_lock = threading.Lock()
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
        self.DIGITAL_13 = 0
        self.DIGITAL_1E = 0
        self.DIGITAL_1F = 0
        self.DIGITAL_21 = 0

        initial_settings = settings if isinstance(settings, dict) else Load_Config(CONFIG_FILE)
        self.update_settings(initial_settings)
        
        self.Header = 255
        self.returnBytes = 16
        fileName = datetime.datetime.now().strftime("%d-%m-%y-%H-%M") # NOTE This is unused
        
        self.start()

    def update_settings(self, settings_obj):
        """Update conversion settings at runtime from config JSON values."""
        source = settings_obj if isinstance(settings_obj, dict) else {}
        with self._settings_lock:
            self.settings = dict(source)
            self.units_speed = str(self.settings.get("Units_Speed", "MPH")).upper()
            self.units_temp = str(self.settings.get("Units_Temp", "F")).upper()
        
    @staticmethod
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
            incomingData = self.port.read(18) # 0xFF + length byte + 16 register bytes
            if not incomingData:
                time.sleep(0.002)
                continue

            dataList = list(incomingData)

            if len(dataList) < 16:
                time.sleep(0.002)
                continue

            # if not self.check_data_size(dataList): ## NOTE BROKEN!! FIX ME!!!
            #     continue
                
            try:
                self.SPEED_Value = int(self.convertToSpeed(int(dataList[-2])))
                self.RPM_Value = int(self.convertToRev(int(dataList[-1])))
                self.TEMP_Value = self.convertToTemp(int(dataList[0]))
                self.BATT_Value = self.convertToBattery(float(dataList[1]))
                self.TPS_Value = self.convertToTPS(float(dataList[2])) # Not sure if this is the correct value in dataList
                self.MAF_Value = self.convertToMAF(int(dataList[5]))
                self.AAC_Value = self.convertToAAC(int(dataList[8]))
                self.INJ_Value = self.convertToInjection(int(dataList[6])) # Not sure if this is the correct value in dataList
                self.TIM_Value = int(self.convertToTiming(int(dataList[9]))) # Not sure if this is the correct value in dataList
                self.TPS_Value = self.convertToTPS(float(dataList[2])) # Not sure if this is the correct value in dataList

                # Expose digital bit registers for UI pages.
                # Stream now includes 0x13, 0x1E, 0x1F, and 0x21.
                self.DIGITAL_13 = int(dataList[8])
                self.DIGITAL_1E = int(dataList[13])
                self.DIGITAL_1F = int(dataList[14])
                self.DIGITAL_21 = int(dataList[15])

            except (ValueError, IndexError):
                pass
            time.sleep(0.002)
        return self.SPEED_Value, self.RPM_Value, self.TEMP_Value, self.BATT_Value, self.TPS_Value, self.MAF_Value, self.AAC_Value, self.INJ_Value, self.TIM_Value

    def run(self):
        self.port.write(bytes([0x5A,0x0B,0x5A,0x01,0x5A,0x08,0x5A,0x0C,0x5A,0x0D,0x5A,0x03,0x5A,0x05,0x5A,0x09,0x5A,0x13,0x5A,0x16,0x5A,0x17,0x5A,0x1A,0x5A,0x1C,0x5A,0x1E,0x5A,0x1F,0x5A,0x21,0xF0]))
        #/ Speed / CAS-RPM / CoolantTemp / BatteryVoltage / ThrottlePosition / CAS-RPM / MAF / LH02 / Digital(0x13) / IgnitionTiming / AAC / AFAlphaL / AFAlphaLSelfLear / Digital(0x1E) / Digital(0x1F) / M-R F-C Mnt(0x21) /
        self.consume_data() 

    def convertToSpeed(self,inputData):
        with self._settings_lock:
            units_speed = self.units_speed
        if units_speed == 'MPH':
            return int(round((inputData * 2.11) * 0.621371192237334))
        return int(round((inputData * 2.11)))

    def convertToTemp(self,inputData):
        with self._settings_lock:
            units_temp = self.units_temp
        if units_temp == 'F':
            return (inputData - 50) * 9/5 + 32
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