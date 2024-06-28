from configupdater import ConfigUpdater

def Increment_Setting():
    global SettingsCount
    SettingsCount += 1
    if SettingsCount > 1:
        SettingsCount = 0

def SettingsMode():
    updater =  ConfigUpdater()
    updater.read('confs.ini')

    temp = updater['units']['temp']
    speed = updater['units']['speed']

    if speed == 1:
        SU = 'MPH' # Speed Units
    else:
        SU = 'KPH'
    if temp == 1:
        TU = 'F' # Temp Units
    else:
        TU = 'C'
    
    SettingsNames = ['Speed Units','Temp Units']
    SettingsValues = [SU,TU]

    writetext(SettingsNames[SettingsCount],SettingsValues[SettingsCount]) #second one should be the current units, referenced from config?
    
    DisplayButton.when_pressed = Increment_Setting #This should be a function that shows the next setting
    PeakButton.when_pressed = Change_Setting #This should be a function that changes the value of the current setting

def Change_Setting():
    global speed
    global temp
    global SettingsCount

    import config

    updater =  ConfigUpdater()
    updater.read('confs.ini')
    
    #take the value of the current setting we're on and update it using setting = (setting+1)%2 so we cycle between 0 and 1
    if SettingsCount == 0:
        speed = updater['units']['speed']
        updater['units']['speed'] = (speed + 1) %2

    if SettingsCount == 1:
        temp = updater['units']['temp']
        updater['units']['temp'] = (temp + 1) %2

    #save to config file
    with open('confs.ini', 'w') as configfile:
        updater.write(configfile)