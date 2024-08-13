import threading
import datetime
import time
import Resources.config as config

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
        
        read_Thread = True; # NOTE I think this is unused? Becuase it's a different case
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
                
    def consume_data(self,PORT):
        read_thread = True
        while read_thread:
            incomingData = PORT.read(16)
            if incomingData:
                dataList = list(incomingData)

            # if not self.check_data_size(dataList): ## NOTE BROKEN!! FIX ME!!!
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
        return SPEED_Value, RPM_Value, TEMP_Value, BATT_Value, MAF_Value, AAC_Value, INJ_Value, TIM_Value

    def run(self):
        #PORT.write('\x5A\x0B\x5A\x01\x5A\x08\x5A\x0C\x5A\x0D\x5A\x03\x5A\x05\x5A\x09\x5A\x13\x5A\x16\x5A\x17\x5A\x1A\x5A\x1C\x5A\x21\xF0')
        PORT.write(bytes([0x5A,0x0B,0x5A,0x01,0x5A,0x08,0x5A,0x0C,0x5A,0x0D,0x5A,0x03,0x5A,0x05,0x5A,0x09,0x5A,0x13,0x5A,0x16,0x5A,0x17,0x5A,0x1A,0x5A,0x1C,0x5A,0x21,0xF0]))
        #/ Speed / CAS/RPM / CoolantTemp / BatteryVoltage / ThrottlePosition / CAS/RPM / MAF / LH02 / DigitalBit / IgnitionTiming / AAC / AFAlphaL / AFAlphaLSelfLear / M/R F/C Mnt /
        self.consume_data() 

    if config.Units_Speed == 1:
        Speed_Units = 'MPH'
        def convertToSpeed(self,inputData):
            return int(round((inputData * 2.11) * 0.621371192237334 * config.Combined_Ratio))
    else:
        Speed_Units = 'KPH'
        def convertToSpeed(self,inputData):
            return int(round((inputData * 2.11)*config.Combined_Ratio))
        
    if config.Units_Temp == 1:
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