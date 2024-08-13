import config as config

# if config.Units_Speed == 1:
#     #Speed_Units = 'MPH'
#     def convertToSpeed(self,inputData):
#         return int(round((inputData * 2.11) * 0.621371192237334 * config.Combined_Ratio))
# elif config.Units_Speed == 0:
#     #Speed_Units = 'KPH'
#     def convertToSpeed(self,inputData):
#         return int(round((inputData * 2.11)*config.Combined_Ratio))

def convertToSpeed(inputData, config):
    if config == 1:
        return int(round((inputData * 2.11) * 0.621371192237334 * config.Combined_Ratio))
    elif config == 0:
        return int(round((inputData * 2.11)*config.Combined_Ratio))
        
# if config.Units_Temp == 1:
#     #Temp_Units = 'F'
#     def convertToTemp(inputData):
#         return (inputData - 50) * 9/5 + 32

# elif config.Units_Temp == 0:
#     #Temp_Units = 'C'
#     def convertToTemp(inputData):
#         return inputData - 50

def convertToTemp(inputData, config):
    if config == 1:
        return (inputData - 50) * 9/5 + 32
    elif config == 0:
        return inputData - 50

def convertToRev(inputData):
    return int(round((inputData * 12.5),2))

def convertToBattery(inputData):
    return round(((inputData * 80) / 1000),1)

def convertToMAF(inputData):
    return inputData * 5

def convertToAAC(inputData): 
    return inputData / 2

def convertToInjection(inputData):
    return inputData / 100

def convertToTiming(inputData):
    return 110 - inputData