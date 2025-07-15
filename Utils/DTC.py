import threading
import datetime
import time
import Resources.config as config
from Resources.dtc_dict import DTC_DICT

def Init_DTC(PORT):
    PORT.write(bytes([0xD1]))

def Parse_DTC(PORT):
    DTC_thread = True
    DTC_Codes = [] # Code numbers are keys for the dictionary DCT_DICT
    DTC_Counts = []
    while DTC_thread:
        incomingData = PORT.readall() # NOTE Might be able to get away with this? Idk
        if incomingData:
            dataList = list(incomingData)
        try:
            for i in range(0,len(dataList)):
                if dataList[i] in DTC_DICT: # NOTE Need to actually check how the data is received and parse it accordingly
                    DTC_Codes.append(dataList[i])
                else: 
                    DTC_Counts.append(dataList[i]) # This should be how many starts since last thrown
        except (ValueError,IndexError):
            print('DTC Error')
        
    return DTC_Codes,DTC_Counts