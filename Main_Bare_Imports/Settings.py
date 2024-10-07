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

            "Stock_Final": 4.083,
            "New_Final": 4.083,

            "Stock_Tire_Height": 24.9,
            "New_Tire_Height": 25.1,

            "Stock_Tire_AR": 45,
            "New_Tire_AR": 45,

            "Stock_Tire_Diam": 24.9,
            "New_Tire_Diam": 25.1,

            "Default_Display": 0
        }

# Save settings to the config file
def Save_Config(FILE,settings):
    with open(FILE, 'w') as file:
        json.dump(settings, file)