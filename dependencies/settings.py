import json

# Load settings from the config file
def Load_Config(FILE):
    try:
        with open(FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print("Config file not found, using default settings")
        # Default settings if config file doesn't exist
        return {

            "Units_Speed": "MPH",
            "Units_Temp": "F",
            "Speed_Correction": 1.0,

            "Default_Display": 0,

            "Coolant_Warning": 200,

            "RPM_Warning": 7000,

            "Log_Index": 0
        }

# Save settings to the config file
def Save_Config(FILE,settings):
    with open(FILE, 'w') as file:
        json.dump(settings, file)