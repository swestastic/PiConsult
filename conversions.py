import config

if config.Units_Speed == 1:
        #Speed_Units = 'MPH'
        def convertToSpeed(self,inputData):
            return int(round((inputData * 2.11) * 0.621371192237334 * config.Combined_Ratio))
else:
    #Speed_Units = 'KPH'
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